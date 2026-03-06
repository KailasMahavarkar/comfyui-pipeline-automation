# Phase 1: Foundation Libraries - Research

**Researched:** 2026-03-06
**Domain:** Python library modules for image metadata, filesystem operations, prompt mutation, and workflow fingerprinting
**Confidence:** HIGH

## Summary

Phase 1 builds 9 standalone Python library modules under `lib/` that all subsequent nodes depend on. These modules have zero ComfyUI dependencies -- they are pure Python, testable in isolation. The primary technical challenges are: (1) cross-format metadata embedding (PNG/JPEG/WebP each use different mechanisms), (2) cross-platform filesystem operations (Windows vs Unix path handling and file locking), (3) deterministic workflow fingerprinting from JSON structures, and (4) prompt mutation strategies that produce genuinely distinct variants.

The standard stack is straightforward: Pillow for image I/O and PNG metadata, piexif for JPEG EXIF, filelock for cross-platform thread-safe file locking, and Python stdlib for everything else. All modules use `pathlib.Path` exclusively for filesystem operations (LIB-15).

**Primary recommendation:** Build modules in dependency order (naming -> metadata -> sidecar -> manifest -> response_parser -> bulk_prompter -> tag_generator -> scanner -> fingerprint), with each module fully tested before moving to the next.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LIB-01 | Naming module resolves template tokens ({prefix}, {topic}, {date}, {time}, {resolution}, {counter}, {batch}, {format}) into filenames | String template resolution with `str.replace()` or `string.Template`. Counter needs session-level state. |
| LIB-02 | Naming module supports preset templates (Simple, Detailed, Minimal, Custom) | Dict mapping preset names to template strings. Straightforward. |
| LIB-03 | Metadata module embeds flat tags + prompt in PNG tEXt, JPEG EXIF, WebP XMP, and GIF comment | Pillow PngInfo for PNG, piexif for JPEG EXIF ImageDescription, Pillow `xmp=` param for WebP, GIF comment via Pillow info dict. |
| LIB-04 | Sidecar module writes .json sidecar alongside each output with full categorized tags and provenance | `json.dump()` with pathlib. Trivial module. |
| LIB-05 | Manifest module appends rows to manifest.csv with thread-safe locking and auto-header creation | `csv.writer` + `filelock` for cross-platform file locking. |
| LIB-06 | Response parser extracts values from nested JSON using dot-path notation with auto-parse of stringified JSON | Custom dot-path walker. Must handle stringified JSON and markdown code block stripping. |
| LIB-07 | Bulk prompter generates N prompt variants using 6 mutation strategies | Random-based text manipulation. Word bank loading from shipped .txt files. |
| LIB-08 | Tag generator implements 3-layer pipeline: prompt extraction, topic bank lookup, and LLM generation | Layer 1+2 are pure Python. Layer 3 calls external API (uses response_parser). |
| LIB-09 | Scanner detects gaps in topic x prompt x resolution matrix by comparing filesystem to planned entries | pathlib directory traversal, set difference for gap detection. |
| LIB-10 | Scanner performs Level 2 integrity checks (existence + size + header validation) on every run | File header magic byte comparison. PNG: `\x89PNG\r\n\x1a\n`, JPEG: `\xff\xd8`, WebP: bytes 8-12 = `WEBP`. |
| LIB-11 | Scanner performs Level 3 integrity checks (Pillow decode) on files modified in last hour on restart | `Image.open().load()` and `Image.verify()` for full decode validation. |
| LIB-12 | Fingerprint module computes workflow fingerprint from node types, connections, checkpoint/LoRA names, and workflow_name | Canonical JSON serialization + hashlib SHA-256. |
| LIB-13 | Fingerprint module saves/loads/compares fingerprints and produces actionable collision error messages | JSON file I/O + structured error messages with diff details. |
| LIB-14 | Scanner implements incremental caching (full scan on first run, in-memory updates after each save) | In-memory set of known files, updated on save events. |
| LIB-15 | All lib modules use pathlib for cross-platform filesystem compatibility | Use `pathlib.Path` everywhere, never `os.path.join`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pillow | >=10.0 | PNG metadata (PngInfo), WebP XMP embedding, image decode for integrity checks | Industry standard for Python image I/O. Already a ComfyUI dependency. |
| piexif | 1.1.3 | JPEG EXIF writing (ImageDescription field) | Pure Python, no C dependencies. Only viable option for EXIF writing without heavy dependencies. Inactive maintenance but stable and widely used (295K weekly downloads). |
| filelock | >=3.13 | Cross-platform file locking for manifest.csv thread safety | Platform-independent (fcntl on Unix, msvcrt on Windows). Used by pip, tox, virtualenv. v3.25.0 current. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib | stdlib | SHA-256 fingerprint computation | Always (workflow fingerprinting) |
| pathlib | stdlib | Cross-platform path operations | Always (LIB-15 mandate) |
| json | stdlib | JSON serialization/deserialization | Always (sidecar, fingerprint, response parsing) |
| csv | stdlib | Manifest CSV writing | Manifest module |
| re | stdlib | Regex for prompt parsing, markdown stripping | Response parser, tag generator, bulk prompter |
| random | stdlib | Random selection for mutation strategies | Bulk prompter |
| datetime | stdlib | Date/time tokens for naming | Naming module |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| piexif | exif (pip package) | exif is read-only for most tags. piexif supports writing. Stick with piexif. |
| piexif | py3exiv2 | Requires libexiv2 C library. piexif is pure Python, simpler to install. |
| filelock | portalocker | Both work. filelock is more actively maintained, used by more projects. |
| str.replace for templates | string.Template or f-strings | str.replace is simplest for known token set. No need for Template complexity. |
| json-fingerprint package | Custom canonical JSON + hashlib | Custom is simpler for this use case. We control what fields go into the hash. No need for a dependency. |

