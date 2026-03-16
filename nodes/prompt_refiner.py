"""Prompt Refiner node — enhances a prompt via LLM call."""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# Cache refined prompts to avoid re-calling LLM on crash recovery
_refine_cache: dict[str, str] = {}


class PromptRefiner:
    """Takes a raw prompt, calls an LLM to enhance it, outputs the refined version.
    Caches results per input prompt so crash recovery doesn't re-call the LLM."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("refined_prompt", "original_prompt")
    FUNCTION = "refine"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "llm_config": ("LLM_CONFIG",),
            },
            "optional": {
                "instruction": ("STRING", {
                    "multiline": True,
                    "default": "Enhance this image generation prompt. Make it more detailed and vivid. Keep it as a single prompt, no explanations. Return ONLY the enhanced prompt text.",
                }),
            },
        }

    def refine(self, prompt, llm_config, instruction=""):
        if not prompt or not prompt.strip():
            return ("", "")

        # Check cache
        cache_key = f"{prompt}:{llm_config.get('model', '')}"
        if cache_key in _refine_cache:
            return (_refine_cache[cache_key], prompt)

        api_url = llm_config.get("api_url", "")
        api_key = llm_config.get("api_key", "")
        model = llm_config.get("model", "")
        temperature = llm_config.get("temperature", 0.7)
        max_tokens = llm_config.get("max_tokens", 200)

        if not api_url:
            return (prompt, prompt)

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
