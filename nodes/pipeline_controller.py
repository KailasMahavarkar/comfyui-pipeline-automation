"""Pipeline Controller node — the brain of the automated pipeline.

Scans filesystem for gaps, generates prompts and tags for new topics,
outputs parameters for the next missing entry.
"""

import json
import os
import re
import logging
from datetime import datetime

from ..lib.scanner import GapScanner
from ..lib.fingerprint import compute_fingerprint, check_collision, save_fingerprint
from ..lib.bulk_prompter import generate_variants
from ..lib.tag_generator import generate_tags, flatten_tags
from ..lib.naming import resolve_template

logger = logging.getLogger(__name__)

# Module-level cache for scanner instances (persists across runs)
_scanners: dict[str, GapScanner] = {}


def _sanitize_name(name: str) -> str:
    """Convert workflow name to filesystem-safe string."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('._').lower()


def _load_prompt_cache(cache_dir: str, topic: str) -> dict | None:
    """Load cached prompts + tags for a topic."""
    path = os.path.join(cache_dir, f"{_sanitize_name(topic)}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_prompt_cache(cache_dir: str, topic: str, data: dict):
    """Save prompts + tags cache for a topic."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{_sanitize_name(topic)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_failures(workflow_dir: str) -> dict:
    """Load strike counter data."""
    path = os.path.join(workflow_dir, ".failures.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _get_skipped_paths(failures: dict) -> set[str]:
    """Get paths that have been skipped due to repeated failures."""
    return {path for path, data in failures.items() if data.get("skipped", False)}


class PipelineController:
    """Filesystem scanning, prompt generation, tag generation, orchestration."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT", "STRING", "BOOLEAN", "STRING")
    RETURN_NAMES = ("prompt", "negative_prompt", "width", "height", "metadata", "is_complete", "status")
    FUNCTION = "process"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "workflow_name": ("STRING", {"default": ""}),
                "topic_list": ("STRING", {"multiline": True}),
                "resolution_list": ("STRING", {"multiline": True, "default": "512x512"}),
                "prompts_per_topic": ("INT", {"default": 50, "min": 1, "max": 10000}),
                "base_prompt_template": ("STRING", {"multiline": True, "default": "a beautiful {topic}, highly detailed"}),
                "base_negative_prompt": ("STRING", {"multiline": True, "default": "blurry, watermark, text, low quality"}),
                "queue_order": (["sequential", "interleaved", "shuffled"],),
            },
            "optional": {
                "vary_negative": ("BOOLEAN", {"default": False}),
                "generate_tags_via_llm": ("BOOLEAN", {"default": False}),
                "llm_config": ("STRING", {"default": ""}),
                "custom_word_bank_path": ("STRING", {"default": ""}),
                "topic_tag_bank": ("STRING", {"multiline": True, "default": ""}),
                "reset_workflow": ("BOOLEAN", {"default": False}),
                "output_dir": ("STRING", {"default": "output"}),
                "format": ("STRING", {"default": "png"}),
            },
        }

    def process(self, workflow_name, topic_list, resolution_list,
                prompts_per_topic, base_prompt_template, base_negative_prompt,
                queue_order, vary_negative=False, generate_tags_via_llm=False,
                llm_config="", custom_word_bank_path="", topic_tag_bank="",
                reset_workflow=False, output_dir="output", format="png"):

        if not workflow_name:
            return ("", "", 512, 512, "{}", False, "ERROR: workflow_name is required")

        workflow_name = _sanitize_name(workflow_name)

        # Parse inputs
        topics = [t.strip() for t in topic_list.strip().splitlines() if t.strip()]
        resolutions = [r.strip() for r in resolution_list.strip().splitlines() if r.strip()]

        if not topics:
            return ("", "", 512, 512, "{}", True, "ERROR: No topics provided")
        if not resolutions:
            return ("", "", 512, 512, "{}", True, "ERROR: No resolutions provided")

        workflow_dir = os.path.join(output_dir, workflow_name)
        cache_dir = os.path.join(workflow_dir, ".prompt_cache")

        # Handle reset
        if reset_workflow and os.path.exists(workflow_dir):
            import shutil
            shutil.rmtree(workflow_dir)
            if workflow_name in _scanners:
                del _scanners[workflow_name]

        # Get or create scanner
        if workflow_name not in _scanners:
            _scanners[workflow_name] = GapScanner(output_dir, workflow_name)
        scanner = _scanners[workflow_name]

        # Load failures / skipped
        failures = _load_failures(workflow_dir)
        skipped = _get_skipped_paths(failures)

        # Build matrix
        sanitized_topics = [_sanitize_name(t) for t in topics]
        matrix = scanner.build_matrix(sanitized_topics, resolutions, prompts_per_topic)

        # Find first gap
        gap = scanner.find_first_gap(matrix, format, skipped)

        if gap is None:
            total = len(matrix)
            status = f"{workflow_name} | COMPLETE | {total}/{total} (100%)"
            return ("", base_negative_prompt, 512, 512, "{}", True, status)

        # Get topic info
        topic = gap["topic"]
        resolution = gap["resolution"]
        width = gap["width"]
        height = gap["height"]
        variant_index = gap["variant_index"]

        # Find original topic name (pre-sanitized)
        topic_idx = sanitized_topics.index(topic) if topic in sanitized_topics else 0
        original_topic = topics[topic_idx] if topic_idx < len(topics) else topic

        # Generate or load cached prompts
        cached = _load_prompt_cache(cache_dir, topic)
        if cached is None:
            # Generate prompt variants
            resolved_base = base_prompt_template.replace("{topic}", original_topic)
            variants = generate_variants(
                base_prompt=resolved_base,
                num_variants=prompts_per_topic,
                custom_word_bank_path=custom_word_bank_path or None,
            )

            # Generate tags
            llm_cfg = None
            if generate_tags_via_llm and llm_config:
                try:
                    llm_cfg = json.loads(llm_config)
                except json.JSONDecodeError:
                    pass

            tags, tag_sources = generate_tags(
                topic=original_topic,
                base_prompt=resolved_base,
                resolution=resolution,
                topic_tag_bank=topic_tag_bank or None,
                llm_config=llm_cfg,
            )

            cached = {
                "topic": original_topic,
                "base_prompt": resolved_base,
                "variants": variants,
                "tags": tags,
                "tag_sources": tag_sources,
            }
            _save_prompt_cache(cache_dir, topic, cached)

        # Get the variant for the current gap
        variants = cached.get("variants", [])
        if variant_index < len(variants):
            variant = variants[variant_index]
            prompt = variant["prompt"]
            strategy = variant.get("strategy", "unknown")
        else:
            # Fallback if fewer variants than expected
            prompt = base_prompt_template.replace("{topic}", original_topic)
            strategy = "fallback"

        # Build metadata output
        total = len(matrix)
        existing = total - len(scanner.find_gaps(matrix, format, skipped))
        global_index = existing + 1

        metadata_dict = {
            "prompt": prompt,
            "negative_prompt": base_negative_prompt,
            "tags": cached.get("tags", {}),
            "tag_sources": cached.get("tag_sources", {}),
            "pipeline": {
                "workflow_name": workflow_name,
                "topic": topic,
                "variant_index": variant_index,
                "variant_strategy": strategy,
                "total_variants": prompts_per_topic,
                "global_index": global_index,
                "global_total": total,
            },
        }

        # Build status string
        topic_idx_display = sanitized_topics.index(topic) + 1 if topic in sanitized_topics else 0
        pct = (global_index / total * 100) if total > 0 else 0
        status = (
            f"{workflow_name} | topic {topic_idx_display}/{len(topics)} ({original_topic}) | "
            f"prompt {variant_index + 1}/{prompts_per_topic} | "
            f"res {resolutions.index(resolution) + 1}/{len(resolutions)} | "
            f"global {global_index:,}/{total:,} ({pct:.1f}%) | "
            f"{len(skipped)} skipped"
        )

        metadata_json = json.dumps(metadata_dict, ensure_ascii=False)

        return (prompt, base_negative_prompt, width, height, metadata_json, False, status)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Return unique value each time to force re-execution
        return float("nan")