**Installation:**
```bash
pip install Pillow piexif filelock
```

Note: Pillow and numpy are already ComfyUI dependencies. piexif and filelock are the only new dependencies for Phase 1.

## Architecture Patterns

### Recommended Project Structure
```
lib/
    __init__.py          # Exports all public functions/classes
    naming.py            # Template token resolution + presets
    metadata.py          # Per-format metadata embedding
    sidecar.py           # JSON sidecar writer
    manifest.py          # CSV manifest writer with locking
    response_parser.py   # Dot-path JSON extraction
    bulk_prompter.py     # 6 mutation strategies + word bank loading
    tag_generator.py     # 3-layer tag pipeline
    scanner.py           # Filesystem gap detection + integrity
    fingerprint.py       # Workflow fingerprint + collision detection
word_banks/
    adjectives.txt       # ~200 entries
    styles.txt           # ~100 entries
    moods.txt            # ~60 entries
    scene_details.txt    # ~150 entries
tests/
    test_naming.py
    test_metadata.py
    test_sidecar.py
    test_manifest.py
    test_response_parser.py
    test_bulk_prompter.py
    test_tag_generator.py
    test_scanner.py
    test_fingerprint.py
```

### Pattern 1: Stateless Function Modules
**What:** Most lib modules expose pure functions with no module-level state. Pass all context as arguments.
**When to use:** naming, metadata, sidecar, manifest, response_parser, fingerprint, tag_generator
**Example:**
```python
# lib/naming.py
from pathlib import Path
from datetime import datetime

PRESETS = {
    "Simple": "{prefix}_{date}_{time}",
    "Detailed": "{prefix}_{topic}_{resolution}_{counter}",
    "Minimal": "{prefix}_{counter}",
}

def resolve_template(
    template: str,
    prefix: str = "comfyui",
    topic: str = "unknown",
    resolution: str = "unknown",
    width: int = 0,
    height: int = 0,
    counter: int = 0,
    batch: int = 0,
    format_ext: str = "png",
) -> str:
    now = datetime.now()
    tokens = {
        "{prefix}": prefix,
        "{topic}": _sanitize(topic),
        "{date}": now.strftime("%Y%m%d"),
        "{time}": now.strftime("%H%M%S"),
        "{datetime}": now.strftime("%Y%m%d_%H%M%S"),
        "{resolution}": f"{width}x{height}" if width and height else resolution,
        "{width}": str(width),
        "{height}": str(height),
        "{counter}": f"{counter:04d}",
        "{batch}": f"{batch:04d}",
        "{format}": format_ext,
    }
    result = template
    for token, value in tokens.items():
        result = result.replace(token, value)
    return _sanitize_filename(result)
```

