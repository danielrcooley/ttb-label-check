from io import BytesIO

import numpy as np
import pytest
from app.pipeline.images import (
    ImageError,
    decode_image,
    rotate_array,
    sniff_format,
    to_canonical,
    unrotate_point,
)
from PIL import Image


def _png_bytes(w=60, h=40, color=(200, 30, 30)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def test_sniff_by_signature_not_extension():
    assert sniff_format(_png_bytes()) == "png"
    assert sniff_format(b"\xff\xd8\xff\xe0JFIF") == "jpeg"
    assert sniff_format(b"GIF89a....") == "gif"
    assert sniff_format(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert sniff_format(b"%PDF-1.7") is None
    assert sniff_format(b"<svg xmlns=") is None


def test_pdf_and_svg_get_specific_messages():
    with pytest.raises(ImageError) as e:
        decode_image(b"%PDF-1.7 ...", max_pixels=10**7, max_side=1280)
    assert e.value.code == "unsupported_format" and "PDF" in e.value.message
    with pytest.raises(ImageError) as e:
        decode_image(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", max_pixels=10**7, max_side=1280)
    assert "SVG" in e.value.message


def test_decompression_bomb_guard_uses_header_dimensions():
    big = _png_bytes(3000, 3000)
    with pytest.raises(ImageError) as e:
        decode_image(big, max_pixels=1_000_000, max_side=1280)
    assert e.value.code == "image_too_large"


def test_corrupt_image_is_reported_cleanly():
    with pytest.raises(ImageError) as e:
        decode_image(b"\x89PNG\r\n\x1a\n" + b"garbage" * 10, max_pixels=10**7, max_side=1280)
    assert e.value.code == "corrupt_image"


def test_downscale_keeps_canonical_dimensions_and_scale():
    d = decode_image(_png_bytes(2000, 1000), max_pixels=10**8, max_side=500)
    assert (d.width, d.height) == (2000, 1000)
    assert d.array.shape[:2] == (250, 500)
    assert d.scale == pytest.approx(0.25)


def test_exif_orientation_is_applied():
    im = Image.new("RGB", (60, 40), (10, 10, 10))
    exif = im.getexif()
    exif[0x0112] = 6  # rotate 90 CW on display
    buf = BytesIO()
    im.save(buf, "JPEG", exif=exif.tobytes())
    d = decode_image(buf.getvalue(), max_pixels=10**7, max_side=1280)
    assert (d.width, d.height) == (40, 60)


@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_unrotate_point_round_trips_a_marked_pixel(degrees):
    arr = np.zeros((40, 60, 3), dtype=np.uint8)  # h=40, w=60
    px, py = 47, 12
    arr[py, px] = 255
    rot = rotate_array(arr, degrees)
    ys, xs = np.nonzero(rot[:, :, 0])
    rx, ry = float(xs[0]) + 0.5, float(ys[0]) + 0.5  # pixel center in rotated space
    ux, uy = unrotate_point(rx, ry, degrees, rot_w=rot.shape[1], rot_h=rot.shape[0])
    assert (int(ux), int(uy)) == (px, py)


def test_to_canonical_undoes_scale_and_rotation():
    quad = to_canonical([(10, 10), (20, 10), (20, 20), (10, 20)], scale=0.5, degrees=0, rot_w=100, rot_h=100)
    assert quad == ((20.0, 20.0), (40.0, 20.0), (40.0, 40.0), (20.0, 40.0))
