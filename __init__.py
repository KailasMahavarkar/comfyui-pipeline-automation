"""ComfyUI Pipeline Automation Node Pack."""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = None

try:
    from .nodes import (SaveAs, APICall, BulkPrompter, CRONScheduler,
                        LLMConfig, GapScannerNode, PromptGenerator)

    NODE_CLASS_MAPPINGS = {
        "CRONScheduler": CRONScheduler,
        "GapScanner": GapScannerNode,
        "PromptGenerator": PromptGenerator,
        "LLMConfig": LLMConfig,
        "SaveAs": SaveAs,
        "APICall": APICall,
        "BulkPrompter": BulkPrompter,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "CRONScheduler": "CRON Scheduler",
        "GapScanner": "Gap Scanner",
        "PromptGenerator": "Prompt Generator",
        "LLMConfig": "LLM Config",
        "SaveAs": "Save As",
        "APICall": "API Call",
        "BulkPrompter": "Bulk Prompter",
    }
except ImportError:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
