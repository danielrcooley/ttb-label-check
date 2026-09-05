"""Image intake: format sniffing, decompression-bomb guard, EXIF orientation, downscaling, and
the coordinate transforms that map OCR boxes back to the oriented original image.

Canonical space = the image after EXIF transpose, at its original resolution. Every box the API
returns lives there.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps

from app.schemas import Quad

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
    (b"BM", "bmp"),
)
SUPPORTED = ("png", "jpeg", "gif", "webp", "tiff", "bmp")


class ImageError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.hint = code, message, hint


def sniff_format(data: bytes) -> str | None:
    for sig, fmt in _SIGNATURES:
        if data.startswith(sig):
            return fmt
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


@dataclass
class DecodedImage:
    array: np.ndarray  # RGB uint8, downscaled working copy
    width: int  # canonical (oriented original) width
    height: int  # canonical height
    scale: float  # working = canonical * scale
    format: str
    filename: str | None


def decode_image(data: bytes, *, max_pixels: int, max_side: int, filename: str | None = None) -> DecodedImage:
    fmt = sniff_format(data)
    if fmt is None:
        head = data[:5]
        if head.startswith(b"%PDF"):
            raise ImageError(
                "unsupported_format",
                "PDF files are not supported.",
                "Export the label artwork as PNG or JPEG and upload that.",
            )
        if head.lstrip().startswith(b"<"):
            raise ImageError(
                "unsupported_format",
                "SVG and other text-based files are not supported.",
                "Upload PNG, JPEG, GIF, WebP, TIFF or BMP.",
            )
        if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypmsf1"):
            raise ImageError(
                "unsupported_format",
                "HEIC photos are not supported.",
                "On iPhone, share the photo as JPEG, or set Camera > Formats to Most Compatible.",
            )
        raise ImageError(
            "unsupported_format", "This file is not a supported image.", "Upload PNG, JPEG, GIF, WebP, TIFF or BMP."
        )
    try:
        im = Image.open(BytesIO(data))
        w, h = im.size
        if w * h > max_pixels:
            raise ImageError(
                "image_too_large",
                f"This image is {w} x {h} pixels, above the {max_pixels // 1_000_000} megapixel limit.",
                "Resize the image below the limit and upload it again.",
            )
        if fmt == "gif":
            im.seek(0)
        # The canonical size is the oriented original, fixed here from the header before any
        # reduced-size decode can change im.size. EXIF orientations 5-8 swap width and height.
        swapped = im.getexif().get(0x0112, 1) in (5, 6, 7, 8)
        canon_w, canon_h = (h, w) if swapped else (w, h)
        if fmt == "jpeg" and min(w, h) >= 2 * max_side:
            # libjpeg decodes at 1/2, 1/4 or 1/8 size while keeping both sides at or above max_side:
            # a 12 MP phone photo costs a quarter of the memory and time. Coordinates are unaffected
            # because scale is computed against the canonical size recorded above.
            im.draft("RGB", (max_side, max_side))
        im = ImageOps.exif_transpose(im) or im
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            # Artwork on a transparent background is composited on white first: dropping the alpha
            # channel would leave the transparent pixels' own colour, often black, so black text on
            # a transparent background became a black image (review 009)
            rgba = im.convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", rgba.size, (255, 255, 255, 255)), rgba)
        im = im.convert("RGB")
    except ImageError:
        raise
    except Exception as exc:  # Pillow raises many types for corrupt data
        raise ImageError(
            "corrupt_image",
            "This image could not be decoded.",
            "The file may be truncated or corrupt. Re-export it and try again.",
        ) from exc
    scale = min(1.0, max_side / max(canon_w, canon_h))
    target = (max(1, round(canon_w * scale)), max(1, round(canon_h * scale)))
    if im.size != target:
        im = im.resize(target, Image.LANCZOS)
    return DecodedImage(array=np.asarray(im), width=canon_w, height=canon_h, scale=scale, format=fmt, filename=filename)


def rotate_array(arr: np.ndarray, degrees: int) -> np.ndarray:
    """Rotate counter-clockwise by 90, 180 or 270 degrees (numpy convention)."""
    k = {0: 0, 90: 1, 180: 2, 270: 3}[degrees]
    return np.ascontiguousarray(np.rot90(arr, k)) if k else arr


def unrotate_point(x: float, y: float, degrees: int, rot_w: int, rot_h: int) -> tuple[float, float]:
    """Map a point in a rotated array back to the unrotated array's coordinates.

    rot_w, rot_h are the rotated array's width and height. Derived from numpy.rot90 semantics:
    k=1 (90 CCW): rotated (x, y) came from original (rot_h - y, x)
    k=2 (180):    original (rot_w - x, rot_h - y)
    k=3 (270 CCW = 90 CW): original (y, rot_w - x)
    """
    if degrees == 0:
        return x, y
    if degrees == 90:
        return rot_h - y, x
    if degrees == 180:
        return rot_w - x, rot_h - y
    if degrees == 270:
        return y, rot_w - x
    raise ValueError(degrees)


def to_canonical(
    box: np.ndarray | Sequence[Sequence[float]], *, scale: float, degrees: int, rot_w: int, rot_h: int
) -> Quad:
    """OCR box (4 points, in the working array as fed to OCR, possibly rotated) -> canonical quad."""
    pts = []
    for x, y in box:
        ux, uy = unrotate_point(float(x), float(y), degrees, rot_w, rot_h)
        pts.append((round(ux / scale, 1), round(uy / scale, 1)))
    return (pts[0], pts[1], pts[2], pts[3])
