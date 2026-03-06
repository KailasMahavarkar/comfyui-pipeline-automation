"""Thread-safe CSV manifest writer for tracking all outputs."""

import csv
import os
import threading

MANIFEST_HEADERS = [
    "topic", "resolution", "variant_index", "filename", "path", "tags", "saved_at"
]

_write_lock = threading.Lock()


def append_manifest(manifest_path: str, row: dict):
    """Append a single row to the manifest CSV. Creates file with header if needed.

    Args:
        manifest_path: Path to manifest.csv.
        row: Dict with keys matching MANIFEST_HEADERS.
    """
    with _write_lock:
        file_exists = os.path.exists(manifest_path)
        os.makedirs(os.path.dirname(manifest_path) or ".", exist_ok=True)

        with open(manifest_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_HEADERS, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)


def read_manifest(manifest_path: str) -> list[dict]:
    """Read all rows from a manifest CSV."""
    if not os.path.exists(manifest_path):
        return []

    with open(manifest_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)
