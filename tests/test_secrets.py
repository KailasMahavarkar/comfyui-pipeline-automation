"""Tests for lib/secrets.py"""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.secrets import get_api_key, clear_cache


class TestGetApiKey:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        clear_cache()
        yield
        clear_cache()

    def test_key_found(self, tmp_path, monkeypatch):
        key_file = tmp_path / "api_keys.json"
        key_file.write_text(json.dumps({"openrouter": "sk-or-abc123"}))
        monkeypatch.setattr("lib.secrets._KEY_FILE", str(key_file))

        assert get_api_key("openrouter") == "sk-or-abc123"

    def test_key_not_found(self, tmp_path, monkeypatch):
        key_file = tmp_path / "api_keys.json"
        key_file.write_text(json.dumps({"openrouter": "sk-or-abc123"}))
        monkeypatch.setattr("lib.secrets._KEY_FILE", str(key_file))

        assert get_api_key("nonexistent") == ""

    def test_file_missing(self, monkeypatch):
        monkeypatch.setattr("lib.secrets._KEY_FILE", "/nonexistent/path.json")
        assert get_api_key("anything") == ""

    def test_invalid_json(self, tmp_path, monkeypatch):
        key_file = tmp_path / "api_keys.json"
        key_file.write_text("not valid json {{{")
        monkeypatch.setattr("lib.secrets._KEY_FILE", str(key_file))

        assert get_api_key("anything") == ""

    def test_empty_name_returns_empty(self, tmp_path, monkeypatch):
        key_file = tmp_path / "api_keys.json"
        key_file.write_text(json.dumps({"openrouter": "sk-or-abc123"}))
        monkeypatch.setattr("lib.secrets._KEY_FILE", str(key_file))

        assert get_api_key("") == ""
        assert get_api_key("  ") == ""

    def test_mtime_cache_reloads_on_change(self, tmp_path, monkeypatch):
        key_file = tmp_path / "api_keys.json"
        key_file.write_text(json.dumps({"k": "v1"}))
        monkeypatch.setattr("lib.secrets._KEY_FILE", str(key_file))

        assert get_api_key("k") == "v1"

        # Overwrite with new content and force mtime change
        key_file.write_text(json.dumps({"k": "v2"}))
        os.utime(str(key_file), (9999999999, 9999999999))

        assert get_api_key("k") == "v2"

    def test_non_dict_json_returns_empty(self, tmp_path, monkeypatch):
        key_file = tmp_path / "api_keys.json"
        key_file.write_text(json.dumps(["not", "a", "dict"]))
        monkeypatch.setattr("lib.secrets._KEY_FILE", str(key_file))

        assert get_api_key("anything") == ""



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
