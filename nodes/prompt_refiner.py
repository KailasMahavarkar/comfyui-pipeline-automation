"""Prompt Refiner node — enhances prompt and generates negative via LLM."""

import json
import logging
import urllib.request

from ..lib.response_parser import auto_parse_json

logger = logging.getLogger(__name__)

# Cache: input prompt → (refined_prompt, refined_negative)
_refine_cache: dict[str, tuple[str, str]] = {}

PROVIDER_URLS = {
    "OpenRouter": "https://openrouter.ai/api/v1/chat/completions",
    "OpenAI": "https://api.openai.com/v1/chat/completions",
    "Ollama": "http://localhost:11434/v1/chat/completions",
    "LM Studio": "http://localhost:1234/v1/chat/completions",
    "Custom": "",
}


class PromptRefiner:
    """Enhances a prompt and generates a matching negative prompt via LLM.
    Drop between Prompt Generator and CLIP Encode.
    Outputs metadata for Save As with the refined prompt baked in.
    Caches results per input prompt — crash recovery doesn't re-call the LLM.
    Falls back to original prompt silently on failure."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("refined_prompt", "refined_negative")
    FUNCTION = "refine"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "negative_prompt": ("STRING", {"forceInput": True}),
                "provider": (list(PROVIDER_URLS.keys()),),
                "model": ("STRING", {"default": "google/gemini-3.1-flash-lite-preview"}),
                "api_key": ("STRING", {"default": ""}),
            },
            "optional": {
                "api_url_override": ("STRING", {"default": ""}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 500, "min": 50, "max": 4096}),
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

    def refine(self, prompt, negative_prompt, provider, model, api_key,
               api_url_override="", temperature=0.7, max_tokens=500,
               positive_guidance="", negative_guidance=""):

        if not prompt or not prompt.strip():
            return ("", negative_prompt)

        # Resolve API URL
        api_url = api_url_override.strip() if api_url_override and api_url_override.strip() else PROVIDER_URLS.get(provider, "")

        # No API URL — pass through without refinement
        if not api_url:
            return (prompt, negative_prompt)

        # Check cache
        cache_key = f"{prompt}:{model}:{positive_guidance}:{negative_guidance}"
        if cache_key in _refine_cache:
            return _refine_cache[cache_key]

        # Build LLM prompt
        parts = [
            "You are an image generation prompt expert.",
            "Given a base prompt, enhance it and generate a matching negative prompt.",
        ]
        if positive_guidance and positive_guidance.strip():
            parts.append(f"Positive guidance (always include): {positive_guidance.strip()}")
        if negative_guidance and negative_guidance.strip():
            parts.append(f"Negative guidance (always avoid): {negative_guidance.strip()}")

        parts.append(
            '\nReturn ONLY valid JSON with two keys: "prompt" and "negative". '
            "No explanation, no markdown. Example:\n"
            '{"prompt": "enhanced prompt here", "negative": "negative prompt here"}'
        )
        parts.append(f"\nBase prompt: {prompt}")
        if negative_prompt and negative_prompt.strip():
            parts.append(f"Base negative: {negative_prompt}")

        user_msg = "\n".join(parts)

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
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

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

            result_tuple = (refined, negative)
            _refine_cache[cache_key] = result_tuple
            logger.info("Prompt refined: '%s...' → '%s...'", prompt[:40], refined[:40])
            return result_tuple

        except Exception as e:
            logger.warning("Prompt refinement failed, using original: %s", e)
            return (prompt, negative_prompt)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
