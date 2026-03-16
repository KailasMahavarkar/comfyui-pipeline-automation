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
_last_prompt: dict | None = None
_client_id: str | None = None


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


def _fetch_last_prompt(api_url: str) -> dict | None:
    """Fetch the most recent workflow from ComfyUI /history."""
    global _client_id
    try:
        req = urllib.request.Request(f"{api_url.rstrip('/')}/history?max_items=1")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data:
            return None
        latest = next(iter(data.values()))
        prompt_data = latest.get("prompt", [])
        # Extract client_id from extra_data so UI shows progress
        if len(prompt_data) >= 4 and isinstance(prompt_data[3], dict):
            _client_id = prompt_data[3].get("client_id")
        if len(prompt_data) >= 3:
            return prompt_data[2]
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch history: {e}")
        return None


def _check_prompt_completed(api_url: str, prompt_id: str) -> bool:
    """Check if a specific prompt_id completed via /history."""
    try:
        req = urllib.request.Request(f"{api_url.rstrip('/')}/history/{prompt_id}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return prompt_id in data
    except Exception:
        return False


def _requeue_workflow(api_url: str) -> str | None:
    """Re-queue the workflow via ComfyUI /prompt API. Returns prompt_id or None."""
    global _last_prompt

    prompt = _last_prompt
    if not prompt:
        prompt = _fetch_last_prompt(api_url)
    if not prompt:
        logger.error("No workflow found to re-queue")
        return None

    try:
        url = f"{api_url.rstrip('/')}/prompt"
        payload = {"prompt": prompt}
        if _client_id:
            payload["client_id"] = _client_id
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        _last_prompt = prompt
        prompt_id = result.get("prompt_id", "")
        logger.info("Workflow re-queued: %s", prompt_id)
        return prompt_id
    except Exception as e:
        logger.error(f"Failed to re-queue workflow: {e}")
        _last_prompt = None
        return None


def _wait_for_queue_free(api_url: str, stop_event: threading.Event, poll_interval: int = 3):
    """Wait until the queue is no longer busy."""
    while not stop_event.is_set():
        if not _check_queue_busy(api_url):
            return True
        if stop_event.wait(timeout=poll_interval):
            return False
    return False


def _scheduler_loop(interval_seconds: int, api_url: str):
    """Background thread loop for interval-based scheduling."""
    global _run_count

    while not _scheduler_stop.is_set():
        if _scheduler_stop.wait(timeout=interval_seconds):
            break

        # Skip-if-busy guard
        if _check_queue_busy(api_url):
            continue

        # Re-queue
        prompt_id = _requeue_workflow(api_url)
        if not prompt_id:
            break

        # Wait for execution to finish
        _wait_for_queue_free(api_url, _scheduler_stop)

        if _scheduler_stop.is_set():
            break

        # Check immediately: did it complete or was it cancelled?
        if not _check_prompt_completed(api_url, prompt_id):
            logger.info("Execution cancelled (prompt %s not in history), stopping pipeline", prompt_id)
            break

        with _lock:
            _run_count += 1


class CRONScheduler:
    """Re-queues workflow on interval via background thread.
    Marked as OUTPUT_NODE so it always executes without needing a passthrough.
    Stops automatically when user cancels (detects interrupted execution)."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "schedule"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "is_complete": ("BOOLEAN", {"forceInput": True}),
                "schedule_preset": (list(SCHEDULE_PRESETS.keys()),),
                "comfyui_api_url": ("STRING", {"default": "http://127.0.0.1:8188"}),
            },
            "optional": {
                "interval_seconds": ("INT", {"default": 60, "min": 10, "max": 86400}),
            },
        }

    def schedule(self, is_complete, schedule_preset, comfyui_api_url,
                 interval_seconds=60):
        global _scheduler_thread, _run_count

        actual_interval = SCHEDULE_PRESETS.get(schedule_preset, interval_seconds)

        if is_complete:
            _stop_existing()
            status = f"DONE | runs: {_run_count} | pipeline complete"
            return (status,)

        _stop_existing()
        _run_count = 0

        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(actual_interval, comfyui_api_url),
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
