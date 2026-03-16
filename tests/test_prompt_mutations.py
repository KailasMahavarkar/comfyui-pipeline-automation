"""Tests for lib/prompt_mutations — generate_variants, parse_prompt_list."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.prompt_mutations import generate_variants, ALL_STRATEGIES


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
