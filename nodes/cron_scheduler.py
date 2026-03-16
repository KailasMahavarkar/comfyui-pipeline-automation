"""CRON Scheduler node — re-queues workflow on interval via background thread."""

import json
import threading
import logging
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

SCHEDULE_PRESETS = {
    "Continuous": 5,
    "Every 1 min": 60,
    "Every 5 min": 300,
    "Every 15 min": 900,
    "Every 30 min": 1800,
    "Hourly": 3600,
    "Every 6 hours": 21600,
    "Every 12 hours": 43200,
    "Daily": 86400,
}

# Module-level state for single-instance lock
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()
_run_count = 0
_lock = threading.Lock()


def _stop_existing():
    """Stop any existing scheduler thread."""
    global _scheduler_thread
    _scheduler_stop.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)
    _scheduler_thread = None
    _scheduler_stop.clear()


def _check_queue_busy(api_url: str) -> bool:
    """Check if ComfyUI queue has pending/running items."""
    try:
        req = urllib.request.Request(f"{api_url.rstrip('/')}/queue")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            running = data.get("queue_running", [])
            pending = data.get("queue_pending", [])
            return len(running) > 0 or len(pending) > 0
    except Exception as e:
        logger.warning(f"Failed to check queue: {e}")
        return False


def _requeue_workflow(api_url: str, workflow: dict | None = None):
    """Re-queue the current workflow via ComfyUI /prompt API."""
    try:
        url = f"{api_url.rstrip('/')}/prompt"
        body = json.dumps({"prompt": workflow or {}}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        logger.info("Workflow re-queued successfully")
    except Exception as e:
        logger.error(f"Failed to re-queue workflow: {e}")


def _scheduler_loop(interval_seconds: int, api_url: str, mode: str,
                    external_command: str, max_iterations: int):
    """Background thread loop for interval-based scheduling."""
    global _run_count

    while not _scheduler_stop.is_set():
        if _scheduler_stop.wait(timeout=interval_seconds):
            break

        # Skip-if-busy guard
        if _check_queue_busy(api_url):
            logger.warning("Queue busy, skipping this tick")
            continue

        # Execute
        if mode in ("requeue_workflow", "both"):
            _requeue_workflow(api_url)

        if mode in ("run_command", "both") and external_command:
            import subprocess
            try:
                subprocess.run(
                    external_command, shell=True, timeout=300,
                    capture_output=True, text=True,
                )
            except subprocess.TimeoutExpired:
                logger.error(f"External command timed out: {external_command}")
            except Exception as e:
                logger.error(f"External command failed: {e}")

        with _lock:
            _run_count += 1

        if max_iterations > 0 and _run_count >= max_iterations:
            logger.info(f"Max iterations ({max_iterations}) reached, stopping")
            break


class CRONScheduler:
    """Re-queues workflow on interval via background thread.
    Marked as OUTPUT_NODE so it always executes without needing a passthrough."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "schedule"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "schedule_preset": (list(SCHEDULE_PRESETS.keys()),),
                "interval_seconds": ("INT", {"default": 60, "min": 10, "max": 86400}),
                "enabled": ("BOOLEAN", {"default": False}),
                "mode": (["requeue_workflow", "run_command", "both"],),
                "comfyui_api_url": ("STRING", {"default": "http://127.0.0.1:8188"}),
                "max_iterations": ("INT", {"default": 0, "min": 0, "max": 1000000}),
            },
            "optional": {
                "external_command": ("STRING", {"default": ""}),
                "is_complete": ("BOOLEAN", {"default": False}),
            },
        }

    def schedule(self, schedule_preset, interval_seconds, enabled, mode,
                 comfyui_api_url, max_iterations,
                 external_command="", is_complete=False):
        global _scheduler_thread, _run_count

        # Preset overrides manual interval
        actual_interval = SCHEDULE_PRESETS.get(schedule_preset, interval_seconds)

        # Handle DONE signal
        if is_complete:
            _stop_existing()
            status = f"DONE | runs: {_run_count} | pipeline complete"
            return (status,)

        # Handle disabled
        if not enabled:
            _stop_existing()
            status = "OFF"
            return (status,)

        # Start or restart scheduler
        _stop_existing()
        _run_count = 0

        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(actual_interval, comfyui_api_url, mode, external_command, max_iterations),
            daemon=True,
            name="CRONScheduler",
        )
        _scheduler_thread.start()

        next_run = datetime.now().timestamp() + actual_interval
        next_dt = datetime.fromtimestamp(next_run)
        status = f"ON | every {actual_interval}s | next: {next_dt.strftime('%H:%M:%S')} | runs: {_run_count}"

        return (status,)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
