"""PromptGenerator node — generates prompt variants via mutations."""

import json
import os

from ..lib.prompt_mutations import generate_variants
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
    """Generates prompt variants from a base template + topic.

    Reads topic, resolution, variant_index from PIPELINE_CONFIG.
    For LLM-enhanced prompts, wire the output through a Prompt Refiner node.
    """

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "negative_prompt")
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipeline_config": ("PIPELINE_CONFIG",),
                "base_prompt_template": ("STRING", {"multiline": True, "default": "a beautiful {topic}, highly detailed"}),
                "base_negative_prompt": ("STRING", {"multiline": True, "default": "blurry, watermark, text, low quality"}),
            },
        }

    def generate(self, pipeline_config, base_prompt_template, base_negative_prompt):

        workflow_name = pipeline_config.get("workflow_name", "")
        output_dir = pipeline_config.get("output_dir", "output")
        prompts_per_topic = pipeline_config.get("prompts_per_topic", 50)
        topic = pipeline_config.get("topic", "")
        resolution = pipeline_config.get("resolution", "512x512")
        variant_index = pipeline_config.get("variant_index", 0)

        if not topic:
            return ("", base_negative_prompt, "{}")

        sanitized_topic = sanitize_name(topic)
        resolved_base = base_prompt_template.replace("{topic}", topic)

        # Cache-backed mutation generation
        cache_key = f"{workflow_name}:{sanitized_topic}" if workflow_name else sanitized_topic
        cached = _prompt_cache.get(cache_key)

        if cached is None and workflow_name:
            cache_dir = os.path.join(output_dir, sanitize_name(workflow_name), ".prompt_cache")
            cached = _load_prompt_cache(cache_dir, sanitized_topic)

        if cached is None:
            variants = generate_variants(
                base_prompt=resolved_base,
                num_variants=prompts_per_topic,
            )

            tags, tag_sources = generate_tags(
                topic=topic,
                base_prompt=resolved_base,
                resolution=resolution,
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

        variants = cached.get("variants", [])
        if variant_index < len(variants):
            prompt = variants[variant_index]["prompt"]
        else:
            prompt = resolved_base

        return (prompt, base_negative_prompt)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
