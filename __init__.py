"""ComfyUI Pipeline Automation Node Pack."""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = None

try:
    from .nodes import (SaveAs, Webhook, CRONScheduler,
                        GapScannerNode, PromptGenerator,
                        PromptList, TagBank, PromptRefiner)

    NODE_CLASS_MAPPINGS = {
        "CRONScheduler": CRONScheduler,
        "GapScanner": GapScannerNode,
        "PromptGenerator": PromptGenerator,
        "SaveAs": SaveAs,
        "Webhook": Webhook,
        "PromptList": PromptList,
        "TagBank": TagBank,
        "PromptRefiner": PromptRefiner,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "CRONScheduler": "CRON Scheduler",
        "GapScanner": "Gap Scanner",
        "PromptGenerator": "Prompt Generator",
        "SaveAs": "Save As",
        "Webhook": "Webhook",
        "PromptList": "Prompt List",
        "TagBank": "Tag Bank",
        "PromptRefiner": "Prompt Refiner",
    }
except ImportError:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
