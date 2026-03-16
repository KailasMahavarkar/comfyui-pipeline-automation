"""ComfyUI Pipeline Automation Node Pack."""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = None

try:
    from .nodes import (SaveAs, Webhook, CRONScheduler,
                        LLMConfig, GapScannerNode, PromptGenerator,
                        PromptList, TagBank)

    NODE_CLASS_MAPPINGS = {
        "CRONScheduler": CRONScheduler,
        "GapScanner": GapScannerNode,
        "PromptGenerator": PromptGenerator,
        "LLMConfig": LLMConfig,
        "SaveAs": SaveAs,
        "Webhook": Webhook,
        "PromptList": PromptList,
        "TagBank": TagBank,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "CRONScheduler": "CRON Scheduler",
        "GapScanner": "Gap Scanner",
        "PromptGenerator": "Prompt Generator",
        "LLMConfig": "LLM Config",
        "SaveAs": "Save As",
        "Webhook": "Webhook",
        "PromptList": "Prompt List",
        "TagBank": "Tag Bank",
    }
except ImportError:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
