"""Tests for lib/bulk_prompter.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.bulk_prompter import generate_variants, ALL_STRATEGIES


class TestGenerateVariants:
    def test_produces_correct_count(self):
        variants = generate_variants("a beautiful sunset", num_variants=5, seed=42)
        assert len(variants) == 5

    def test_all_variants_unique(self):
        variants = generate_variants("a beautiful sunset over calm ocean waves",
                                     num_variants=10, seed=42)
        prompts = [v["prompt"] for v in variants]
        assert len(set(prompts)) == len(prompts)

    def test_each_variant_has_strategy(self):
        variants = generate_variants("a sunset", num_variants=5, seed=42)
        for v in variants:
            assert "strategy" in v
            assert v["strategy"] in ALL_STRATEGIES

    def test_each_variant_has_index(self):
        variants = generate_variants("a sunset", num_variants=3, seed=42)
        for i, v in enumerate(variants):
            assert v["variant_index"] == i

    def test_seed_produces_reproducible_results(self):
        v1 = generate_variants("a sunset", num_variants=5, seed=42)
        v2 = generate_variants("a sunset", num_variants=5, seed=42)
        assert [v["prompt"] for v in v1] == [v["prompt"] for v in v2]

    def test_different_seeds_produce_different_results(self):
        v1 = generate_variants("a sunset", num_variants=5, seed=42)
        v2 = generate_variants("a sunset", num_variants=5, seed=99)
        assert [v["prompt"] for v in v1] != [v["prompt"] for v in v2]


class TestStrategies:
    def test_all_six_strategies_exist(self):
        assert len(ALL_STRATEGIES) == 6
        assert "synonym_swap" in ALL_STRATEGIES
        assert "detail_injection" in ALL_STRATEGIES
        assert "style_shuffle" in ALL_STRATEGIES
        assert "weight_jitter" in ALL_STRATEGIES
        assert "reorder" in ALL_STRATEGIES
        assert "template_fill" in ALL_STRATEGIES

    def test_single_strategy_filter(self):
        variants = generate_variants(
            "a beautiful sunset over calm ocean waves, cinematic lighting",
            num_variants=3,
            strategies=["synonym_swap"],
            seed=42,
        )
        for v in variants:
            assert v["strategy"] == "synonym_swap"

    def test_detail_injection_appends(self):
        variants = generate_variants(
            "a sunset",
            num_variants=3,
            strategies=["detail_injection"],
            seed=42,
        )
        for v in variants:
            assert len(v["prompt"]) > len("a sunset")

    def test_weight_jitter_adds_weights(self):
        variants = generate_variants(
            "a sunset, golden light, calm waves",
            num_variants=5,
            strategies=["weight_jitter"],
            seed=42,
        )
        weighted = [v for v in variants if ":" in v["prompt"]]
        assert len(weighted) > 0

    def test_reorder_preserves_first_clause(self):
        base = "a sunset, golden light, calm waves, cinematic"
        variants = generate_variants(
            base,
            num_variants=5,
            strategies=["reorder"],
            seed=42,
        )
        for v in variants:
            assert v["prompt"].startswith("a sunset")

    def test_template_fill_replaces_wildcards(self):
        variants = generate_variants(
            "a {mood} sunset, {style}",
            num_variants=3,
            strategies=["template_fill"],
            seed=42,
        )
        for v in variants:
            assert "{mood}" not in v["prompt"]
            assert "{style}" not in v["prompt"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
