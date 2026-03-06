"""Tests for lib/sidecar.py and lib/manifest.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.sidecar import write_sidecar, read_sidecar
from lib.manifest import append_manifest, read_manifest


class TestSidecar:
    def test_write_and_read(self, tmp_path):
        media_path = str(tmp_path / "image.png")
        metadata = {"prompt": "a sunset", "tags": ["sunset", "ocean"]}

        sidecar_path = write_sidecar(media_path, metadata)
        assert os.path.exists(sidecar_path)
        assert sidecar_path.endswith(".json")

        result = read_sidecar(media_path)
        assert result["prompt"] == "a sunset"
        assert result["tags"] == ["sunset", "ocean"]

    def test_extra_fields_merged(self, tmp_path):
        media_path = str(tmp_path / "image.png")
        metadata = {"prompt": "test"}
        extra = {"file": {"filename": "image.png"}}

        write_sidecar(media_path, metadata, extra=extra)
        result = read_sidecar(media_path)
        assert result["file"]["filename"] == "image.png"

    def test_read_nonexistent_returns_none(self, tmp_path):
        assert read_sidecar(str(tmp_path / "nope.png")) is None


class TestManifest:
    def test_creates_with_header(self, tmp_path):
        path = str(tmp_path / "manifest.csv")
        row = {
            "topic": "sunset",
            "resolution": "512x512",
            "variant_index": 1,
            "filename": "sunset_001.png",
            "path": "sunset/512x512/sunset_001.png",
            "tags": "sunset|ocean",
            "saved_at": "2026-03-05T14:30:00",
        }
        append_manifest(path, row)

        rows = read_manifest(path)
        assert len(rows) == 1
        assert rows[0]["topic"] == "sunset"

    def test_appends_multiple_rows(self, tmp_path):
        path = str(tmp_path / "manifest.csv")
        for i in range(5):
            append_manifest(path, {
                "topic": f"topic_{i}",
                "resolution": "512x512",
                "variant_index": i,
                "filename": f"file_{i}.png",
                "path": f"path_{i}",
                "tags": "tag",
                "saved_at": "2026-01-01",
            })

        rows = read_manifest(path)
        assert len(rows) == 5

    def test_read_empty_returns_empty(self, tmp_path):
        assert read_manifest(str(tmp_path / "nope.csv")) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
