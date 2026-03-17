"""Prompt Refiner node — enhances prompt and generates negative via LLM."""

import json
import logging
import urllib.request

from ..lib.response_parser import auto_parse_json

logger = logging.getLogger(__name__)

# Cache: input prompt → (refined_prompt, refined_negative)
_refine_cache: dict[str, tuple[str, str]] = {}


class PromptRefiner:
    """Enhances a prompt and generates a matching negative prompt via LLM.
    Drop between Prompt Generator and CLIP Encode.
    Outputs metadata for Save As with the refined prompt baked in.
    Caches results per input prompt — crash recovery doesn't re-call the LLM.
    Falls back to original prompt silently on failure."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("refined_prompt", "refined_negative", "metadata")
    FUNCTION = "refine"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "negative_prompt": ("STRING", {"forceInput": True}),
                "metadata": ("STRING", {"forceInput": True}),
                "llm_config": ("LLM_CONFIG",),
            },
            "optional": {
                "api_url_override": ("STRING", {"default": ""}),
                "positive_guidance": ("STRING", {
                    "multiline": True,
                    "default": "",
                }),
                "negative_guidance": ("STRING", {
                    "multiline": True,
                    "default": "",
                }),
            },
        }

    def refine(self, prompt, negative_prompt, metadata, llm_config,
               api_url_override="", positive_guidance="", negative_guidance=""):

        if not prompt or not prompt.strip():
            return ("", negative_prompt, metadata)

        # Extract config
        api_url = api_url_override.strip() if api_url_override and api_url_override.strip() else llm_config.get("api_url", "")
        api_key = llm_config.get("api_key", "")
        model = llm_config.get("model", "")
        llm_format = llm_config.get("format", "openai")
        temperature = llm_config.get("temperature", 0.7)
        max_tokens = llm_config.get("max_tokens", 1024)

        if not api_url:
            return (prompt, negative_prompt, metadata)

        # Check cache
        cache_key = f"{prompt}:{model}:{positive_guidance}:{negative_guidance}"
        if cache_key in _refine_cache:
            refined, negative = _refine_cache[cache_key]
            return (refined, negative, metadata)

        # Build LLM prompt
        parts = [
            "You are an image prompt writer. Write a scene description in 2-3 natural sentences. "
            "Describe what is in the scene, where it is, and what it looks and feels like. "
            "Write like you are describing a painting to someone who cannot see it.",
            "",
            "Good example: 'A young woman sits beneath a cherry blossom tree in a quiet Japanese garden, "
            "reading a worn paperback while pink petals drift around her. A stone lantern glows faintly "
            "beside a moss-covered path. The warm afternoon light catches the edges of the pages. "
            "Painted in soft watercolor with delicate linework.'",
            "",
            "Bad example: 'woman, tree, petals, garden, lantern, light, watercolor, detailed, 8k, masterpiece'",
            "",
            "Also generate a short negative prompt listing things to avoid.",
            "",
            "IMPORTANT: The prompt must always depict positive, uplifting, or neutral scenes. "
            "Never include violence, self-harm, death, gore, sadness, loneliness, fear, or dark themes. "
            "Transform any negative input into a wholesome, beautiful version of the same subject.",
        ]
        # Extract topic from metadata so LLM stays on topic
        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        topic = meta_dict.get("pipeline", {}).get("topic", "")
        if topic:
            parts.append(f"The image MUST be about: {topic}. Stay focused on this topic.")

        if positive_guidance and positive_guidance.strip():
            parts.append(f"Positive guidance (always include): {positive_guidance.strip()}")
        if negative_guidance and negative_guidance.strip():
            parts.append(f"Negative guidance (always avoid): {negative_guidance.strip()}")

        parts.append(
            "\nKeep the prompt under 75 words and the negative under 30 words. "
            'Return ONLY valid JSON with two keys: "prompt" and "negative". '
            "No explanation, no markdown, no truncation. Example:\n"
            '{"prompt": "enhanced prompt here", "negative": "negative prompt here"}'
        )
        parts.append(f"\nBase prompt: {prompt}")
        if negative_prompt and negative_prompt.strip():
            parts.append(f"Base negative: {negative_prompt}")

        user_msg = "\n".join(parts)

        is_ollama = llm_format == "ollama"

        if is_ollama:
            body = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": user_msg}],
                "stream": False,
            }).encode("utf-8")
        else:
            body = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": user_msg}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # Ollama returns message.content, OpenAI returns choices[0].message.content
            if is_ollama:
                content = result.get("message", {}).get("content", "")
            else:
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = auto_parse_json(content.strip())

            if isinstance(parsed, dict):
                refined = str(parsed.get("prompt", prompt)).strip()
                negative = str(parsed.get("negative", "")).strip()
            else:
                refined = content.strip()
                negative = ""

            if not refined:
                refined = prompt
            if not negative:
                negative = negative_prompt

            _refine_cache[cache_key] = (refined, negative)
            logger.info("Prompt refined: '%s...' → '%s...'", prompt[:40], refined[:40])
            return (refined, negative, metadata)

        except Exception as e:
            logger.warning("Prompt refinement failed, using original: %s", e)
            return (prompt, negative_prompt, metadata)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
