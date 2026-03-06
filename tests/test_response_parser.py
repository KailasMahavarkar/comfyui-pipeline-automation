"""Tests for lib/response_parser.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.response_parser import walk_dot_path, strip_code_blocks, auto_parse_json, extract_mappings


class TestStripCodeBlocks:
    def test_strips_json_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert strip_code_blocks(text) == '{"key": "value"}'

    def test_strips_plain_block(self):
        text = '```\n{"key": "value"}\n```'
        assert strip_code_blocks(text) == '{"key": "value"}'

    def test_no_block_returns_original(self):
        text = '{"key": "value"}'
        assert strip_code_blocks(text) == text


class TestAutoParseJson:
    def test_parses_json_string(self):
        result = auto_parse_json('{"a": 1}')
        assert result == {"a": 1}

    def test_parses_code_block(self):
        result = auto_parse_json('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_non_json_returns_string(self):
        result = auto_parse_json("hello world")
        assert result == "hello world"


class TestWalkDotPath:
    def test_simple_path(self):
        data = {"a": {"b": "value"}}
        assert walk_dot_path(data, "a.b") == "value"

    def test_array_index(self):
        data = {"choices": [{"message": "hello"}]}
        assert walk_dot_path(data, "choices.0.message") == "hello"

    def test_deep_openai_path(self):
        data = {
            "choices": [
                {"message": {"content": '{"prompt": "a sunset"}'}}
            ]
        }
        result = walk_dot_path(data, "choices.0.message.content.prompt")
        assert result == "a sunset"

    def test_missing_path_returns_none(self):
        assert walk_dot_path({"a": 1}, "b.c") is None

    def test_auto_parses_stringified_json(self):
        data = {"result": '{"nested": "value"}'}
        result = walk_dot_path(data, "result.nested")
        assert result == "value"


class TestExtractMappings:
    def test_extracts_multiple(self):
        data = {"a": {"x": 1}, "b": "hello"}
        mapping = "first=a.x\nsecond=b"
        result = extract_mappings(data, mapping)
        assert result["first"] == 1
        assert result["second"] == "hello"

    def test_skips_invalid_lines(self):
        data = {"a": 1}
        mapping = "key=a\n\n# comment\nbad line"
        result = extract_mappings(data, mapping)
        assert result == {"key": 1}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
