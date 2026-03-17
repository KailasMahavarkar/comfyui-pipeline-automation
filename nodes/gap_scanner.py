"""GapScanner node — scans output directory for missing topic/resolution combos."""

import json
import os

from ..lib.scanner import GapScanner as Scanner
from ..lib.naming import sanitize_name

# Module-level cache for scanner instances (persists across runs)
_scanners: dict[str, Scanner] = {}


def _load_failures(workflow_dir: str) -> dict:
    """Load strike counter data."""
    path = os.path.join(workflow_dir, ".failures.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _get_skipped_paths(failures: dict) -> set[str]:
    """Get paths that have been skipped due to repeated failures."""
    return {path for path, data in failures.items() if data.get("skipped", False)}


class GapScannerNode:
    """Scans output directory, finds missing topic/resolution combos, emits the next one.

    All per-execution data (topic, resolution, variant_index) is packed into
    PIPELINE_CONFIG to minimize wiring. Only width/height/is_complete/status
    are separate outputs since they go to standard ComfyUI nodes.
    """

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("INT", "INT", "BOOLEAN", "STRING", "PIPELINE_CONFIG")
    RETURN_NAMES = ("width", "height", "is_complete", "status", "pipeline_config")
    FUNCTION = "scan"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "workflow_name": ("STRING", {"default": ""}),
                "topic_list": ("STRING", {"multiline": True}),
                "resolution_list": ("STRING", {"multiline": True, "default": "512x512"}),
                "prompts_per_topic": ("INT", {"default": 50, "min": 1, "max": 10000}),
            },
            "optional": {
                "output_dir": ("STRING", {"default": "output"}),
                "format": (["png", "jpeg", "webp"],),
                "reset_workflow": ("BOOLEAN", {"default": False}),
            },
        }

    def _build_config(self, workflow_name, output_dir, fmt, prompts_per_topic,
                      topic="", resolution="", variant_index=0):
        return {
            "workflow_name": workflow_name,
            "output_dir": output_dir,
            "format": fmt,
            "prompts_per_topic": prompts_per_topic,
            "topic": topic,
            "resolution": resolution,
            "variant_index": variant_index,
        }

    def scan(self, workflow_name, topic_list, resolution_list,
             prompts_per_topic,
             output_dir="output", format="png", reset_workflow=False):

        if not workflow_name:
            cfg = self._build_config("", output_dir, format, prompts_per_topic)
            return (512, 512, False, "ERROR: workflow_name is required", cfg)

        workflow_name = sanitize_name(workflow_name)

        # Parse inputs
        topics = [t.strip() for t in topic_list.strip().splitlines() if t.strip()]
        resolutions = [r.strip() for r in resolution_list.strip().splitlines() if r.strip()]

        if not topics:
            cfg = self._build_config(workflow_name, output_dir, format, prompts_per_topic)
            return (512, 512, True, "ERROR: No topics provided", cfg)
        if not resolutions:
            cfg = self._build_config(workflow_name, output_dir, format, prompts_per_topic)
            return (512, 512, True, "ERROR: No resolutions provided", cfg)

        workflow_dir = os.path.join(output_dir, workflow_name)

        # Handle reset
        if reset_workflow and os.path.exists(workflow_dir):
            import shutil
            shutil.rmtree(workflow_dir)
            if workflow_name in _scanners:
                del _scanners[workflow_name]

        # Get or create scanner
        if workflow_name not in _scanners:
            _scanners[workflow_name] = Scanner(output_dir, workflow_name)
        scanner = _scanners[workflow_name]

        # Force rescan — Save As wrote files since the last execution
        scanner.invalidate_cache()

        # Load failures / skipped
        failures = _load_failures(workflow_dir)
        skipped = _get_skipped_paths(failures)

        # Build matrix
        sanitized_topics = [sanitize_name(t) for t in topics]
        matrix = scanner.build_matrix(sanitized_topics, resolutions, prompts_per_topic)

        # Find first gap
        gap = scanner.find_first_gap(matrix, format, skipped)

        if gap is None:
            total = len(matrix)
            status = f"{workflow_name} | COMPLETE | {total}/{total} (100%)"
            cfg = self._build_config(workflow_name, output_dir, format, prompts_per_topic)
            return (512, 512, True, status, cfg)

        topic = gap["topic"]
        resolution = gap["resolution"]
        width = gap["width"]
        height = gap["height"]
        variant_index = gap["variant_index"]

        # Find original topic name (pre-sanitized)
        topic_idx = sanitized_topics.index(topic) if topic in sanitized_topics else 0
        original_topic = topics[topic_idx] if topic_idx < len(topics) else topic

        # Build status
        total = len(matrix)
        existing = total - len(scanner.find_gaps(matrix, format, skipped))
        global_index = existing + 1

        topic_idx_display = sanitized_topics.index(topic) + 1 if topic in sanitized_topics else 0
        pct = (global_index / total * 100) if total > 0 else 0
        status = (
            f"{workflow_name} | topic {topic_idx_display}/{len(topics)} ({original_topic}) | "
            f"variant {variant_index + 1}/{prompts_per_topic} | "
            f"res {resolutions.index(resolution) + 1}/{len(resolutions)} | "
            f"global {global_index:,}/{total:,} ({pct:.1f}%) | "
            f"{len(skipped)} skipped"
        )

        cfg = self._build_config(workflow_name, output_dir, format, prompts_per_topic,
                                 topic=original_topic, resolution=resolution,
                                 variant_index=variant_index)

        return (width, height, False, status, cfg)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
