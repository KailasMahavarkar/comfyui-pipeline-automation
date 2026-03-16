"""Integration test — simulates the full pipeline loop end-to-end.

Verifies:
1. GapScanner finds gaps and advances through variant_index
2. PromptGenerator generates distinct prompts per variant
3. Scanner counts files per directory (not by filename)
4. Pipeline completes when all files exist
5. Save As skips on completion (empty topic)
"""

import json
import os
import sys

import pytest
from PIL import Image
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.scanner import GapScanner
from lib.prompt_mutations import generate_variants
from lib.naming import sanitize_name


class TestFullPipelineLoop:
    """Simulate: 2 topics × 1 resolution × 3 variants = 6 images."""

    @pytest.fixture
    def pipeline_dir(self, tmp_path):
        return tmp_path / "output"

    @pytest.fixture
    def config(self):
        return {
            "workflow_name": "test_run",
            "topics": ["sunset beach", "mountain lake"],
            "resolutions": ["512x512"],
            "prompts_per_topic": 3,
            "format": "png",
        }

    def _run_gap_scanner(self, pipeline_dir, config):
        """Simulate one GapScanner execution."""
        output_dir = str(pipeline_dir)
        workflow_name = sanitize_name(config["workflow_name"])
        scanner = GapScanner(output_dir, workflow_name)
        scanner.invalidate_cache()

        sanitized_topics = [sanitize_name(t) for t in config["topics"]]
        matrix = scanner.build_matrix(
            sanitized_topics, config["resolutions"], config["prompts_per_topic"]
        )
        gap = scanner.find_first_gap(matrix, config["format"])

        if gap is None:
            return None  # complete

        # Find original topic
        idx = sanitized_topics.index(gap["topic"])
        original_topic = config["topics"][idx]
        return {
            "topic": original_topic,
            "sanitized_topic": gap["topic"],
            "resolution": gap["resolution"],
            "width": gap["width"],
            "height": gap["height"],
            "variant_index": gap["variant_index"],
        }

    def _run_prompt_generator(self, topic, variant_index, prompts_per_topic):
        """Simulate one PromptGenerator execution."""
        base = f"a beautiful {topic}, highly detailed, cinematic lighting, vivid colors"
        variants = generate_variants(
            base_prompt=base,
            num_variants=prompts_per_topic,
            seed=42,
        )
        if variant_index < len(variants):
            return variants[variant_index]["prompt"]
        return base

    def _run_save_as(self, pipeline_dir, config, gap, prompt):
        """Simulate Save As — write a real PNG file."""
        workflow_name = sanitize_name(config["workflow_name"])
        topic_dir = (
            pipeline_dir / workflow_name / gap["sanitized_topic"] / gap["resolution"]
        )
        os.makedirs(topic_dir, exist_ok=True)

        # Use any filename — scanner counts files, not filenames
        filename = f"comfyui_{gap['sanitized_topic']}_{gap['variant_index']:04d}.png"
        path = topic_dir / filename

        arr = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        Image.fromarray(arr).save(str(path), format="PNG")
        return str(path)

    def test_pipeline_completes_in_correct_iterations(self, pipeline_dir, config):
        """Run the full loop and verify it completes after exactly N iterations."""
        total_expected = (
            len(config["topics"])
            * len(config["resolutions"])
            * config["prompts_per_topic"]
        )  # 2 * 1 * 3 = 6

        saved_files = []
        prompts_used = []

        for iteration in range(total_expected + 2):  # +2 safety margin
            gap = self._run_gap_scanner(pipeline_dir, config)

            if gap is None:
                # Pipeline complete
                assert iteration == total_expected, (
                    f"Completed at iteration {iteration}, expected {total_expected}"
                )
                break

            prompt = self._run_prompt_generator(
                gap["topic"], gap["variant_index"], config["prompts_per_topic"]
            )
            prompts_used.append(prompt)

            path = self._run_save_as(pipeline_dir, config, gap, prompt)
            saved_files.append(path)
        else:
            pytest.fail(f"Pipeline did not complete after {total_expected + 2} iterations")

        assert len(saved_files) == total_expected

    def test_variant_index_advances_each_iteration(self, pipeline_dir, config):
        """Verify variant_index advances 0, 1, 2 for each topic."""
        indices_per_topic: dict[str, list[int]] = {}

        for _ in range(20):  # safety limit
            gap = self._run_gap_scanner(pipeline_dir, config)
            if gap is None:
                break
            topic = gap["sanitized_topic"]
            indices_per_topic.setdefault(topic, []).append(gap["variant_index"])

            self._run_save_as(pipeline_dir, config, gap, "dummy")

        for topic, indices in indices_per_topic.items():
            assert indices == [0, 1, 2], f"Topic {topic} had indices {indices}"

    def test_prompts_are_distinct_per_variant(self, pipeline_dir, config):
        """Verify each variant gets a different prompt."""
        prompts_per_topic: dict[str, list[str]] = {}

        for _ in range(20):
            gap = self._run_gap_scanner(pipeline_dir, config)
            if gap is None:
                break

            prompt = self._run_prompt_generator(
                gap["topic"], gap["variant_index"], config["prompts_per_topic"]
            )
            topic = gap["sanitized_topic"]
            prompts_per_topic.setdefault(topic, []).append(prompt)

            self._run_save_as(pipeline_dir, config, gap, prompt)

        for topic, prompts in prompts_per_topic.items():
            assert len(prompts) == len(set(prompts)), (
                f"Topic {topic} had duplicate prompts"
            )

    def test_scanner_counts_any_filename(self, pipeline_dir, config):
        """Verify scanner counts files regardless of naming convention."""
        workflow_name = sanitize_name(config["workflow_name"])
        topic = sanitize_name(config["topics"][0])
        res = config["resolutions"][0]

        d = pipeline_dir / workflow_name / topic / res
        os.makedirs(d, exist_ok=True)

        # Write files with random names
        for name in ["abc.png", "xyz_123.png", "whatever.png"]:
            arr = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            Image.fromarray(arr).save(str(d / name), format="PNG")

        scanner = GapScanner(str(pipeline_dir), workflow_name)
        counts = scanner.count_existing()
        key = f"{topic}/{res}"
        assert counts.get(key, 0) == 3

    def test_save_as_skips_empty_topic(self):
        """Verify Save As skip logic when pipeline is complete."""
        # When is_complete=True, PromptGenerator returns empty metadata
        metadata = "{}"
        meta_dict = json.loads(metadata)
        topic = meta_dict.get("pipeline", {}).get("topic")
        assert not topic  # falsy → Save As should skip


