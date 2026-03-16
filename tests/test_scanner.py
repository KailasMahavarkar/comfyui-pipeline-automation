"""Tests for lib/scanner.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PIL import Image
from lib.scanner import GapScanner


@pytest.fixture
def scanner(tmp_path):
    return GapScanner(str(tmp_path), "test_workflow")


@pytest.fixture
def small_matrix(scanner):
    return scanner.build_matrix(
        topics=["cat", "dog"],
        resolutions=["512x512", "768x768"],
        prompts_per_topic=2,
    )


class TestBuildMatrix:
    def test_correct_size(self, scanner):
        matrix = scanner.build_matrix(["a", "b"], ["512x512"], 3)
        assert len(matrix) == 2 * 1 * 3  # 2 topics * 1 res * 3 prompts

    def test_entry_has_all_fields(self, scanner):
        matrix = scanner.build_matrix(["cat"], ["512x512"], 1)
        entry = matrix[0]
        assert "topic" in entry
        assert "resolution" in entry
        assert "width" in entry
        assert "height" in entry
        assert "variant_index" in entry
        assert "filename" in entry
        assert "path" in entry

    def test_resolution_parsing(self, scanner):
        matrix = scanner.build_matrix(["a"], ["1024x576"], 1)
        assert matrix[0]["width"] == 1024
        assert matrix[0]["height"] == 576


class TestGapDetection:
    def test_all_missing_initially(self, scanner, small_matrix):
        gaps = scanner.find_gaps(small_matrix)
        assert len(gaps) == len(small_matrix)

    def test_first_gap(self, scanner, small_matrix):
        gap = scanner.find_first_gap(small_matrix)
        assert gap is not None
        assert gap["topic"] == "cat"

    def test_no_gaps_when_complete(self, scanner, small_matrix, tmp_path):
        # Create 2 files per topic/resolution directory (prompts_per_topic=2)
        for topic in ["cat", "dog"]:
            for res in ["512x512", "768x768"]:
                d = tmp_path / "test_workflow" / topic / res
                os.makedirs(d, exist_ok=True)
                for i in range(2):
                    Image.new("RGB", (64, 64)).save(str(d / f"img_{i}.png"), format="PNG")

        scanner.invalidate_cache()
        gap = scanner.find_first_gap(small_matrix)
        assert gap is None

    def test_partial_fills_show_remaining_gaps(self, scanner, small_matrix, tmp_path):
        # Create 1 file for cat/512x512 (needs 2)
        d = tmp_path / "test_workflow" / "cat" / "512x512"
        os.makedirs(d, exist_ok=True)
        Image.new("RGB", (64, 64)).save(str(d / "img_0.png"), format="PNG")

        scanner.invalidate_cache()
        gaps = scanner.find_gaps(small_matrix)
        # 1 of 2 filled for cat/512x512, rest all missing
        # total = 8, filled = 1, gaps = 7
        assert len(gaps) == 7

    def test_skipped_paths_excluded(self, scanner, small_matrix):
        skipped = {"cat/512x512"}
        gaps = scanner.find_gaps(small_matrix, skipped=skipped)
        # 2 entries for cat/512x512 skipped
        assert len(gaps) == len(small_matrix) - 2

    def test_invalidate_cache_forces_rescan(self, scanner, small_matrix, tmp_path):
        # First scan: 0 files
        gaps_before = scanner.find_gaps(small_matrix)
        assert len(gaps_before) == len(small_matrix)

        # Create files
        for topic in ["cat", "dog"]:
            for res in ["512x512", "768x768"]:
                d = tmp_path / "test_workflow" / topic / res
                os.makedirs(d, exist_ok=True)
                for i in range(2):
                    Image.new("RGB", (64, 64)).save(str(d / f"img_{i}.png"), format="PNG")

        # Without invalidation, cache returns stale result
        gaps_stale = scanner.find_gaps(small_matrix)
        assert len(gaps_stale) == len(small_matrix)

        # After invalidation, sees new files
        scanner.invalidate_cache()
        gaps_fresh = scanner.find_gaps(small_matrix)
        assert len(gaps_fresh) == 0


class TestIntegrityChecks:
    def test_valid_png_passes(self, tmp_path):
        import numpy as np
        scanner = GapScanner(str(tmp_path), "w")
        path = str(tmp_path / "test.png")
        # Use random pixels so PNG doesn't compress below 1KB
        arr = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
        Image.fromarray(arr).save(path, format="PNG")
        assert scanner.check_integrity(path, "png") is True

    def test_zero_byte_fails(self, tmp_path):
        scanner = GapScanner(str(tmp_path), "w")
        path = str(tmp_path / "empty.png")
        with open(path, "wb") as f:
            f.write(b"")
        assert scanner.check_integrity(path, "png") is False

    def test_small_file_fails(self, tmp_path):
        scanner = GapScanner(str(tmp_path), "w")
        path = str(tmp_path / "small.png")
        with open(path, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 10)
        assert scanner.check_integrity(path, "png") is False

    def test_wrong_header_fails(self, tmp_path):
        scanner = GapScanner(str(tmp_path), "w")
        path = str(tmp_path / "fake.png")
        with open(path, "wb") as f:
            f.write(b'\xff\xd8' + b'\x00' * 2000)  # JPEG header in .png
        assert scanner.check_integrity(path, "png") is False

    def test_valid_jpeg_passes(self, tmp_path):
        scanner = GapScanner(str(tmp_path), "w")
        path = str(tmp_path / "test.jpg")
        Image.new("RGB", (256, 256)).save(path, format="JPEG")
        assert scanner.check_integrity(path, "jpeg") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
