#!/usr/bin/env python
"""Synthetic TTB label generator with known ground truth.

Renders front/back label pairs for fictional products, plus degraded variants
(rotation, blur, glare, low contrast, perspective, downscale, JPEG) and
"problem" variants (wrong ABV, title-case warning, all-bold warning, altered
wording, tiny warning, missing warning). Deterministic for a given --seed.

Why not AI image generation: the government warning must be letter-perfect
and image generators garble long text. Rendered labels give exact ground truth.

Usage:
    python tools/make_labels.py --out tests/fixtures/labels --seed 42 --count 6 --degraded --problems
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

WARNING_ANCHOR = "GOVERNMENT WARNING:"
WARNING_BODY = (
    " (1) According to the Surgeon General, women should not drink alcoholic beverages "
    "during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic "
    "beverages impairs your ability to drive a car or operate machinery, and may cause "
    "health problems."
)
WARNING_TEXT = WARNING_ANCHOR + WARNING_BODY

# ----------------------------------------------------------------------------- fonts
FONT_DIRS = [
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path(__file__).resolve().parent / "fonts",
]

# (regular, bold) candidates per style; first pair found wins.
FONT_FAMILIES: dict[str, list[tuple[str, str]]] = {
    "serif": [
        ("georgia.ttf", "georgiab.ttf"),
        ("times.ttf", "timesbd.ttf"),
        ("GARA.TTF", "GARABD.TTF"),
        ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"),
        ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf"),
    ],
    "sans": [
        ("arial.ttf", "arialbd.ttf"),
        ("verdana.ttf", "verdanab.ttf"),
        ("calibri.ttf", "calibrib.ttf"),
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
    ],
    "display": [
        ("COPRGTL.TTF", "COPRGTB.TTF"),
        ("BASKVILL.TTF", "BASKVILL.TTF"),
        ("impact.ttf", "impact.ttf"),
        ("georgiab.ttf", "georgiab.ttf"),
        ("DejaVuSerif-Bold.ttf", "DejaVuSerif-Bold.ttf"),
    ],
}


def _find_font(name: str) -> Path | None:
    for d in FONT_DIRS:
        p = d / name
        if p.exists():
            return p
    return None


def resolve_family(style: str) -> tuple[Path, Path]:
    for reg, bold in FONT_FAMILIES[style]:
        r, b = _find_font(reg), _find_font(bold)
        if r and b:
            return r, b
    # last resort: any family that resolves
    for other in FONT_FAMILIES:
        if other == style:
            continue
        for reg, bold in FONT_FAMILIES[other]:
            r, b = _find_font(reg), _find_font(bold)
            if r and b:
                return r, b
    raise SystemExit("No usable TrueType fonts found; add .ttf files to tools/fonts/")


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


# ----------------------------------------------------------------------------- catalog
@dataclass
class Product:
    beverage_type: str  # spirits | wine | malt
    brand: str
    class_type: str
    alcohol_content: str
    net_contents: str
    bottler: str
    origin: str


CATALOG: list[Product] = [
    Product(
        "spirits",
        "OLD TOM DISTILLERY",
        "Kentucky Straight Bourbon Whiskey",
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        "Distilled and Bottled by Old Tom Distillery, Bardstown, Kentucky",
        "Product of USA",
    ),
    Product(
        "spirits",
        "STONE'S THROW",
        "Straight Rye Whiskey",
        "47.5% ALC/VOL (95 PROOF)",
        "750 mL",
        "Bottled by Stone's Throw Spirits Co., Denver, Colorado",
        "Product of USA",
    ),
    Product(
        "spirits",
        "HARBOR LIGHT",
        "London Dry Gin",
        "Alc. 40% by Vol.",
        "1 L",
        "Distilled by Harbor Light Distillers, Portland, Maine",
        "Product of USA",
    ),
    Product(
        "spirits",
        "SABLE RIDGE",
        "Vodka",
        "40% Alc./Vol. (80 Proof)",
        "1.75 L",
        "Produced and Bottled by Sable Ridge Spirits, Austin, Texas",
        "Product of USA",
    ),
    Product(
        "wine",
        "Willow Creek Cellars",
        "Cabernet Sauvignon",
        "Alc. 13.5% by Vol.",
        "750 mL",
        "Produced and Bottled by Willow Creek Cellars, Paso Robles, California",
        "Product of USA",
    ),
    Product(
        "wine",
        "Blue Heron Vineyards",
        "Chardonnay",
        "14.1% Alc./Vol.",
        "750 mL",
        "Vinted and Bottled by Blue Heron Vineyards, Walla Walla, Washington",
        "Product of USA",
    ),
    Product(
        "malt",
        "COPPER KETTLE BREWING",
        "India Pale Ale",
        "6.8% ALC/VOL",
        "12 FL OZ (355 mL)",
        "Brewed and Bottled by Copper Kettle Brewing Co., Asheville, North Carolina",
        "Product of USA",
    ),
    Product(
        "malt",
        "IRON ANVIL",
        "Stout",
        "ABV 5.2%",
        "16 FL. OZ.",
        "Brewed by Iron Anvil Brewery, Duluth, Minnesota",
        "Product of USA",
    ),
    Product(
        "spirits",
        "CHATEAU BELMONT",
        "Blended Scotch Whisky",
        "43% Alc./Vol. (86 Proof)",
        "700 mL",
        "Imported by Belmont Imports LLC, Newark, New Jersey",
        "Product of Scotland",
    ),
    Product(
        "spirits",
        "RIDGEBACK",
        "Tequila Blanco",
        "40% Alc./Vol.",
        "375 mL",
        "Imported by Ridgeback Spirits, El Paso, Texas",
        "Product of Mexico",
    ),
]

THEMES = [
    # (background, text, accent)
    ("#f6f1e3", "#1d1a16", "#7a1f1f"),  # cream, near-black, oxblood
    ("#ffffff", "#111111", "#2b4c7e"),  # white, black, navy
    ("#101010", "#e8dcb8", "#c9a227"),  # black, parchment, gold (dark label)
    ("#1e2a1e", "#f2efe6", "#b58b3c"),  # bottle green, off-white, brass
    ("#e9e4d8", "#2a2420", "#3e5a3a"),  # linen, brown, forest
]


# ----------------------------------------------------------------------------- drawing helpers
def text_size(draw: ImageDraw.ImageDraw, s: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), s, font=f)
    return right - left, bottom - top


def fit_font(draw, s: str, path: Path, max_w: int, start: int, min_size: int = 24) -> ImageFont.FreeTypeFont:
    size = start
    while size > min_size:
        f = font(path, size)
        if text_size(draw, s, f)[0] <= max_w:
            return f
        size -= 4
    return font(path, min_size)


def draw_centered(draw, y: int, s: str, f: ImageFont.FreeTypeFont, W: int, fill: str) -> int:
    w, h = text_size(draw, s, f)
    draw.text(((W - w) // 2, y), s, font=f, fill=fill)
    return y + h


def wrap_words(draw, words: list[tuple[str, ImageFont.FreeTypeFont]], max_w: int, space_w: int):
    """Greedy wrap of (word, font) pairs into lines. Returns list of lines (lists of pairs)."""
    lines: list[list[tuple[str, ImageFont.FreeTypeFont]]] = [[]]
    cur = 0
    for w, f in words:
        ww = text_size(draw, w, f)[0]
        add = ww if not lines[-1] else ww + space_w
        if lines[-1] and cur + add > max_w:
            lines.append([(w, f)])
            cur = ww
        else:
            lines[-1].append((w, f))
            cur += add
    return lines


def draw_mixed_paragraph(draw, x: int, y: int, max_w: int, words, fill: str, line_gap: int = 6) -> int:
    space_w = text_size(draw, " ", words[0][1])[0]
    for line in wrap_words(draw, words, max_w, space_w):
        cx = x
        line_h = 0
        for w, f in line:
            draw.text((cx, y), w, font=f, fill=fill)
            ww, wh = text_size(draw, w, f)
            cx += ww + space_w
            line_h = max(line_h, wh)
        y += line_h + line_gap
    return y


# ----------------------------------------------------------------------------- label renderers
W, H = 1200, 1600  # ~4 x 5.3 in at 300 dpi


def render_front(
    p: Product,
    theme,
    fam_display,
    fam_body,
    rng: random.Random,
    brand_override: str | None = None,
    abv_override: str | None = None,
) -> Image.Image:
    bg, fg, accent = theme
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    # border
    m = 48
    d.rectangle([m, m, W - m, H - m], outline=accent, width=6)
    d.rectangle([m + 14, m + 14, W - m - 14, H - m - 14], outline=accent, width=2)

    _disp_reg, disp_bold = fam_display
    body_reg, _body_bold = fam_body
    brand = brand_override or p.brand
    y = 220
    # small establishment line
    y = draw_centered(d, y, f"EST. 19{rng.randint(10, 95):02d}", font(body_reg, 30), W, accent) + 40
    # brand, possibly two lines
    words = brand.split()
    if len(words) >= 2 and text_size(d, brand, font(disp_bold, 150))[0] > W - 2 * m - 80:
        half = math.ceil(len(words) / 2)
        lines = [" ".join(words[:half]), " ".join(words[half:])]
    else:
        lines = [brand]
    for ln in lines:
        f = fit_font(d, ln, disp_bold, W - 2 * m - 100, 150, 60)
        y = draw_centered(d, y, ln, f, W, fg) + 18
    y += 30
    # rule
    d.line([(W // 2 - 220, y), (W // 2 + 220, y)], fill=accent, width=4)
    y += 40
    # class/type, possibly two lines
    ct = p.class_type
    f_ct = fit_font(d, ct, body_reg, W - 2 * m - 160, 64, 36)
    if text_size(d, ct, font(body_reg, 64))[0] > W - 2 * m - 160 and len(ct.split()) >= 3:
        ws = ct.split()
        half = math.ceil(len(ws) / 2)
        for ln in (" ".join(ws[:half]), " ".join(ws[half:])):
            y = draw_centered(d, y, ln.upper() if p.brand.isupper() else ln, font(body_reg, 60), W, fg) + 12
    else:
        y = draw_centered(d, y, ct.upper() if p.brand.isupper() else ct, f_ct, W, fg) + 12
    # bottom block: ABV + net contents
    abv = abv_override or p.alcohol_content
    f_small = font(body_reg, 40)
    yb = H - m - 200
    draw_centered(d, yb, abv, f_small, W, fg)
    draw_centered(d, yb + 60, p.net_contents, f_small, W, fg)
    return img


def render_back(
    p: Product, theme, fam_body, rng: random.Random, *, warning_mode: str = "normal", warning_scale: float = 1.0
) -> Image.Image:
    """warning_mode: normal | titlecase | allbold | altered | missing"""
    bg, fg, accent = theme
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    m = 48
    d.rectangle([m, m, W - m, H - m], outline=accent, width=6)
    body_reg, body_bold = fam_body
    x, y, max_w = m + 70, 160, W - 2 * m - 140

    f_body = font(body_reg, 36)
    # marketing blurb (noise text, like real back labels)
    blurb = rng.choice(
        [
            "Crafted in small batches and aged in charred new oak barrels for a smooth, "
            "full-bodied character. Enjoy responsibly.",
            "Made with locally sourced grain and pure spring water. Each bottle is hand-numbered by our cellar team.",
            "Estate grown and bottled. Best served slightly chilled with food and friends.",
        ]
    )
    y = draw_mixed_paragraph(d, x, y, max_w, [(w, f_body) for w in blurb.split()], fg) + 40
    # bottler and origin
    y = draw_mixed_paragraph(d, x, y, max_w, [(w, f_body) for w in p.bottler.split()], fg) + 10
    y = draw_mixed_paragraph(d, x, y, max_w, [(w, f_body) for w in p.origin.split()], fg) + 10
    y = (
        draw_mixed_paragraph(
            d, x, y, max_w, [(w, f_body) for w in (p.alcohol_content + "   " + p.net_contents).split()], fg
        )
        + 60
    )
    # warning block
    if warning_mode != "missing":
        ws = max(14, int(34 * warning_scale))
        f_wb = font(body_bold, ws)
        f_wr = font(body_reg, ws)
        anchor = WARNING_ANCHOR
        body = WARNING_BODY
        if warning_mode == "titlecase":
            anchor = "Government Warning:"
        if warning_mode == "altered":
            body = body.replace("may cause health problems", "can cause health problems")
        body_font = f_wb if warning_mode == "allbold" else f_wr
        words = [(w, f_wb) for w in anchor.split()] + [(w, body_font) for w in body.split()]
        d.line([(x, y - 20), (x + max_w, y - 20)], fill=accent, width=2)
        y = draw_mixed_paragraph(d, x, y, max_w, words, fg, line_gap=4)
        d.line([(x, y + 6), (x + max_w, y + 6)], fill=accent, width=2)
    # barcode-ish block at bottom (noise)
    bx, by = W // 2 - 200, H - m - 220
    for i in range(60):
        wdt = rng.choice([2, 3, 5])
        d.rectangle([bx + i * 6, by, bx + i * 6 + wdt, by + 120], fill=fg)
    return img


# ----------------------------------------------------------------------------- degradations
def _persp_coeffs(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A = np.asarray(A, dtype=np.float64)
    B = np.asarray(dst, dtype=np.float64).reshape(8)
    res = np.linalg.lstsq(A, B, rcond=None)[0]
    return tuple(res)


def degrade(img: Image.Image, kind: str, rng: random.Random) -> Image.Image:
    bgc = img.getpixel((5, 5))
    if kind == "rotate7":
        return img.rotate(rng.choice([-7, 7]), expand=True, fillcolor=bgc, resample=Image.BICUBIC)
    if kind == "rotate90":
        return img.rotate(90, expand=True)
    if kind == "blur":
        return img.filter(ImageFilter.GaussianBlur(radius=1.6))
    if kind == "lowcontrast":
        return ImageEnhance.Contrast(img).enhance(0.45)
    if kind == "glare":
        w, h = img.size
        glare = Image.new("L", (w, h), 0)
        gd = ImageDraw.Draw(glare)
        cx, cy = int(w * rng.uniform(0.3, 0.7)), int(h * rng.uniform(0.2, 0.6))
        for r in range(int(w * 0.45), 0, -8):
            val = int(255 * (1 - r / (w * 0.45)) ** 2)
            gd.ellipse([cx - r, cy - r // 2, cx + r, cy + r // 2], fill=val)
        glare = glare.filter(ImageFilter.GaussianBlur(40))
        white = Image.new("RGB", (w, h), "white")
        return Image.composite(white, img, glare.point(lambda v: min(255, int(v * 0.85))))
    if kind == "perspective":
        w, h = img.size
        dx, dy = int(w * 0.08), int(h * 0.05)
        src = [(0, 0), (w, 0), (w, h), (0, h)]
        dst = [(dx, dy), (w - dx // 2, 0), (w, h - dy), (dx // 3, h)]
        coeffs = _persp_coeffs(dst, src)
        return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=bgc)
    if kind == "small":
        w, h = img.size
        s = img.resize((w // 3, h // 3), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), (90, 90, 90))
        canvas.paste(s, ((w - s.width) // 2, (h - s.height) // 2))
        return canvas
    if kind == "jpeg":
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, "JPEG", quality=35)
        buf.seek(0)
        return Image.open(buf).convert("RGB")
    raise ValueError(kind)


DEGRADATIONS = ["rotate7", "blur", "glare", "lowcontrast", "perspective", "small", "jpeg", "rotate90"]


# ----------------------------------------------------------------------------- driver
@dataclass
class ImageRecord:
    file: str
    side: str  # front | back
    variant: str  # clean | <degradation> | <problem>
    expected_findings: dict = field(default_factory=dict)


@dataclass
class AppRecord:
    id: str
    beverage_type: str
    brand: str
    class_type: str
    alcohol_content: str
    net_contents: str
    bottler: str
    origin: str
    theme: int
    images: list[ImageRecord] = field(default_factory=list)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--count", type=int, default=len(CATALOG))
    ap.add_argument("--degraded", action="store_true", help="also emit degraded variants")
    ap.add_argument("--problems", action="store_true", help="also emit problem-label variants")
    ap.add_argument("--fmt", default="png", choices=["png", "jpg"])
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fam = {k: resolve_family(k) for k in FONT_FAMILIES}
    ext = "png" if args.fmt == "png" else "jpg"

    records: list[AppRecord] = []
    for i, p in enumerate(CATALOG[: args.count]):
        theme_i = i % len(THEMES)
        theme = THEMES[theme_i]
        fam_display = fam["display"] if p.brand.isupper() else fam["serif"]
        fam_body = fam["sans"] if i % 2 else fam["serif"]
        app_id = f"APP-{i + 1:03d}"
        rec = AppRecord(
            app_id,
            p.beverage_type,
            p.brand,
            p.class_type,
            p.alcohol_content,
            p.net_contents,
            p.bottler,
            p.origin,
            theme_i,
        )

        front = render_front(p, theme, fam_display, fam_body, rng)
        back = render_back(p, theme, fam_body, rng)
        for side, im in (("front", front), ("back", back)):
            fn = f"{app_id}_{side}_clean.{ext}"
            im.save(out / fn)
            rec.images.append(ImageRecord(fn, side, "clean", {"warning_present": side == "back"}))

        if args.degraded:
            # two degradations per app, cycling through the list
            for k in range(2):
                kind = DEGRADATIONS[(i * 2 + k) % len(DEGRADATIONS)]
                side, im = ("front", front) if k == 0 else ("back", back)
                fn = f"{app_id}_{side}_{kind}.{ext}"
                degrade(im, kind, rng).save(out / fn)
                rec.images.append(ImageRecord(fn, side, kind, {"warning_present": side == "back"}))

        if args.problems and i < 6:
            mode = ["wrong_abv", "titlecase", "allbold", "altered", "tiny", "missing"][i]
            if mode == "wrong_abv":
                bad = "40% Alc./Vol. (80 Proof)" if "45%" in p.alcohol_content else "45% Alc./Vol. (90 Proof)"
                im = render_front(p, theme, fam_display, fam_body, rng, abv_override=bad)
                fn = f"{app_id}_front_wrong_abv.{ext}"
                im.save(out / fn)
                rec.images.append(ImageRecord(fn, "front", "wrong_abv", {"label_abv": bad}))
            else:
                kw = {"warning_mode": mode} if mode != "tiny" else {"warning_scale": 0.45}
                im = render_back(p, theme, fam_body, rng, **kw)
                fn = f"{app_id}_back_{mode}.{ext}"
                im.save(out / fn)
                rec.images.append(ImageRecord(fn, "back", mode, {"warning_present": mode != "missing"}))
        records.append(rec)

    manifest = {
        "seed": args.seed,
        "warning_text": WARNING_TEXT,
        "applications": [
            {**{k: v for k, v in asdict(r).items() if k != "images"}, "images": [asdict(im) for im in r.images]}
            for r in records
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    n_img = sum(len(r.images) for r in records)
    print(f"wrote {n_img} images for {len(records)} applications to {out}")


if __name__ == "__main__":
    main()
