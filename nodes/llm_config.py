"""LLM Config node — structured LLM connection settings."""

PROVIDER_URLS = {
    "OpenRouter": "https://openrouter.ai/api/v1/chat/completions",
    "OpenAI": "https://api.openai.com/v1/chat/completions",
    "Ollama": "http://localhost:11434/v1/chat/completions",
    "LM Studio": "http://localhost:1234/v1/chat/completions",
    "Custom": "",
}


class LLMConfig:
    """Structured LLM connection settings. Outputs LLM_CONFIG for downstream nodes."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("LLM_CONFIG",)
    RETURN_NAMES = ("llm_config",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "provider": (list(PROVIDER_URLS.keys()),),
                "model": ("STRING", {"default": "anthropic/claude-3-haiku"}),
                "api_key": ("STRING", {"default": ""}),
            },
            "optional": {
                "api_url_override": ("STRING", {"default": ""}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 200, "min": 1, "max": 4096}),
            },
        }

    def build(self, provider, model, api_key,
              api_url_override="", temperature=0.7, max_tokens=200):

        api_url = api_url_override.strip() if api_url_override.strip() else PROVIDER_URLS.get(provider, "")

        config = {
            "provider": provider,
            "api_url": api_url,
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        return (config,)
