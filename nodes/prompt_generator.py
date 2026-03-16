"""PromptGenerator node — generates prompt variants with three source strategies."""

import json
import os

from ..lib.prompt_mutations import generate_variants, generate_variants_via_llm, parse_prompt_list
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

    Variant source priority:
        1. prompt_list  — user-provided prompts, picked by variant_index
        2. llm_config   — one LLM call per topic generates all variants, cached
        3. (default)    — local mutation strategies, cached
    """

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
                "prompt_list": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    def generate(self, topic, variant_index, base_prompt_template,
                 base_negative_prompt, prompts_per_topic,
                 pipeline_config=None, resolution="512x512",
                 llm_config=None,
                 custom_word_bank_path="", topic_tag_bank="",
                 prompt_list=""):

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
        resolved_base = base_prompt_template.replace("{topic}", topic)
        llm_cfg = llm_config if llm_config and llm_config.get("api_url") else None

        # --- Priority 1: custom prompt list ---
        # Bypasses cache — list is user-controlled and may change each run.
        # Tags use layers 1+2 only (instant, no LLM cost per execution).
        if prompt_list and prompt_list.strip():
            variants = parse_prompt_list(prompt_list)
            tags, tag_sources = generate_tags(
                topic=topic,
                base_prompt=resolved_base,
                resolution=resolution,
                topic_tag_bank=topic_tag_bank or None,
                llm_config=None,
            )
            if variants:
                idx = variant_index % len(variants)
                prompt = variants[idx]["prompt"]
                strategy = "custom_list"
            else:
                prompt = resolved_base
                strategy = "fallback"

            return self._build_result(
                prompt, base_negative_prompt, strategy,
                variant_index, prompts_per_topic,
                workflow_name, sanitized_topic, tags, tag_sources,
            )

        # --- Priority 2 & 3: cache-backed generation ---
        cache_key = f"{workflow_name}:{sanitized_topic}" if workflow_name else sanitized_topic
        cached = _prompt_cache.get(cache_key)

        if cached is None and workflow_name:
            cache_dir = os.path.join(output_dir, sanitize_name(workflow_name), ".prompt_cache")
            cached = _load_prompt_cache(cache_dir, sanitized_topic)

        if cached is None:
            # Priority 2: LLM generates all variants in one call
            if llm_cfg:
                variants = generate_variants_via_llm(
                    base_prompt=resolved_base,
                    num_variants=prompts_per_topic,
                    topic=topic,
                    llm_config=llm_cfg,
                )
                # Fall back to mutations if LLM failed or returned too few
                if not variants:
                    variants = generate_variants(
                        base_prompt=resolved_base,
                        num_variants=prompts_per_topic,
                        custom_word_bank_path=custom_word_bank_path or None,
                    )
            else:
                # Priority 3: local mutation strategies
                variants = generate_variants(
                    base_prompt=resolved_base,
                    num_variants=prompts_per_topic,
                    custom_word_bank_path=custom_word_bank_path or None,
                )

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

        variants = cached.get("variants", [])
        if variant_index < len(variants):
            prompt = variants[variant_index]["prompt"]
            strategy = variants[variant_index].get("strategy", "unknown")
        else:
            prompt = resolved_base
            strategy = "fallback"

        return self._build_result(
            prompt, base_negative_prompt, strategy,
            variant_index, prompts_per_topic,
            workflow_name, sanitized_topic,
            cached.get("tags", {}), cached.get("tag_sources", {}),
        )

    def _build_result(self, prompt, negative_prompt, strategy,
                      variant_index, total_variants,
                      workflow_name, sanitized_topic, tags, tag_sources):
        metadata_dict = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "tags": tags,
            "tag_sources": tag_sources,
            "pipeline": {
                "workflow_name": workflow_name or "unnamed",
                "topic": sanitized_topic,
                "variant_index": variant_index,
                "variant_strategy": strategy,
                "total_variants": total_variants,
            },
        }
        return (prompt, negative_prompt, json.dumps(metadata_dict, ensure_ascii=False))

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
