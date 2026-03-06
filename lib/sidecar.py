"""JSON sidecar writer — writes metadata alongside output files."""

import json
import os


def write_sidecar(media_path: str, metadata: dict, extra: dict | None = None):
    """Write a .json sidecar file next to the media file.

    Args:
        media_path: Path to the saved media file (e.g., image.png).
        metadata: The metadata dict from Pipeline Controller.
        extra: Optional extra fields to merge (e.g., file info).
    """
    base, _ = os.path.splitext(media_path)
    sidecar_path = base + ".json"

    data = dict(metadata)
    if extra:
        data.update(extra)

    os.makedirs(os.path.dirname(sidecar_path) or ".", exist_ok=True)

    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return sidecar_path


def read_sidecar(media_path: str) -> dict | None:
    """Read the sidecar JSON for a media file, if it exists."""
    base, _ = os.path.splitext(media_path)
    sidecar_path = base + ".json"

    if not os.path.exists(sidecar_path):
        return None

    with open(sidecar_path, "r", encoding="utf-8") as f:
        return json.load(f)
