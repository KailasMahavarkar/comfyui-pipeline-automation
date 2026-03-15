"""PromptGenerator node — generates prompt variants with optional LLM tag generation."""

import json
import os

from ..lib.bulk_prompter import generate_variants
from ..lib.tag_generator import generate_tags
from ..lib.naming import sanitize_name

# Module-level cache for generated prompts (persists across runs)
_prompt_cache: dict[str, dict] = {}


def _load_prompt_cache(cache_dir: str, topic: str) -> dict | None:
    """Load cached prompts + tags for a topic from disk."""
    path = os.path.join(cache_dir, f"{sanitize_name(topic)}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_prompt_cache(cache_dir: str, topic: str, data: dict):
    """Save prompts + tags cache for a topic to disk."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{sanitize_name(topic)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class PromptGenerator:
    """Generates prompt variants from a base template + topic, with optional LLM tags."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "negative_prompt", "metadata")
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "topic": ("STRING", {"default": ""}),
                "variant_index": ("INT", {"default": 0, "min": 0, "max": 10000}),
                "base_prompt_template": ("STRING", {"multiline": True, "default": "a beautiful {topic}, highly detailed"}),
                "base_negative_prompt": ("STRING", {"multiline": True, "default": "blurry, watermark, text, low quality"}),
                "prompts_per_topic": ("INT", {"default": 50, "min": 1, "max": 10000}),
            },
            "optional": {
                "pipeline_config": ("PIPELINE_CONFIG",),
                "resolution": ("STRING", {"default": "512x512"}),
                "llm_config": ("LLM_CONFIG",),
                "custom_word_bank_path": ("STRING", {"default": ""}),
                "topic_tag_bank": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    def generate(self, topic, variant_index, base_prompt_template,
                 base_negative_prompt, prompts_per_topic,
                 pipeline_config=None, resolution="512x512",
                 llm_config=None,
                 custom_word_bank_path="", topic_tag_bank=""):

        # PIPELINE_CONFIG overrides manual fields
        if pipeline_config:
            workflow_name = pipeline_config.get("workflow_name", "")
            output_dir = pipeline_config.get("output_dir", "output")
            prompts_per_topic = pipeline_config.get("prompts_per_topic", prompts_per_topic)
        else:
            workflow_name = ""
            output_dir = "output"

        if not topic:
            return ("", base_negative_prompt, "{}")

        sanitized_topic = sanitize_name(topic)

        # Resolve base prompt
        resolved_base = base_prompt_template.replace("{topic}", topic)

        # Check memory cache first, then disk
        cache_key = f"{workflow_name}:{sanitized_topic}" if workflow_name else sanitized_topic
        cached = _prompt_cache.get(cache_key)

        if cached is None and workflow_name:
            cache_dir = os.path.join(output_dir, sanitize_name(workflow_name), ".prompt_cache")
            cached = _load_prompt_cache(cache_dir, sanitized_topic)

        if cached is None:
            variants = generate_variants(
                base_prompt=resolved_base,
                num_variants=prompts_per_topic,
                custom_word_bank_path=custom_word_bank_path or None,
            )

            llm_cfg = None
            if llm_config and llm_config.get("api_url"):
                llm_cfg = llm_config

            tags, tag_sources = generate_tags(
                topic=topic,
                base_prompt=resolved_base,
                resolution=resolution,
                topic_tag_bank=topic_tag_bank or None,
                llm_config=llm_cfg,
            )

            cached = {
                "topic": topic,
                "base_prompt": resolved_base,
                "variants": variants,
                "tags": tags,
                "tag_sources": tag_sources,
            }

            _prompt_cache[cache_key] = cached
            if workflow_name:
                cache_dir = os.path.join(output_dir, sanitize_name(workflow_name), ".prompt_cache")
                _save_prompt_cache(cache_dir, sanitized_topic, cached)

        # Get the variant for the requested index
        variants = cached.get("variants", [])
        if variant_index < len(variants):
            variant = variants[variant_index]
            prompt = variant["prompt"]
            strategy = variant.get("strategy", "unknown")
        else:
            prompt = resolved_base
            strategy = "fallback"

        metadata_dict = {
            "prompt": prompt,
            "negative_prompt": base_negative_prompt,
            "tags": cached.get("tags", {}),
            "tag_sources": cached.get("tag_sources", {}),
            "pipeline": {
                "workflow_name": workflow_name or "unnamed",
                "topic": sanitized_topic,
                "variant_index": variant_index,
                "variant_strategy": strategy,
                "total_variants": prompts_per_topic,
            },
        }

        return (prompt, base_negative_prompt, json.dumps(metadata_dict, ensure_ascii=False))

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
