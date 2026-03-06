"""Tests for lib/naming.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.naming import resolve_template, get_preset_template, resolve_with_preset, reset_counter, PRESET_TEMPLATES


class TestPresets:
    def test_all_four_presets_exist(self):
        assert len(PRESET_TEMPLATES) == 4
        assert "Simple" in PRESET_TEMPLATES
        assert "Detailed" in PRESET_TEMPLATES
        assert "Minimal" in PRESET_TEMPLATES
        assert "Custom" in PRESET_TEMPLATES

    def test_custom_returns_none(self):
        assert get_preset_template("Custom") is None

    def test_presets_have_templates(self):
        for name, tmpl in PRESET_TEMPLATES.items():
            if name != "Custom":
                assert tmpl is not None
                assert "{" in tmpl


class TestResolveTemplate:
    def setup_method(self):
        reset_counter()

    def test_all_eight_tokens_resolve(self):
        context = {
            "prefix": "test",
            "topic": "sunset",
            "width": 512,
            "height": 512,
            "format": "png",
            "batch": 3,
        }
        template = "{prefix}_{topic}_{date}_{time}_{datetime}_{resolution}_{counter}_{batch}_{format}"
        result = resolve_template(template, context)

        assert "test" in result
        assert "sunset" in result
        assert "512x512" in result
        assert "0000" in result  # counter
        assert "0003" in result  # batch
        assert "png" in result
        # date/time tokens are dynamic but should be present (8 digits for date)
        parts = result.split("_")
        assert len(parts) >= 8

    def test_unresolved_token_becomes_unknown(self):
        result = resolve_template("{nonexistent}", {})
        assert result == "unknown"

    def test_counter_increments(self):
        ctx = {"prefix": "a"}
        r1 = resolve_template("{counter}", ctx)
        r2 = resolve_template("{counter}", ctx)
        assert r1 == "0000"
        assert r2 == "0001"

    def test_sanitizes_unsafe_characters(self):
        context = {"topic": 'hello<world>:test"file'}
        result = resolve_template("{topic}", context)
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result

    def test_width_height_tokens(self):
        context = {"width": 1024, "height": 576}
        result = resolve_template("{width}x{height}", context)
        assert result == "1024x576"


class TestResolveWithPreset:
    def setup_method(self):
        reset_counter()

    def test_simple_preset(self):
        result = resolve_with_preset("Simple", None, {"prefix": "img"})
        assert "img" in result

    def test_detailed_preset(self):
        result = resolve_with_preset("Detailed", None, {
            "prefix": "img", "topic": "cat", "width": 512, "height": 512
        })
        assert "img" in result
        assert "cat" in result
        assert "512x512" in result

    def test_custom_preset_uses_template(self):
        result = resolve_with_preset("Custom", "{prefix}_custom", {"prefix": "img"})
        assert "img_custom" == result

    def test_custom_without_template_falls_back(self):
        result = resolve_with_preset("Custom", None, {"prefix": "img"})
        assert "img" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
