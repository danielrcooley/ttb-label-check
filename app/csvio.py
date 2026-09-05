"""CSV intake for batch mode: tolerant of Excel exports, strict about the result.

Accepts UTF-8 (with or without BOM) or cp1252; sniffs comma, semicolon and tab delimiters; maps
common header spellings to the application fields; validates every row with the same model the
single-application screen uses; returns per-row errors instead of failing the whole file.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.schemas import ApplicationFields, BeverageType

# A single cell may hold most of a 2 MB upload; the default limit (128 KB) would raise csv.Error
# and answer 500 for a file the size guard accepted (review 009)
csv.field_size_limit(8 * 1024 * 1024)

_ALIASES: dict[str, str] = {
    "application_id": "application_id",
    "applicationid": "application_id",
    "id": "application_id",
    "ttb_id": "application_id",
    "ttbid": "application_id",
    "application": "application_id",
    "cola_id": "application_id",
    "reference": "application_id",
    "beverage_type": "beverage_type",
    "beverage": "beverage_type",
    "type": "beverage_type",
    "commodity": "beverage_type",
    "product_type": "beverage_type",
    "brand_name": "brand_name",
    "brand": "brand_name",
    "brandname": "brand_name",
    "class_type": "class_type",
    "class": "class_type",
    "classtype": "class_type",
    "class_type_designation": "class_type",
    "designation": "class_type",
    "class_and_type": "class_type",
    "alcohol_content": "alcohol_content",
    "alcohol": "alcohol_content",
    "abv": "alcohol_content",
    "alc": "alcohol_content",
    "alcohol_by_volume": "alcohol_content",
    "proof": "alcohol_content",
    "net_contents": "net_contents",
    "net_content": "net_contents",
    "netcontents": "net_contents",
    "contents": "net_contents",
    "volume": "net_contents",
    "size": "net_contents",
    "container_size": "net_contents",
    "bottler": "bottler",
    "producer": "bottler",
    "name_and_address": "bottler",
    "bottler_name_and_address": "bottler",
    "name_address": "bottler",
    "manufacturer": "bottler",
    "importer": "bottler",
    "country_of_origin": "country_of_origin",
    "origin": "country_of_origin",
    "country": "country_of_origin",
    "imported": "imported",
    "import": "imported",
    "is_imported": "imported",
    "images": "images",
    "image": "images",
    "files": "images",
    "filenames": "images",
    "image_files": "images",
    "labels": "images",
}
_TRUE = {"y", "yes", "true", "1", "x", "imported"}
_BEV = [
    (
        re.compile(r"spirit|whisk|bourbon|vodka|gin\b|rum\b|tequila|brandy|liqueur|distilled", re.I),
        BeverageType.spirits,
    ),
    (re.compile(r"wine|cider|mead|sake|vermouth", re.I), BeverageType.wine),
    (re.compile(r"malt|beer|ale\b|lager|stout|porter|ipa\b|hard seltzer", re.I), BeverageType.malt),
]

TEMPLATE_HEADER = [
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
TEMPLATE_EXAMPLE = [
    "COLA-2026-000123",
    "spirits",
    "OLD TOM DISTILLERY",
    "Kentucky Straight Bourbon Whiskey",
    "45% Alc./Vol. (90 Proof)",
    "750 mL",
    "Distilled and Bottled by Old Tom Distillery, Bardstown, Kentucky",
    "USA",
    "no",
    "COLA-2026-000123_front.png;COLA-2026-000123_back.png",
]


@dataclass
class CsvRow:
    row_number: int
    application: ApplicationFields | None
    images: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CsvResult:
    rows: list[CsvRow]
    columns: list[str]
    unmapped_columns: list[str]
    delimiter: str
    warnings: list[str] = field(default_factory=list)


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower().lstrip("﻿")).strip("_")


def _decode(data: bytes) -> tuple[str, str | None]:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(enc), None
        except UnicodeDecodeError:
            continue
    return data.decode("cp1252", errors="replace"), "File was not UTF-8; decoded as Windows-1252."


def _beverage(value: str) -> BeverageType | None:
    v = value.strip().lower()
    if v in ("spirits", "spirit", "distilled spirits", "ds"):
        return BeverageType.spirits
    if v in ("wine", "w"):
        return BeverageType.wine
    if v in ("malt", "malt beverage", "beer", "mb"):
        return BeverageType.malt
    for pat, bev in _BEV:
        if pat.search(v):
            return bev
    return None


def template_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(TEMPLATE_HEADER)
    w.writerow(TEMPLATE_EXAMPLE)
    return buf.getvalue()


def parse_csv(data: bytes, *, max_rows: int) -> CsvResult:
    text, warn = _decode(data)
    warnings = [warn] if warn else []
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        raw_header = next(reader)
    except StopIteration:
        return CsvResult(rows=[], columns=[], unmapped_columns=[], delimiter=delimiter, warnings=["The file is empty."])
    headers = [_norm_header(h) for h in raw_header]
    mapping = {i: _ALIASES[h] for i, h in enumerate(headers) if h in _ALIASES}
    unmapped = [raw_header[i] for i, h in enumerate(headers) if h not in _ALIASES and h]
    if "brand_name" not in mapping.values():
        warnings.append("No brand name column was recognized. Expected a header like 'brand_name' or 'Brand'.")

    rows: list[CsvRow] = []
    for n, rec in enumerate(reader, start=2):
        if not any(cell.strip() for cell in rec):
            continue
        if len(rows) >= max_rows:
            warnings.append(f"Only the first {max_rows} rows were read.")
            break
        fields: dict[str, str] = {}
        for i, cell in enumerate(rec):
            key = mapping.get(i)
            if key and cell.strip():
                value = cell.strip()
                if headers[i] == "proof" and re.fullmatch(r"\d{1,3}(?:[.,]\d)?", value):
                    value = f"{value} proof"  # a bare number under a Proof header is a proof, not a percentage
                fields[key] = value if key not in fields else fields[key] + " " + value
        errors: list[str] = []
        images = [s.strip() for s in re.split(r"[;|]", fields.pop("images", "")) if s.strip()]
        bev_raw = fields.pop("beverage_type", "")
        bev = _beverage(bev_raw) if bev_raw else None
        if bev is None:
            bev = _beverage(fields.get("class_type", "")) or None
            if bev is None:
                errors.append("beverage_type missing or not recognized (use spirits, wine or malt).")
        imported = fields.pop("imported", "").strip().lower() in _TRUE
        app: ApplicationFields | None = None
        if not errors:
            try:
                app = ApplicationFields(beverage_type=bev, imported=imported, **fields)
            except ValidationError as exc:
                errors.extend(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        rows.append(CsvRow(row_number=n, application=app, images=images, errors=errors))
    return CsvResult(
        rows=rows,
        columns=list(dict.fromkeys(mapping.values())),
        unmapped_columns=unmapped,
        delimiter=delimiter,
        warnings=warnings,
    )
