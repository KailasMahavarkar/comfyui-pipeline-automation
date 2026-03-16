"""Prompt Refiner node — enhances a prompt via LLM call."""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# Cache refined prompts to avoid re-calling LLM on crash recovery
_refine_cache: dict[str, str] = {}

PROVIDER_URLS = {
    "OpenRouter": "https://openrouter.ai/api/v1/chat/completions",
    "OpenAI": "https://api.openai.com/v1/chat/completions",
    "Ollama": "http://localhost:11434/v1/chat/completions",
    "LM Studio": "http://localhost:1234/v1/chat/completions",
    "Custom": "",
}


class PromptRefiner:
    """Enhances a prompt via LLM. Drop between Prompt Generator and CLIP Encode.
    Caches results per input prompt — crash recovery doesn't re-call the LLM.
    Falls back to original prompt silently on failure."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("refined_prompt", "original_prompt")
    FUNCTION = "refine"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "provider": (list(PROVIDER_URLS.keys()),),
                "model": ("STRING", {"default": "google/gemini-3.1-flash-lite-preview"}),
                "api_key": ("STRING", {"default": ""}),
            },
            "optional": {
                "api_url_override": ("STRING", {"default": ""}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 300, "min": 50, "max": 4096}),
                "instruction": ("STRING", {
                    "multiline": True,
                    "default": "Enhance this image generation prompt. Make it more detailed and vivid. Keep it as a single prompt, no explanations. Return ONLY the enhanced prompt text.",
                }),
            },
        }

    def refine(self, prompt, provider, model, api_key,
               api_url_override="", temperature=0.7, max_tokens=300,
               instruction=""):

        if not prompt or not prompt.strip():
            return ("", "")

        # Resolve API URL
        api_url = api_url_override.strip() if api_url_override and api_url_override.strip() else PROVIDER_URLS.get(provider, "")
        if not api_url:
            return (prompt, prompt)

        # Check cache
        cache_key = f"{prompt}:{model}"
        if cache_key in _refine_cache:
            return (_refine_cache[cache_key], prompt)

        default_instruction = (
            "Enhance this image generation prompt. Make it more detailed and vivid. "
            "Keep it as a single prompt, no explanations. Return ONLY the enhanced prompt text."
        )
        inst = instruction.strip() if instruction and instruction.strip() else default_instruction
        user_msg = f"{inst}\n\nPrompt: {prompt}"

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
            refined = content.strip()

            if not refined:
                logger.warning("LLM returned empty refinement, using original")
                return (prompt, prompt)

            # Strip markdown code blocks if LLM wrapped it
            if refined.startswith("```") and refined.endswith("```"):
                refined = refined.strip("`").strip()

            _refine_cache[cache_key] = refined
            logger.info("Prompt refined: '%s...' → '%s...'", prompt[:40], refined[:40])
            return (refined, prompt)

        except Exception as e:
            logger.warning("Prompt refinement failed, using original: %s", e)
            return (prompt, prompt)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
