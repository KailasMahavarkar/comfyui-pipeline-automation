"""ComfyUI Pipeline Automation Node Pack."""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = None

try:
    from .nodes import (SaveAs, Webhook, CRONScheduler,
                        GapScannerNode, PromptGenerator, PromptRefiner,
                        OpenRouterProvider, OpenAIProvider, OllamaProvider)

    NODE_CLASS_MAPPINGS = {
        "CRONScheduler": CRONScheduler,
        "GapScanner": GapScannerNode,
        "PromptGenerator": PromptGenerator,
        "SaveAs": SaveAs,
        "Webhook": Webhook,
        "PromptRefiner": PromptRefiner,
        "OpenRouterProvider": OpenRouterProvider,
        "OpenAIProvider": OpenAIProvider,
        "OllamaProvider": OllamaProvider,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "CRONScheduler": "CRON Scheduler",
        "GapScanner": "Gap Scanner",
        "PromptGenerator": "Prompt Generator",
        "SaveAs": "Save As",
        "Webhook": "Webhook",
        "PromptRefiner": "Prompt Refiner",
        "OpenRouterProvider": "OpenRouter Provider",
        "OpenAIProvider": "OpenAI Provider",
        "OllamaProvider": "Ollama Provider",
    }
except ImportError:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
