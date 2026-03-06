"""Filesystem gap detection with multi-level integrity checking.

Scans output directory against the planned matrix (topics x resolutions x prompts)
to find missing entries. Supports incremental caching for performance.
"""

import os
import time
import threading
from PIL import Image

# Magic bytes for format validation
FORMAT_HEADERS = {
    "png": b'\x89PNG\r\n\x1a\n',
    "jpeg": b'\xff\xd8',
    "jpg": b'\xff\xd8',
    "webp": None,  # Checked via bytes 8-12
}

RECENT_THRESHOLD_SECONDS = 3600  # 1 hour


class GapScanner:
    """Scans output directory for missing entries in the generation matrix."""

    def __init__(self, output_dir: str, workflow_name: str):
        self.root = os.path.join(output_dir, workflow_name)
        self._cache: set[str] = set()
        self._cache_built = False
        self._lock = threading.Lock()
        self._is_restart = True

    def build_matrix(self, topics: list[str], resolutions: list[str],
                     prompts_per_topic: int, naming_fn=None) -> list[dict]:
        """Build the full planned matrix of expected outputs.

        Args:
            topics: List of topic strings.
            resolutions: List of "WxH" strings.
            prompts_per_topic: Number of prompt variants per topic.
            naming_fn: Optional callable(topic, resolution, variant_index) -> filename.
                       Defaults to "{topic}_{resolution}_{variant:03d}".

        Returns:
            List of dicts with keys: topic, resolution, width, height, variant_index, filename, path.
        """
        matrix = []
        for topic in topics:
            for resolution in resolutions:
                parts = resolution.lower().split("x")
                width = int(parts[0]) if len(parts) == 2 else 0
                height = int(parts[1]) if len(parts) == 2 else 0

                for variant_idx in range(prompts_per_topic):
                    if naming_fn:
                        filename = naming_fn(topic, resolution, variant_idx)
                    else:
                        filename = f"{topic}_{resolution}_{variant_idx + 1:03d}"

                    rel_path = os.path.join(topic, resolution, filename)
                    matrix.append({
                        "topic": topic,
                        "resolution": resolution,
                        "width": width,
                        "height": height,
                        "variant_index": variant_idx,
                        "filename": filename,
                        "path": rel_path,
                    })
        return matrix

    def scan_existing(self, fmt: str = "png") -> set[str]:
        """Scan filesystem for existing files. Returns set of relative paths (without extension)."""
        with self._lock:
            if self._cache_built:
                return set(self._cache)

        existing = set()
        if not os.path.exists(self.root):
            with self._lock:
                self._cache = existing
                self._cache_built = True
            return existing

        for dirpath, _, filenames in os.walk(self.root):
            for fn in filenames:
                if fn.startswith("."):
                    continue
                base, ext = os.path.splitext(fn)
                if ext.lstrip(".").lower() in ("png", "jpeg", "jpg", "webp", "gif"):
                    rel = os.path.relpath(os.path.join(dirpath, base), self.root)
                    existing.add(rel.replace("\\", "/"))

        with self._lock:
            self._cache = existing
            self._cache_built = True
            self._is_restart = False

        return set(existing)

    def find_gaps(self, matrix: list[dict], fmt: str = "png",
                  skipped: set[str] | None = None) -> list[dict]:
        """Find entries in the matrix that don't have corresponding output files.

        Args:
            matrix: The planned matrix from build_matrix().
            fmt: Expected file format extension.
            skipped: Set of paths to skip (from strike counter).

        Returns:
            List of matrix entries that are missing.
        """
        existing = self.scan_existing(fmt)
        skipped = skipped or set()
        gaps = []

        for entry in matrix:
            rel_path = entry["path"].replace("\\", "/")
            if rel_path in skipped:
                continue
            if rel_path not in existing:
                gaps.append(entry)

        return gaps

    def find_first_gap(self, matrix: list[dict], fmt: str = "png",
                       skipped: set[str] | None = None) -> dict | None:
        """Find the first missing entry. Returns None if complete."""
        gaps = self.find_gaps(matrix, fmt, skipped)
        return gaps[0] if gaps else None

    def mark_complete(self, rel_path: str):
        """Mark a path as complete in the cache (after successful save)."""
        with self._lock:
            self._cache.add(rel_path.replace("\\", "/"))

    def invalidate_cache(self):
        """Force a full rescan on next call."""
        with self._lock:
            self._cache.clear()
            self._cache_built = False

    def check_integrity(self, file_path: str, fmt: str = "png") -> bool:
        """Check file integrity. Uses Level 2 by default, Level 3 for recent files on restart."""
        if not os.path.exists(file_path):
            return False

        # Level 2: existence + size + header
        if not self._check_level2(file_path, fmt):
            return False

        # Level 3: full decode for recent files on restart
        if self._is_restart and self._is_recent(file_path):
            return self._check_level3(file_path)

        return True

    def _check_level2(self, file_path: str, fmt: str) -> bool:
        """Level 2: Check existence, minimum size, and format header."""
        try:
            size = os.path.getsize(file_path)
            if size < 1024:  # Must be > 1KB
                return False

            with open(file_path, "rb") as f:
                header = f.read(12)

            fmt = fmt.lower()
            if fmt in ("png",):
                return header[:8] == b'\x89PNG\r\n\x1a\n'
            elif fmt in ("jpeg", "jpg"):
                return header[:2] == b'\xff\xd8'
            elif fmt == "webp":
                return header[8:12] == b'WEBP'
            else:
                return True  # Unknown format, pass if size OK

        except OSError:
            return False

    def _check_level3(self, file_path: str) -> bool:
        """Level 3: Full Pillow decode validation."""
        try:
            img = Image.open(file_path)
            img.load()  # Force full decode
            return True
        except Exception:
            return False

    def _is_recent(self, file_path: str) -> bool:
        """Check if file was modified in the last hour."""
        try:
            mtime = os.path.getmtime(file_path)
            return (time.time() - mtime) < RECENT_THRESHOLD_SECONDS
        except OSError:
            return False
