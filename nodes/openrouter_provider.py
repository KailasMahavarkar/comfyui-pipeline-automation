"""OpenRouter Provider — builds LLM_CONFIG for OpenRouter API."""

from ..lib.secrets import get_api_key


class OpenRouterProvider:
    """Outputs an LLM_CONFIG dict pre-configured for OpenRouter."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("LLM_CONFIG",)
    RETURN_NAMES = ("llm_config",)
    FUNCTION = "configure"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": "google/gemini-3.1-flash-lite-preview"}),
            },
            "optional": {
                "api_key_name": ("STRING", {"default": "openrouter"}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 1024, "min": 100, "max": 4096}),
            },
        }

    def configure(self, model, api_key_name="openrouter", temperature=0.7, max_tokens=1024):
        return ({
            "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "api_key": get_api_key(api_key_name),
            "model": model,
            "format": "openai",
            "temperature": temperature,
            "max_tokens": max_tokens,
        },)
