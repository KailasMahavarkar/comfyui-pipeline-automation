"""Per-format metadata embedding and reading for image files.

Supports PNG (tEXt chunk), JPEG (EXIF ImageDescription), and WebP (XMP).
Audio/video formats are handled separately when those nodes are built.
"""

import json
from PIL import Image, PngImagePlugin

METADATA_KEY = "comfyui_metadata"


def embed_png(image: Image.Image, metadata: dict, save_path: str, **save_kwargs):
    """Save a PNG with metadata embedded in a tEXt chunk."""
    info = PngImagePlugin.PngInfo()
    info.add_text(METADATA_KEY, json.dumps(metadata, ensure_ascii=False))
    image.save(save_path, format="PNG", pnginfo=info, **save_kwargs)


def read_png(file_path: str) -> dict | None:
    """Read metadata from a PNG tEXt chunk."""
    img = Image.open(file_path)
    raw = img.info.get(METADATA_KEY)
    if raw:
        return json.loads(raw)
    return None


def embed_jpeg(image: Image.Image, metadata: dict, save_path: str, quality: int = 95):
    """Save a JPEG with metadata in EXIF ImageDescription field."""
    import piexif

    meta_str = json.dumps(metadata, ensure_ascii=False)

    # Build minimal EXIF with ImageDescription
    exif_dict = {"0th": {piexif.ImageIFD.ImageDescription: meta_str.encode("utf-8")}}
    exif_bytes = piexif.dump(exif_dict)

    image.save(save_path, format="JPEG", quality=quality, exif=exif_bytes)


def read_jpeg(file_path: str) -> dict | None:
    """Read metadata from JPEG EXIF ImageDescription."""
    import piexif

    try:
        exif_dict = piexif.load(file_path)
    except Exception:
        return None

    desc = exif_dict.get("0th", {}).get(piexif.ImageIFD.ImageDescription)
    if desc:
        if isinstance(desc, bytes):
            desc = desc.decode("utf-8", errors="replace")
        try:
            return json.loads(desc)
        except json.JSONDecodeError:
            return None
    return None


def embed_webp(image: Image.Image, metadata: dict, save_path: str, quality: int = 95):
    """Save a WebP with metadata in XMP data."""
    meta_str = json.dumps(metadata, ensure_ascii=False)

    # Wrap in minimal XMP packet
    xmp = (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:description>{_xml_escape(meta_str)}</dc:description>'
        '</rdf:Description>'
        '</rdf:RDF>'
        '</x:xmpmeta>'
        '<?xpacket end="w"?>'
    )

    image.save(save_path, format="WEBP", quality=quality, xmp=xmp.encode("utf-8"))


def read_webp(file_path: str) -> dict | None:
    """Read metadata from WebP XMP data."""
    import re

    img = Image.open(file_path)
    xmp_data = img.info.get("xmp")
    if not xmp_data:
        return None

    if isinstance(xmp_data, bytes):
        xmp_data = xmp_data.decode("utf-8", errors="replace")

    match = re.search(r'<dc:description>(.*?)</dc:description>', xmp_data, re.DOTALL)
    if match:
        raw = _xml_unescape(match.group(1))
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def embed_metadata(image: Image.Image, metadata: dict, save_path: str,
                   fmt: str = "png", quality: int = 95):
    """Dispatch to format-specific embedding function."""
    fmt = fmt.lower()
    if fmt == "png":
        embed_png(image, metadata, save_path)
    elif fmt in ("jpeg", "jpg"):
        embed_jpeg(image, metadata, save_path, quality=quality)
    elif fmt == "webp":
        embed_webp(image, metadata, save_path, quality=quality)
    else:
        # Unsupported format: save without metadata
        image.save(save_path, quality=quality)


def read_metadata(file_path: str, fmt: str = "png") -> dict | None:
    """Dispatch to format-specific reading function."""
    fmt = fmt.lower()
    if fmt == "png":
        return read_png(file_path)
    elif fmt in ("jpeg", "jpg"):
        return read_jpeg(file_path)
    elif fmt == "webp":
        return read_webp(file_path)
    return None


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _xml_unescape(s: str) -> str:
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