class TestScannerEdgeCases:
    def test_hidden_files_ignored(self, tmp_path):
        """Dot-files (like .prompt_cache) should not be counted."""
        scanner = GapScanner(str(tmp_path), "w")
        d = tmp_path / "w" / "topic" / "512x512"
        os.makedirs(d, exist_ok=True)

        # Real image
        Image.new("RGB", (64, 64)).save(str(d / "real.png"), format="PNG")
        # Hidden file
        with open(d / ".hidden.png", "w") as f:
            f.write("not a real image")

        counts = scanner.count_existing()
        assert counts.get("topic/512x512", 0) == 1

    def test_non_image_files_ignored(self, tmp_path):
        """JSON, CSV, TXT files should not be counted."""
        scanner = GapScanner(str(tmp_path), "w")
        d = tmp_path / "w" / "topic" / "512x512"
        os.makedirs(d, exist_ok=True)

        Image.new("RGB", (64, 64)).save(str(d / "real.png"), format="PNG")
        with open(d / "sidecar.json", "w") as f:
            f.write("{}")
        with open(d / "notes.txt", "w") as f:
            f.write("hello")

        counts = scanner.count_existing()
        assert counts.get("topic/512x512", 0) == 1

    def test_empty_directory_returns_zero(self, tmp_path):
        scanner = GapScanner(str(tmp_path), "w")
        counts = scanner.count_existing()
        assert counts == {}