### Pattern 2: Scanner with Incremental Cache
**What:** Full scan on first run, in-memory set updates after each save
**When to use:** scanner.py (LIB-14)
**Example:**
```python
# lib/scanner.py
class MatrixScanner:
    def __init__(self, base_path: Path, topics: list, resolutions: list, prompts_per_topic: int):
        self.base_path = base_path
        self._known_files: set[str] = set()
        self._scanned = False
        # ...

    def full_scan(self) -> None:
        """Scan filesystem and populate known_files set."""
        self._known_files.clear()
        for path in self.base_path.rglob("*"):
            if path.is_file() and path.suffix in (".png", ".jpg", ".jpeg", ".webp"):
                relative = str(path.relative_to(self.base_path))
                if self._check_integrity_level2(path):
                    self._known_files.add(relative)
        self._scanned = True

    def register_save(self, relative_path: str) -> None:
        """Update cache after successful save (avoids re-scan)."""
        self._known_files.add(relative_path)

    def find_next_gap(self) -> Optional[GapEntry]:
        """Return first missing entry in the matrix."""
        if not self._scanned:
            self.full_scan()
        # Compare planned entries vs known files
        ...
```

### Pattern 3: Format-Dispatched Metadata Embedding
**What:** Single public function dispatches to format-specific internal functions
**When to use:** metadata.py (LIB-03)
**Example:**
```python
# lib/metadata.py
from pathlib import Path
from PIL import Image, PngImagePlugin
import piexif

def embed_metadata(filepath: Path, tags: list[str], prompt: str, format_type: str) -> None:
    """Embed flat metadata into image file based on format."""
    flat_text = f"prompt: {prompt}\ntags: {', '.join(tags)}"
    dispatchers = {
        "png": _embed_png,
        "jpeg": _embed_jpeg,
        "jpg": _embed_jpeg,
        "webp": _embed_webp,
    }
    handler = dispatchers.get(format_type.lower())
    if handler:
        handler(filepath, flat_text)

def _embed_png(filepath: Path, text: str) -> None:
    img = Image.open(filepath)
    info = PngImagePlugin.PngInfo()
    info.add_text("comfyui_metadata", text)
    img.save(filepath, pnginfo=info)

def _embed_jpeg(filepath: Path, text: str) -> None:
    img = Image.open(filepath)
    exif_dict = piexif.load(img.info.get("exif", b""))
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = text.encode("utf-8")
    exif_bytes = piexif.dump(exif_dict)
    img.save(filepath, exif=exif_bytes)

def _embed_webp(filepath: Path, text: str) -> None:
    img = Image.open(filepath)
    xmp = f'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta><rdf:RDF><rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:description>{text}</dc:description></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'.encode("utf-8")
    img.save(filepath, xmp=xmp)
```

### Anti-Patterns to Avoid
- **Global mutable state in modules:** Do not use module-level variables for counter state or file caches. Pass state via class instances or function parameters. The scanner is the one exception where a class with internal state is appropriate.
- **os.path instead of pathlib:** LIB-15 mandates pathlib everywhere. Never use `os.path.join()`, `os.path.exists()`, etc.
- **Opening files without explicit encoding:** Always use `encoding="utf-8"` for text file operations.
- **Catching bare Exception:** Catch specific exceptions (OSError, json.JSONDecodeError, etc.)
- **Modifying images in place without reload:** When embedding metadata into an already-saved file, always open -> modify -> save. Do not assume the Image object from a previous save is still valid.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform file locking | Custom fcntl/msvcrt wrapper | `filelock.FileLock` | Edge cases in Windows locking semantics, stale lock cleanup, timeout handling |
| JPEG EXIF manipulation | Raw byte manipulation of EXIF segments | `piexif` | EXIF format has complex IFD structures, byte ordering, and tag types |
| PNG metadata chunks | Manual PNG chunk writing | `Pillow.PngImagePlugin.PngInfo` | PNG chunk CRC calculation, compression handling |
| Image format detection | Filename extension checking | Magic byte header checking | Extensions can lie. Headers are authoritative. |
| JSON canonicalization for hashing | Ad-hoc string concatenation | `json.dumps(data, sort_keys=True, separators=(',', ':'))` | Deterministic output requires sorted keys and consistent separators |
| WebP metadata | Raw WebP container manipulation | `Pillow save(xmp=...)` | WebP container format is complex (RIFF-based) |

