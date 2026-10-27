"""Logo image validation and content-addressed storage."""

import hashlib
import io
import os
import re

from PIL import Image

Image.MAX_IMAGE_PIXELS = 4096 * 4096

MAX_LOGO_BYTES = 2 * 1024 * 1024
STANDARD_SIZES = [(32, 32), (112, 32), (128, 128), (320, 240), (600, 600)]
MIME_BY_FORMAT = {"PNG": "image/png", "JPEG": "image/jpeg"}
EXT_BY_MIME = {"image/png": "png", "image/jpeg": "jpg"}

_media_dir = None


class ImageError(ValueError):
    pass


def init(data_dir):
    global _media_dir
    _media_dir = os.path.join(data_dir, "media")
    os.makedirs(_media_dir, mode=0o750, exist_ok=True)


def media_dir():
    return _media_dir


def path_for(name: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}\.(png|jpg)", name or ""):
        raise ValueError("invalid media name")
    return os.path.join(_media_dir, name)


def normalise(data: bytes, width=None, height=None, fit=False):
    """Validate an uploaded/fetched image and re-encode it.

    Re-encoding strips metadata and anything appended to the file, so only
    pixel data from a decodable PNG/JPEG ever reaches the carousel or the UI.
    Returns (bytes, mime, width, height)."""
    if len(data) > MAX_LOGO_BYTES:
        raise ImageError("Image is larger than 2 MB.")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in MIME_BY_FORMAT:
            raise ImageError("Only PNG and JPEG images are supported.")
        img.load()
    except Image.DecompressionBombError:
        raise ImageError("Image dimensions are too large.")
    except ImageError:
        raise
    except Exception:
        raise ImageError("File is not a valid PNG or JPEG image.")

    if width and height and img.size != (width, height):
        if not fit:
            raise ImageError(f"Image is {img.size[0]}x{img.size[1]}, expected {width}x{height}.")
        img = _fit(img, width, height, fmt)

    out = io.BytesIO()
    if fmt == "PNG":
        if img.mode not in ("RGB", "RGBA", "P", "L", "LA"):
            img = img.convert("RGBA")
        img.save(out, "PNG", optimize=True)
    else:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(out, "JPEG", quality=90, optimize=True)
    return out.getvalue(), MIME_BY_FORMAT[fmt], img.size[0], img.size[1]


def _fit(img, width, height, fmt):
    """Scale to fit inside width x height and centre on a transparent (PNG) or
    black (JPEG) canvas."""
    img = img.convert("RGBA")
    img.thumbnail((width, height), Image.LANCZOS)
    if fmt == "PNG":
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    canvas.paste(img, ((width - img.size[0]) // 2, (height - img.size[1]) // 2), img)
    return canvas if fmt == "PNG" else canvas.convert("RGB")


_broadcast_cache = {}


def broadcast_variant(name: str, mime: str):
    """A smaller copy of a stored logo for the carousel: a 256-colour PNG, or a
    JPEG when the image has no transparency, whichever is smallest. Used only
    if it saves at least 10%; the stored original is never changed.
    Returns (bytes, mime)."""
    key = (name, mime)
    if key in _broadcast_cache:
        return _broadcast_cache[key]
    original = read(name)
    best = (original, mime)
    try:
        img = Image.open(io.BytesIO(original))
        img.load()
        rgba = img.convert("RGBA")
        opaque = rgba.getextrema()[3][0] == 255
        candidates = []
        out = io.BytesIO()
        # method 2 = fast octree, the only quantizer that keeps an alpha channel
        (rgba.quantize(256, method=2) if not opaque else rgba.convert("RGB").quantize(256)).save(out, "PNG", optimize=True)
        candidates.append((out.getvalue(), "image/png"))
        if opaque:
            out = io.BytesIO()
            rgba.convert("RGB").save(out, "JPEG", quality=85, optimize=True, progressive=False)
            candidates.append((out.getvalue(), "image/jpeg"))
        for data, m in candidates:
            if len(data) < len(best[0]) * 0.9:
                best = (data, m)
    except Exception:
        pass  # keep the original if anything about re-encoding fails
    if len(_broadcast_cache) > 2000:
        _broadcast_cache.clear()
    _broadcast_cache[key] = best
    return best


def store(data: bytes, mime: str) -> str:
    name = hashlib.sha256(data).hexdigest() + "." + EXT_BY_MIME[mime]
    path = os.path.join(_media_dir, name)
    if not os.path.exists(path):
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    return name


def read(name: str) -> bytes:
    with open(path_for(name), "rb") as f:
        return f.read()


def garbage_collect(referenced: set):
    """Remove stored files no longer referenced by logos or snapshots."""
    removed = 0
    for name in os.listdir(_media_dir):
        if name.endswith(".tmp") or name not in referenced:
            try:
                os.remove(os.path.join(_media_dir, name))
                removed += 1
            except OSError:
                pass
    return removed
