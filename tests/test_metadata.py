"""Tests for lib/metadata.py — PNG, JPEG, WebP embed and read-back."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PIL import Image
from lib.metadata import (
    embed_png, read_png, embed_jpeg, read_jpeg,
    embed_webp, read_webp, embed_metadata, read_metadata,
)


@pytest.fixture
def sample_image():
    """Create a small test image."""
    return Image.new("RGB", (64, 64), color=(255, 128, 0))


@pytest.fixture
def sample_metadata():
    return {
        "prompt": "a beautiful sunset over the ocean",
        "tags": ["sunset", "ocean", "cinematic"],
        "pipeline": {"topic": "sunset_beach", "variant_index": 5},
    }


class TestPNG:
    def test_embed_and_read_back(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.png")
        embed_png(sample_image, sample_metadata, path)

        result = read_png(path)
        assert result is not None
        assert result["prompt"] == sample_metadata["prompt"]
        assert result["tags"] == sample_metadata["tags"]

    def test_no_corruption(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.png")
        embed_png(sample_image, sample_metadata, path)

        img = Image.open(path)
        assert img.size == (64, 64)
        assert img.mode == "RGB"

    def test_read_without_metadata_returns_none(self, sample_image, tmp_path):
        path = str(tmp_path / "plain.png")
        sample_image.save(path, format="PNG")
        assert read_png(path) is None


class TestJPEG:
    def test_embed_and_read_back(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.jpg")
        embed_jpeg(sample_image, sample_metadata, path)

        result = read_jpeg(path)
        assert result is not None
        assert result["prompt"] == sample_metadata["prompt"]

    def test_no_corruption(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.jpg")
        embed_jpeg(sample_image, sample_metadata, path)

        img = Image.open(path)
        assert img.size == (64, 64)


class TestWebP:
    def test_embed_and_read_back(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.webp")
        embed_webp(sample_image, sample_metadata, path)

        result = read_webp(path)
        assert result is not None
        assert result["prompt"] == sample_metadata["prompt"]

    def test_no_corruption(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.webp")
        embed_webp(sample_image, sample_metadata, path)

        img = Image.open(path)
        assert img.size == (64, 64)


class TestDispatch:
    def test_embed_metadata_png(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.png")
        embed_metadata(sample_image, sample_metadata, path, fmt="png")
        assert read_metadata(path, fmt="png") is not None

    def test_embed_metadata_jpeg(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.jpg")
        embed_metadata(sample_image, sample_metadata, path, fmt="jpeg")
        assert read_metadata(path, fmt="jpeg") is not None

    def test_embed_metadata_webp(self, sample_image, sample_metadata, tmp_path):
        path = str(tmp_path / "test.webp")
        embed_metadata(sample_image, sample_metadata, path, fmt="webp")
        assert read_metadata(path, fmt="webp") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