**Key insight:** Image metadata formats are deceptively complex. EXIF alone has multiple IFD directories, byte ordering variations, and tag type constraints. Always use established libraries.

## Common Pitfalls

### Pitfall 1: piexif crashes on images without existing EXIF
**What goes wrong:** `piexif.load(img.info["exif"])` raises KeyError when the image has no EXIF data.
**Why it happens:** Not all JPEG files have EXIF data. Images created by Pillow from scratch have none.
**How to avoid:** Use `img.info.get("exif", b"")` and handle the empty bytes case. When loading empty bytes, construct a fresh exif_dict: `{"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}`.
**Warning signs:** Works in testing with photos from cameras, fails with programmatically generated images.

### Pitfall 2: PNG metadata lost on re-save
**What goes wrong:** Opening a PNG and saving it without passing `pnginfo=` drops all custom text chunks.
**Why it happens:** Pillow does not automatically preserve PngInfo on save. You must explicitly pass it.
**How to avoid:** For metadata embedding, always create a new PngInfo object with all desired chunks and pass it via `pnginfo=` parameter.
**Warning signs:** Metadata present after first write, missing after any subsequent image processing.

### Pitfall 3: WebP XMP must be bytes, not str
**What goes wrong:** `img.save("out.webp", xmp="text")` may silently fail or produce unreadable metadata.
**Why it happens:** The `xmp` parameter expects bytes.
**How to avoid:** Always encode: `xmp=xmp_string.encode("utf-8")`.
**Warning signs:** Metadata appears to write but cannot be read back.

### Pitfall 4: Non-deterministic hash from unsorted JSON keys
**What goes wrong:** Same workflow produces different fingerprints on different runs.
**Why it happens:** Python dict ordering is insertion-order, not sorted. `json.dumps()` without `sort_keys=True` produces different strings for semantically identical dicts.
**How to avoid:** Always use `json.dumps(data, sort_keys=True, separators=(',', ':'))` before hashing.
**Warning signs:** Fingerprint collision errors on valid resume scenarios.

### Pitfall 5: File locking on Windows with different semantics
**What goes wrong:** Manifest CSV gets corrupted or locking deadlocks on Windows.
**Why it happens:** Windows locks are mandatory (kernel-enforced), Unix locks are advisory. The filelock library handles this, but raw fcntl/msvcrt code does not.
**How to avoid:** Use `filelock.FileLock` with a separate `.lock` file, not locking the CSV itself.
**Warning signs:** Works on Linux/Mac, fails on Windows. Or works single-threaded, fails multi-threaded.

### Pitfall 6: Image.verify() vs Image.load() for corruption detection
**What goes wrong:** `verify()` passes but image is actually truncated/corrupt.
**Why it happens:** `verify()` only checks file structure, not pixel data. Some PNG files with corrupt IDAT chunks pass verify.
**How to avoid:** For Level 3 integrity, use `img.load()` which forces full pixel decode. Must reopen image after `verify()` since it invalidates the Image object.
**Warning signs:** Corrupt images pass Level 3 check, downstream nodes get garbled data.

### Pitfall 7: Filename sanitization edge cases
**What goes wrong:** Topics with special characters create invalid paths on Windows.
**Why it happens:** Windows forbids `<>:"/\|?*` in filenames. Some topics may contain unicode or spaces.
**How to avoid:** Sanitize by replacing forbidden chars with underscores, strip leading/trailing dots/spaces, limit length to 200 chars.
**Warning signs:** Works on Linux with topic "urban/rural", fails on Windows.

