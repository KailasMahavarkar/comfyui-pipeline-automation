"""CRON Scheduler node — re-queues workflow on cron schedule via background thread."""

import json
import threading
import time
import logging
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

SCHEDULE_PRESETS = {
    "Custom": None,
    "Every 1 min": "*/1 * * * *",
    "Every 5 min": "*/5 * * * *",
    "Every 15 min": "*/15 * * * *",
    "Every 30 min": "*/30 * * * *",
    "Hourly": "0 * * * *",
    "Every 6 hours": "0 */6 * * *",
    "Daily at midnight": "0 0 * * *",
    "Daily at 9 AM": "0 9 * * *",
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


def _scheduler_loop(cron_expr: str, api_url: str, mode: str,
                    external_command: str, max_iterations: int):
    """Background thread loop for cron scheduling."""
    global _run_count
    from croniter import croniter

    cron = croniter(cron_expr, datetime.now())

    while not _scheduler_stop.is_set():
        next_time = cron.get_next(datetime)
        now = datetime.now()
        wait_seconds = (next_time - now).total_seconds()

        if wait_seconds > 0:
            if _scheduler_stop.wait(timeout=wait_seconds):
                break

        if _scheduler_stop.is_set():
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
    """Re-queues workflow on cron schedule via background thread."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("status", "passthrough")
    FUNCTION = "schedule"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "schedule_preset": (list(SCHEDULE_PRESETS.keys()),),
                "cron_expression": ("STRING", {"default": "*/5 * * * *"}),
                "enabled": ("BOOLEAN", {"default": False}),
                "mode": (["requeue_workflow", "run_command", "both"],),
                "comfyui_api_url": ("STRING", {"default": "http://127.0.0.1:8188"}),
                "max_iterations": ("INT", {"default": 0, "min": 0, "max": 1000000}),
            },
            "optional": {
                "external_command": ("STRING", {"default": ""}),
                "passthrough": ("IMAGE",),
                "is_complete": ("BOOLEAN", {"default": False}),
            },
        }

    def schedule(self, schedule_preset, cron_expression, enabled, mode,
                 comfyui_api_url, max_iterations,
                 external_command="", passthrough=None, is_complete=False):
        global _scheduler_thread, _run_count

        # Determine actual cron expression
        if schedule_preset != "Custom" and schedule_preset in SCHEDULE_PRESETS:
            actual_cron = SCHEDULE_PRESETS[schedule_preset]
        else:
            actual_cron = cron_expression

        # Handle DONE signal
        if is_complete:
            _stop_existing()
            status = f"DONE | runs: {_run_count} | pipeline complete"
            return (status, passthrough)

        # Handle disabled
        if not enabled:
            _stop_existing()
            status = "OFF"
            return (status, passthrough)

        # Start or restart scheduler
        _stop_existing()
        _run_count = 0

        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(actual_cron, comfyui_api_url, mode, external_command, max_iterations),
            daemon=True,
            name="CRONScheduler",
        )
        _scheduler_thread.start()

        # Calculate next run for status
        from croniter import croniter
        cron = croniter(actual_cron, datetime.now())
        next_run = cron.get_next(datetime)

        preset_label = schedule_preset if schedule_preset != "Custom" else actual_cron
        status = f"ON | {preset_label} | next: {next_run.isoformat()} | runs: {_run_count}"

        return (status, passthrough)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
