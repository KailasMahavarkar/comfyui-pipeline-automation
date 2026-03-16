"""Tests for lib/prompt_mutations — generate_variants, generate_variants_via_llm, parse_prompt_list."""

import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.prompt_mutations import generate_variants, generate_variants_via_llm, parse_prompt_list, ALL_STRATEGIES


# ---------------------------------------------------------------------------
# generate_variants (mutation-based)
# ---------------------------------------------------------------------------

class TestGenerateVariants:
    def test_returns_requested_count(self):
        variants = generate_variants("a beautiful sunset, highly detailed", num_variants=10)
        assert len(variants) == 10

    def test_all_unique(self):
        variants = generate_variants("a beautiful sunset, highly detailed", num_variants=20)
        prompts = [v["prompt"] for v in variants]
        assert len(set(prompts)) == len(prompts)

    def test_output_shape(self):
        variants = generate_variants("a cat on a rooftop", num_variants=5)
        for i, v in enumerate(variants):
            assert "prompt" in v
            assert "strategy" in v
            assert "variant_index" in v
            assert v["strategy"] in ALL_STRATEGIES
            assert v["variant_index"] == i

    def test_strategy_names_are_valid(self):
        variants = generate_variants("a forest scene, dark", num_variants=30)
        for v in variants:
            assert v["strategy"] in ALL_STRATEGIES

    def test_seed_produces_deterministic_output(self):
        a = generate_variants("a mountain lake", num_variants=10, seed=42)
        b = generate_variants("a mountain lake", num_variants=10, seed=42)
        assert [v["prompt"] for v in a] == [v["prompt"] for v in b]

    def test_different_seeds_differ(self):
        a = generate_variants("a mountain lake", num_variants=10, seed=1)
        b = generate_variants("a mountain lake", num_variants=10, seed=2)
        assert [v["prompt"] for v in a] != [v["prompt"] for v in b]


# ---------------------------------------------------------------------------
# generate_variants_via_llm
# ---------------------------------------------------------------------------

LLM_CONFIG = {
    "api_url": "http://localhost:1234/v1/chat/completions",
    "api_key": "test-key",
    "model": "test-model",
    "temperature": 0.7,
}


def _mock_llm_response(prompts: list[str]):
    """Build a mock urllib response returning a JSON array of prompts."""
    content = json.dumps(prompts)
    response_body = json.dumps({
        "choices": [{"message": {"content": content}}]
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestGenerateVariantsViaLLM:
    def test_returns_variants_on_success(self):
        prompts = [f"prompt variant {i}" for i in range(5)]
        with patch("urllib.request.urlopen", return_value=_mock_llm_response(prompts)):
            variants = generate_variants_via_llm("base prompt", 5, "sunset", LLM_CONFIG)
        assert len(variants) == 5
        assert all(v["strategy"] == "llm" for v in variants)
        assert [v["prompt"] for v in variants] == prompts

    def test_variant_index_is_sequential(self):
        prompts = ["a", "b", "c"]
        with patch("urllib.request.urlopen", return_value=_mock_llm_response(prompts)):
            variants = generate_variants_via_llm("base", 3, "topic", LLM_CONFIG)
        assert [v["variant_index"] for v in variants] == [0, 1, 2]

    def test_returns_empty_on_network_error(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            variants = generate_variants_via_llm("base", 5, "topic", LLM_CONFIG)
        assert variants == []

    def test_returns_empty_when_no_api_url(self):
        variants = generate_variants_via_llm("base", 5, "topic", {"api_url": ""})
        assert variants == []

    def test_returns_empty_on_non_array_response(self):
        bad_body = json.dumps({
            "choices": [{"message": {"content": '{"error": "oops"}'}}]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = bad_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            variants = generate_variants_via_llm("base", 5, "topic", LLM_CONFIG)
        assert variants == []

    def test_filters_empty_strings(self):
        prompts = ["valid prompt", "", "  ", "another valid"]
        with patch("urllib.request.urlopen", return_value=_mock_llm_response(prompts)):
            variants = generate_variants_via_llm("base", 4, "topic", LLM_CONFIG)
        assert len(variants) == 2
        assert variants[0]["prompt"] == "valid prompt"
        assert variants[1]["prompt"] == "another valid"


# ---------------------------------------------------------------------------
# parse_prompt_list
# ---------------------------------------------------------------------------

class TestParsePromptList:
    def test_parses_newline_separated(self):
        result = parse_prompt_list("prompt one\nprompt two\nprompt three")
        assert len(result) == 3
        assert result[0]["prompt"] == "prompt one"
        assert result[2]["prompt"] == "prompt three"

    def test_parses_json_array(self):
        result = parse_prompt_list('["a cat", "a dog", "a bird"]')
        assert len(result) == 3
        assert result[1]["prompt"] == "a dog"

    def test_strategy_is_custom_list(self):
        result = parse_prompt_list("only one prompt")
        assert result[0]["strategy"] == "custom_list"

    def test_variant_index_is_sequential(self):
        result = parse_prompt_list("a\nb\nc")
        assert [v["variant_index"] for v in result] == [0, 1, 2]

    def test_ignores_empty_lines(self):
        result = parse_prompt_list("a\n\n  \nb")
        assert len(result) == 2

    def test_empty_input_returns_empty(self):
        assert parse_prompt_list("") == []
        assert parse_prompt_list("   ") == []

    def test_json_array_with_whitespace(self):
        result = parse_prompt_list('[ "  trimmed  ", "normal" ]')
        assert result[0]["prompt"] == "trimmed"
