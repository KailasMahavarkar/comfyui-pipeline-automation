"""Ollama Provider — builds LLM_CONFIG for Ollama (local or cloud)."""

from ..lib.secrets import get_api_key

_OLLAMA_URLS = {
    "local": "http://localhost:11434/api/chat",
    "cloud": "https://ollama.com/api/chat",
}


class OllamaProvider:
    """Outputs an LLM_CONFIG dict pre-configured for Ollama."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("LLM_CONFIG",)
    RETURN_NAMES = ("llm_config",)
    FUNCTION = "configure"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["local", "cloud"],),
                "model": ("STRING", {"default": "llama3"}),
            },
            "optional": {
                "api_key_name": ("STRING", {"default": ""}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 1024, "min": 100, "max": 4096}),
            },
        }

    def configure(self, mode, model, api_key_name="", temperature=0.7, max_tokens=1024):
        resolved_key_name = api_key_name.strip() if api_key_name else f"ollama_{mode}"
        return ({
            "api_url": _OLLAMA_URLS[mode],
            "api_key": get_api_key(resolved_key_name),
            "model": model,
            "format": "ollama",
            "temperature": temperature,
            "max_tokens": max_tokens,
        },)