## Code Examples

Verified patterns from official sources:

### PNG Metadata Embedding
```python
# Source: Pillow docs - Image file formats
from PIL import Image, PngImagePlugin

img = Image.new("RGB", (100, 100), "red")
info = PngImagePlugin.PngInfo()
info.add_text("comfyui_metadata", "prompt: a sunset\ntags: sunset, ocean")
img.save("output.png", pnginfo=info)

# Reading back:
img2 = Image.open("output.png")
metadata = img2.text.get("comfyui_metadata", "")
```

### JPEG EXIF Writing with piexif
```python
# Source: piexif docs - Functions
import piexif
from PIL import Image

img = Image.new("RGB", (100, 100), "red")
# Save initial JPEG
img.save("output.jpg", "JPEG")

# Create EXIF from scratch (no existing EXIF)
exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
exif_dict["0th"][piexif.ImageIFD.ImageDescription] = b"prompt: a sunset\ntags: sunset, ocean"
exif_bytes = piexif.dump(exif_dict)

# Insert into existing file
piexif.insert(exif_bytes, "output.jpg")
```

### WebP XMP Metadata
```python
# Source: Pillow docs - WebP save parameters
from PIL import Image

img = Image.new("RGB", (100, 100), "red")
xmp_data = b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
xmp_data += b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
xmp_data += b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
xmp_data += b'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
xmp_data += b'<dc:description>prompt: a sunset</dc:description>'
xmp_data += b'</rdf:Description></rdf:RDF></x:xmpmeta>'
xmp_data += b'<?xpacket end="w"?>'
img.save("output.webp", xmp=xmp_data)
```

### Thread-Safe CSV Manifest
```python
# Source: filelock docs
from pathlib import Path
from filelock import FileLock
import csv

def append_manifest(manifest_path: Path, row: dict) -> None:
    lock_path = manifest_path.with_suffix(".csv.lock")
    headers = ["topic", "resolution", "variant_index", "filename", "path", "tags", "saved_at"]

    with FileLock(lock_path):
        write_header = not manifest_path.exists()
        with open(manifest_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
```

### Deterministic Workflow Fingerprint
```python
# Source: Python stdlib hashlib + json
import hashlib
import json

def compute_fingerprint(
    node_types: list[str],
    connections: list[tuple[str, str]],
    checkpoints: list[str],
    loras: list[str],
    workflow_name: str,
) -> str:
    canonical = {
        "node_types": sorted(node_types),
        "connections": sorted([f"{src}->{dst}" for src, dst in connections]),
        "checkpoints": sorted(checkpoints),
        "loras": sorted(loras),
        "workflow_name": workflow_name,
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

### File Integrity Checking
```python
# Source: Pillow docs + community patterns
from pathlib import Path
from PIL import Image

MAGIC_BYTES = {
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8",
    ".jpeg": b"\xff\xd8",
    ".webp": (8, b"WEBP"),  # offset, bytes
}

def check_level2(filepath: Path) -> bool:
    """Level 2: existence + size + header check. ~0.1ms per file."""
    if not filepath.exists() or filepath.stat().st_size < 1024:
        return False
    suffix = filepath.suffix.lower()
    magic = MAGIC_BYTES.get(suffix)
    if magic is None:
        return True  # Unknown format, skip header check
    with open(filepath, "rb") as f:
        if isinstance(magic, tuple):
            offset, expected = magic
            f.seek(offset)
            return f.read(len(expected)) == expected
        return f.read(len(magic)) == magic

def check_level3(filepath: Path) -> bool:
    """Level 3: Full Pillow decode. Catches truncated data."""
    try:
        with Image.open(filepath) as img:
            img.load()  # Forces full pixel decode
        return True
    except (OSError, SyntaxError, ValueError):
        return False
```

### Dot-Path JSON Response Parser
```python
import json
import re

def extract_value(data: dict, dot_path: str):
    """Walk nested JSON using dot-path notation. Auto-parses stringified JSON."""
    parts = dot_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, str):
            # Auto-parse stringified JSON
            current = json.loads(_strip_markdown_code_blocks(current))
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current

