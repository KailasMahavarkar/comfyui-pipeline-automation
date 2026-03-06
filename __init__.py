"""ComfyUI Pipeline Automation Node Pack — registers all 5 nodes."""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = None

try:
    from .nodes import SaveAs, APICall, BulkPrompter, PipelineController, CRONScheduler

    NODE_CLASS_MAPPINGS = {
        "CRONScheduler": CRONScheduler,
        "PipelineController": PipelineController,
        "SaveAs": SaveAs,
        "APICall": APICall,
        "BulkPrompter": BulkPrompter,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "CRONScheduler": "CRON Scheduler",
        "PipelineController": "Pipeline Controller",
        "SaveAs": "Save As",
        "APICall": "API Call",
        "BulkPrompter": "Bulk Prompter",
    }
except ImportError:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
