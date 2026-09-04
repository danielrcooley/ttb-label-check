#!/usr/bin/env python
"""Fetch a stratified sample of approved COLAs (application data + label images) from TTB's
Public COLA Registry (https://ttbonline.gov/colasonline/) for a real-world evaluation.

What it does, politely: one session, an identifying User-Agent, one request every --delay
seconds, hard caps on records and images, resumable. The registry's search export gives the
day's records (TTB ID, brand, fanciful name, class/type, origin); the printable form page of
each record gives the applicant's name and address, the date issued, and the label images with
their types (front, back, neck, other).

What it writes (NOT committed; label artwork belongs to the brand owners and the folder is
git-ignored): <out>/<ttbid>_<n>_<type>.<ext>, <out>/cola.csv (one row per record, all registry
fields, image file names) and <out>/applications.csv in the batch screen's template format.
Alcohol content and net contents are not COLA form fields, so those columns are blank.

Usage:
    python tools/cola_fetch.py --from 08/31/2026 --to 09/02/2026 --per-type 40 --out tests/fixtures/real
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import random
import re
import time
from pathlib import Path
from typing import Any

import requests

try:  # the registry's certificate chain verifies against the OS trust store, not certifi's bundle
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

BASE = "https://ttbonline.gov/colasonline/"
UA = "label-check-eval/0.1 (one-off evaluation sample, rate-limited; github.com/danielrcooley/ttb-label-check)"
IMAGE_TYPES = {
    "brand (front) or keg collar": "front",
    "back": "back",
    "neck": "neck",
    "other": "other",
    "strip": "strip",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp"}
US_PLACES = {
    "ALABAMA",
    "ALASKA",
    "ARIZONA",
    "ARKANSAS",
    "CALIFORNIA",
    "COLORADO",
    "CONNECTICUT",
    "DELAWARE",
    "FLORIDA",
    "GEORGIA",
    "HAWAII",
    "IDAHO",
    "ILLINOIS",
    "INDIANA",
    "IOWA",
    "KANSAS",
    "KENTUCKY",
    "LOUISIANA",
    "MAINE",
    "MARYLAND",
    "MASSACHUSETTS",
    "MICHIGAN",
    "MINNESOTA",
    "MISSISSIPPI",
    "MISSOURI",
    "MONTANA",
    "NEBRASKA",
    "NEVADA",
    "NEW HAMPSHIRE",
    "NEW JERSEY",
    "NEW MEXICO",
    "NEW YORK",
    "NORTH CAROLINA",
    "NORTH DAKOTA",
    "OHIO",
    "OKLAHOMA",
    "OREGON",
    "PENNSYLVANIA",
    "RHODE ISLAND",
    "SOUTH CAROLINA",
    "SOUTH DAKOTA",
    "TENNESSEE",
    "TEXAS",
    "UTAH",
    "VERMONT",
    "VIRGINIA",
    "WASHINGTON",
    "WEST VIRGINIA",
    "WISCONSIN",
    "WYOMING",
    "DISTRICT OF COLUMBIA",
    "PUERTO RICO",
    "GUAM",
    "VIRGIN ISLANDS",
    "UNITED STATES",
    "USA",
    "AMERICAN",
}
_MALT = re.compile(r"MALT BEVERAGE|\bBEER\b|\bALE\b|\bSTOUT\b|\bLAGER\b|\bPORTER\b|CEREAL BEVERAGE|NEAR BEER", re.I)
_SPIRITS = re.compile(
    r"WHISK|VODKA|\bGIN\b|\bRUM\b|TEQUILA|MEZCAL|AGAVE|BRANDY|LIQUEUR|COCKTAIL|SPIRIT|PROOF|SPECIALT|"
    r"CORDIAL|ABSINTHE|SCHNAPPS|PISCO|GRAPPA|BITTERS|AQUAVIT|SOJU|BAIJIU|CACHACA",
    re.I,
)
_WINE = re.compile(r"\bWINE\b|CIDER|\bMEAD\b|SAKE|VERMOUTH|CHAMPAGNE|PERRY|SANGRIA", re.I)
_HEADER = re.compile(r"^(\d{1,2}[a-z]?\.\s|PART\s+[IVX]+\b|FOR TTB USE)")


def beverage_type(class_desc: str) -> str:
    if _MALT.search(class_desc):
        return "malt"
    if _SPIRITS.search(class_desc):
        return "spirits"
    if _WINE.search(class_desc):
        return "wine"
    return "spirits"


def is_domestic(origin_desc: str) -> bool:
    return origin_desc.strip().upper() in US_PLACES


def text_lines(page: str) -> list[str]:
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", body))
    return [ln.strip() for ln in text.splitlines() if ln.strip() and ln.strip() != "\xa0"]


def section(lines: list[str], header: str) -> list[str]:
    """Lines of a numbered form item: after the header, its wrapped continuation lines and its
    parenthetical hint ("(Required)", "(If any)"), until the next numbered item."""
    for i, ln in enumerate(lines):
        if ln.startswith(header):
            j = i + 1
            hint = next((k for k in range(i + 1, min(i + 5, len(lines))) if lines[k].startswith("(")), None)
            if hint is not None:
                j = hint + 1
            out = []
            while j < len(lines) and not _HEADER.match(lines[j]):
                out.append(lines[j])
                j += 1
            return out
    return []


def parse_form(page: str) -> dict[str, Any]:
    lines = text_lines(page)
    images = [
        (html.unescape(src), html.unescape(alt).strip())
        for src, alt in re.findall(r'<img src="([^"]*publicViewAttachment[^"]*)"[^>]*alt="Label Image: ([^"]*)"', page)
    ]
    dims = [ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("Actual Dimensions")]
    if any("has been reduced" in ln for ln in lines):  # the registry downscaled at least one image
        dims.append("reduced by registry")
    return {
        "applicant": [ln for ln in section(lines, "8. NAME AND ADDRESS") if not ln.startswith("8a.")],
        "brand": " ".join(section(lines, "6. BRAND NAME")),
        "fanciful": " ".join(section(lines, "7. FANCIFUL NAME")),
        "serial": " ".join(section(lines, "4. SERIAL NUMBER")),
        "varietal": " ".join(section(lines, "10. GRAPE VARIETAL")),
        "appellation": " ".join(section(lines, "11. WINE APPELLATION")),
        "date_issued": " ".join(section(lines, "19. DATE ISSUED")),
        "images": images,
        "dimensions": dims,
    }


class Registry:
    def __init__(self, delay: float) -> None:
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.delay = delay
        self._last = 0.0
        self.requests = 0

    def _wait(self) -> None:
        dt = time.monotonic() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self._last = time.monotonic()
        self.requests += 1

    def get(self, url: str) -> requests.Response:
        self._wait()
        r = self.s.get(url if url.startswith("http") else BASE + url, timeout=90)
        r.raise_for_status()
        return r

    def search_export(self, date_from: str, date_to: str) -> list[dict[str, str]]:
        self.get("publicSearchColasBasic.do")
        self._wait()
        r = self.s.post(
            BASE + "publicSearchColasBasicProcess.do?action=search",
            data={
                "searchCriteria.dateCompletedFrom": date_from,
                "searchCriteria.dateCompletedTo": date_to,
                "searchCriteria.productOrFancifulName": "",
                "searchCriteria.productNameSearchType": "E",
                "searchCriteria.classTypeFrom": "",
                "searchCriteria.classTypeTo": "",
                "searchCriteria.originCode": "",
            },
            timeout=120,
        )
        r.raise_for_status()
        r = self.get("publicSaveSearchResultsToFile.do?path=/publicSearchColasBasicProcess")
        rows = list(csv.DictReader(io.StringIO(r.text)))
        for row in rows:
            row["TTB ID"] = row["TTB ID"].strip().strip("'")
        return rows

    def form(self, ttbid: str) -> dict[str, Any]:
        return parse_form(self.get(f"viewColaDetails.do?action=publicFormDisplay&ttbid={ttbid}").text)

    def image(self, src: str) -> tuple[bytes, str]:
        r = self.get("https://ttbonline.gov" + src if src.startswith("/") else src)
        return r.content, r.headers.get("content-type", "")


COLA_COLUMNS = [
    "ttbid",
    "beverage_type",
    "brand",
    "fanciful",
    "class_code",
    "class_desc",
    "origin_code",
    "origin_desc",
    "domestic",
    "applicant",
    "permit",
    "serial",
    "date_completed",
    "date_issued",
    "varietal",
    "appellation",
    "images",
    "image_types",
    "dimensions",
]


def ext_for(filename: str, content_type: str) -> str | None:
    suffix = Path(filename.split("?")[0]).suffix.lower()
    if suffix in IMAGE_EXTS:
        return ".jpg" if suffix == ".jpeg" else suffix
    ct = content_type.lower()
    for key, ext in (("jpeg", ".jpg"), ("png", ".png"), ("gif", ".gif"), ("tiff", ".tif"), ("bmp", ".bmp")):
        if key in ct:
            return ext
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="date_from", required=True, help="completed date from, MM/DD/YYYY")
    ap.add_argument("--to", dest="date_to", required=True, help="completed date to, MM/DD/YYYY")
    ap.add_argument("--per-type", type=int, default=40, help="records per beverage type (spirits, wine, malt)")
    ap.add_argument("--max-images", type=int, default=4, help="images per record")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    ap.add_argument("--max-requests", type=int, default=1200, help="hard cap on HTTP requests for this run")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="tests/fixtures/real")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cola_csv = out / "cola.csv"
    have: dict[str, dict[str, str]] = {}
    if cola_csv.exists():
        with cola_csv.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                have[row["ttbid"]] = row
    counts = {"spirits": 0, "wine": 0, "malt": 0}
    for row in have.values():
        counts[row["beverage_type"]] = counts.get(row["beverage_type"], 0) + 1
    print(f"already have {len(have)} records {counts}", flush=True)

    reg = Registry(args.delay)
    rows = reg.search_export(args.date_from, args.date_to)
    print(f"export: {len(rows)} records completed {args.date_from}..{args.date_to}", flush=True)
    random.Random(args.seed).shuffle(rows)

    new_file = not cola_csv.exists()
    with cola_csv.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLA_COLUMNS)
        if new_file:
            w.writeheader()
        for row in rows:
            if all(counts[t] >= args.per_type for t in counts):
                break
            if reg.requests >= args.max_requests:
                print("request cap reached", flush=True)
                break
            ttbid = row["TTB ID"]
            class_desc = row.get("Class/Type Desc") or ""
            if not class_desc:  # the registry's CSV does not quote commas inside descriptions: columns shift
                continue
            btype = beverage_type(class_desc)
            if ttbid in have or counts[btype] >= args.per_type:
                continue
            try:
                form = reg.form(ttbid)
            except requests.RequestException as exc:
                print(f"{ttbid}: form fetch failed ({exc})", flush=True)
                continue
            if not form["images"] or not form["date_issued"]:
                print(f"{ttbid}: skipped (no images or not issued)", flush=True)
                continue
            files: list[str] = []
            types: list[str] = []
            for k, (src, alt) in enumerate(form["images"][: args.max_images], start=1):
                kind = IMAGE_TYPES.get(alt.lower(), "img")
                try:
                    data, ctype = reg.image(src)
                except requests.RequestException as exc:
                    print(f"{ttbid}: image {k} failed ({exc})", flush=True)
                    continue
                ext = ext_for(src.split("filename=")[-1], ctype)
                if ext is None or len(data) < 1000:
                    print(f"{ttbid}: image {k} skipped (type {ctype!r}, {len(data)} bytes)", flush=True)
                    continue
                name = f"{ttbid}_{k}_{kind}{ext}"
                (out / name).write_bytes(data)
                files.append(name)
                types.append(kind)
            if not files:
                continue
            rec = {
                "ttbid": ttbid,
                "beverage_type": btype,
                "brand": row["Brand Name"] or form["brand"],
                "fanciful": row["Fanciful Name"] or form["fanciful"],
                "class_code": row.get("Class/Type") or "",
                "class_desc": class_desc,
                "origin_code": row.get("Origin") or "",
                "origin_desc": row.get("Origin Desc") or "",
                "domestic": "yes" if is_domestic(row.get("Origin Desc") or "") else "no",
                "applicant": " | ".join(form["applicant"]),
                "permit": row["Permit No."],
                "serial": row["Serial Number"] or form["serial"],
                "date_completed": row["Completed Date"],
                "date_issued": form["date_issued"],
                "varietal": form["varietal"],
                "appellation": form["appellation"],
                "images": ";".join(files),
                "image_types": ";".join(types),
                "dimensions": ";".join(form["dimensions"]),
            }
            w.writerow(rec)
            f.flush()
            have[ttbid] = rec
            counts[btype] += 1
            print(f"{ttbid} {btype:7s} {len(files)} image(s)  {rec['brand'][:40]!r}  totals {counts}", flush=True)

    # Batch-screen CSV (alcohol content and net contents are not COLA fields: left blank on purpose).
    with (out / "applications.csv").open("w", encoding="utf-8", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(
            [
                "application_id",
                "beverage_type",
                "brand_name",
                "class_type",
                "alcohol_content",
                "net_contents",
                "bottler",
                "country_of_origin",
                "imported",
                "images",
            ]
        )
        for rec in have.values():
            dom = rec["domestic"] == "yes"
            cw.writerow(
                [
                    rec["ttbid"],
                    rec["beverage_type"],
                    rec["brand"],
                    rec["class_desc"].title(),
                    "",
                    "",
                    rec["applicant"].replace(" | ", ", "),
                    "" if dom else rec["origin_desc"].title(),
                    "no" if dom else "yes",
                    rec["images"],
                ]
            )
    print(f"done: {len(have)} records, {reg.requests} requests this run, {counts}", flush=True)


if __name__ == "__main__":
    main()