def _strip_markdown_code_blocks(text: str) -> str:
    """Remove ```json ... ``` wrappers from LLM responses."""
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else text
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| os.path for file operations | pathlib.Path | Python 3.4+ (mature) | Cleaner API, cross-platform by default |
| fcntl/msvcrt manual locking | filelock library | 2015+ (now v3.25) | No platform detection code needed |
| piexif for all image EXIF | piexif (still best option) | No change | Library is unmaintained but stable. No replacement yet. |
| Manual XMP construction | Pillow native xmp= param | Pillow 8.3+ (2021) | No need for external XMP libraries |

**Deprecated/outdated:**
- `PIL.Image.ANTIALIAS`: Use `PIL.Image.LANCZOS` instead (deprecated since Pillow 10.0)
- `piexif` has not had a release since v1.1.3. It works but monitor for Python version compatibility issues.

## Open Questions

1. **GIF comment metadata embedding**
   - What we know: Build plan mentions GIF comment extension for metadata. Requirements LIB-03 lists GIF as a target format for v1.
   - What's unclear: However, REQUIREMENTS.md LIB-03 only lists PNG, JPEG, WebP, and GIF. GIF is listed. Pillow supports GIF comment via `img.info["comment"]` but writing comments back requires accessing the GIF comment extension.
   - Recommendation: Implement GIF comment support via Pillow's `comment` parameter in `save()`. Test with: `img.save("out.gif", comment=b"metadata")`. Low complexity.

2. **Word bank format and content**
   - What we know: 4 files totaling ~510 entries. Used by bulk prompter mutation strategies.
   - What's unclear: Exact content not yet defined. Phase 1 needs functional word banks to test bulk prompter.
   - Recommendation: Ship minimal word banks (20-30 entries each) for Phase 1 testing. Full curation happens in Phase 4 per the build plan.

3. **piexif Python 3.12+ compatibility**
   - What we know: piexif 1.1.3 was last released years ago. It's unmaintained.
   - What's unclear: Whether it works flawlessly with Python 3.12+.
   - Recommendation: Test early. If issues arise, the fallback is using Pillow's own limited EXIF support via `img.save(exif=exif_bytes)` with manually constructed EXIF bytes, or switching to the `exif` package for a different approach.

## Sources

### Primary (HIGH confidence)
- [Pillow docs - Image file formats](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) - PNG PngInfo, WebP xmp parameter, save options
- [Pillow PngImagePlugin source](https://pillow.readthedocs.io/en/stable/_modules/PIL/PngImagePlugin.html) - PngInfo.add_text() API
- [piexif PyPI](https://pypi.org/project/piexif/) - v1.1.3, pure Python, EXIF writing
- [piexif docs - Functions](https://piexif.readthedocs.io/en/latest/functions.html) - load/dump/insert API
- [filelock PyPI](https://pypi.org/project/filelock/) - v3.25.0, cross-platform file locking
- [filelock docs](https://py-filelock.readthedocs.io/en/latest/) - FileLock usage patterns
- [Python hashlib docs](https://docs.python.org/3/library/hashlib.html) - SHA-256 API

### Secondary (MEDIUM confidence)
- [Pillow WebP metadata tests](https://github.com/python-pillow/Pillow/blob/main/Tests/test_file_webp_metadata.py) - XMP read/write test patterns
- [Pillow issue #6342](https://github.com/python-pillow/Pillow/issues/6342) - Image.verify() limitations for corruption detection
- [piexif samples](https://piexif.readthedocs.io/en/latest/sample.html) - Usage with Pillow save

### Tertiary (LOW confidence)
- [piexif Snyk health analysis](https://snyk.io/advisor/python/piexif) - Maintenance status: Inactive. Functional but no updates.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are well-established, widely used, and verified via official docs
- Architecture: HIGH - Standard Python module patterns, no complex frameworks needed
- Pitfalls: HIGH - Based on official docs, known Pillow behavior, and verified library limitations
- Metadata embedding specifics: MEDIUM - WebP XMP format string and GIF comment support need testing to confirm exact behavior

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain, libraries change slowly)
