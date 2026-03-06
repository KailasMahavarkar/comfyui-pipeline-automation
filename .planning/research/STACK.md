# Technology Stack

**Project:** ComfyUI Pipeline Automation Node Pack
**Researched:** 2026-03-06
**Overall Confidence:** MEDIUM (web verification tools unavailable; based on training data + PROJECT.md constraints)

## Recommended Stack

### Core Runtime

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.10+ (match ComfyUI's requirement) | Node pack runtime | ComfyUI itself requires 3.10+. Do NOT target 3.12+ features — many users run 3.10 via embedded Python in portable installs. Use 3.10 as your floor. | HIGH |
| ComfyUI Custom Node API | Latest (no version pinning) | Node registration, execution, caching | This is the host application. Nodes are Python classes discovered by ComfyUI at startup. No pip package — your code runs inside ComfyUI's process. | HIGH |

### Required Dependencies (pip)

| Library | Version | Purpose | Why | Confidence |
|---------|---------|---------|-----|------------|
| `croniter` | >=2.0,<4.0 | CRON expression parsing for Scheduler node | The standard Python library for cron expression evaluation. Lightweight, no C extensions, well-maintained. `apscheduler` is overkill — you don't need a scheduler daemon, just "when is next run?" math. | HIGH |
| `Pillow` | >=9.0 (already in ComfyUI) | Image validation, metadata embedding, header checks | ComfyUI already depends on Pillow. Do NOT add it to your requirements.txt — it ships with ComfyUI. Use it for file integrity validation (decode check) and EXIF/PNG text chunk metadata. | HIGH |
| `numpy` | >=1.24 (already in ComfyUI) | Tensor/image data handling | ComfyUI nodes pass images as numpy arrays (B,H,W,C format, float32, 0-1 range). Already installed. Do NOT add to your requirements. | HIGH |
| `piexif` | >=1.1.3 | JPEG EXIF metadata writing | Pillow can read EXIF but writing is limited. piexif gives full control over EXIF IFDs for embedding pipeline metadata in JPEGs. Lightweight, pure Python. | MEDIUM |
| `mutagen` | >=1.47 | Audio file metadata (ID3, Vorbis, etc.) | For embedding metadata in audio outputs (MP3, FLAC, OGG). The standard Python audio metadata library. Only needed if audio output support is required. | MEDIUM |

### System Dependencies

| Tool | Purpose | Why | Confidence |
|------|---------|-----|------------|
| `ffmpeg` | Audio/video encoding and muxing | ComfyUI's video workflows already expect ffmpeg on PATH. Not a Python package — system install. Used by Save As node for audio/video output formats. | HIGH |

### Already Available (Do NOT Install)

These ship with ComfyUI or Python stdlib. Listing them because they are central to this pack's implementation.

| Library | Source | Used For |
|---------|--------|----------|
| `Pillow` | ComfyUI dependency | Image I/O, validation, metadata |
| `numpy` | ComfyUI dependency | Image tensor handling |
| `torch` | ComfyUI dependency | Available but likely unnecessary for this pack |
| `aiohttp` | ComfyUI dependency | PromptServer is aiohttp-based; use for custom API routes |
| `json` | Python stdlib | Config, manifest, sidecar files |
| `csv` | Python stdlib | Manifest CSV writing |
| `pathlib` | Python stdlib | Filesystem operations (prefer over os.path) |
| `hashlib` | Python stdlib | Workflow fingerprinting (SHA-256) |
| `logging` | Python stdlib | Structured logging |
| `urllib.request` / `http.client` | Python stdlib | API Call node HTTP requests (simple cases) |
| `subprocess` | Python stdlib | ffmpeg invocation |
| `glob` / `os.scandir` | Python stdlib | Filesystem scanning for gap detection |
| `datetime` | Python stdlib | Timestamps, scheduling |
| `time` | Python stdlib | Timing, delays |
| `re` | Python stdlib | Template parsing, prompt mutation |
| `random` | Python stdlib | Prompt mutation strategies |
| `copy` | Python stdlib | Deep copying prompt data |
| `typing` | Python stdlib | Type hints |

### Optional / Conditional Dependencies

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| `requests` | >=2.28 | HTTP client for API Call node | If you need session management, auth headers, retries beyond what urllib provides. ComfyUI does NOT ship requests — you'd need to add it. However, `urllib.request` handles most REST API calls fine. **Recommendation: start with urllib, add requests only if needed.** | MEDIUM |
| `httpx` | >=0.25 | Async HTTP client | Only if API Call node needs async/concurrent requests. Overkill for sequential API calls. Do NOT use unless you have a clear async requirement. | LOW |

## Project Structure

```
comfyui-nodes/
  __init__.py              # NODE_CLASS_MAPPINGS + NODE_DISPLAY_NAME_MAPPINGS
  requirements.txt         # Only YOUR dependencies (croniter, piexif, mutagen)
  nodes/
    cron_scheduler.py      # CronScheduler node class
    pipeline_controller.py # PipelineController node class
    save_as.py             # SaveAs node class
    api_call.py            # ApiCall node class
    bulk_prompter.py       # BulkPrompter node class
  lib/
    prompt_mutations.py    # 6 mutation strategies (shared logic)
    tag_pipeline.py        # 3-layer tag generation
    filesystem_state.py    # Gap scanning, state management
    manifest.py            # CSV manifest + sidecar JSON
    fingerprint.py         # Workflow fingerprint + collision detection
    integrity.py           # File header validation, Pillow decode check
    naming.py              # Template-based naming engine
    retry.py               # Retry/fallback/skip/log strategy + strike counter
  web/                     # Optional: JS for custom UI widgets
    js/
      progress.js          # Progress display widget (if needed)
  data/
    word_banks/            # ~510 entries across 4 files
      adjectives.txt
      nouns.txt
      styles.txt
      modifiers.txt
  pyproject.toml           # Modern metadata (ComfyUI Registry uses this)
```

**Why this structure:**
- `nodes/` separates node classes from shared logic — each file = one node = easy to find
- `lib/` holds reusable logic that multiple nodes import. Critical for Bulk Prompter logic being callable from Pipeline Controller without node execution overhead (avoiding 74,850 no-op executions per PROJECT.md)
- `web/js/` is where ComfyUI looks for frontend extensions (auto-loaded)
- `__init__.py` at root is the **only** file ComfyUI reads for node registration

## ComfyUI Custom Node API Reference

### Required Class Attributes and Methods

```python
class MyNode:
    """Every ComfyUI node must define these."""

    # --- Required ---
    CATEGORY = "Pipeline Automation"      # Menu category in ComfyUI UI
    FUNCTION = "execute"                   # Method name ComfyUI calls
    RETURN_TYPES = ("IMAGE", "STRING")     # Output type tuple
    RETURN_NAMES = ("image", "status")     # Output name tuple

    @classmethod
    def INPUT_TYPES(cls):
        """Define node inputs. Called once at registration."""
        return {
            "required": {
                "param_name": ("STRING", {"default": "value"}),
                "number": ("INT", {"default": 0, "min": 0, "max": 100}),
                "image": ("IMAGE",),       # Receives from other nodes
            },
            "optional": {
                "opt_param": ("STRING", {"default": ""}),
            },
            "hidden": {
                "prompt": "PROMPT",         # Full workflow prompt data
                "unique_id": "UNIQUE_ID",   # This node's unique ID
                "extra_pnginfo": "EXTRA_PNGINFO",  # Workflow metadata
            },
        }

    def execute(self, param_name, number, image, opt_param="", **kwargs):
        """Main execution. Return tuple matching RETURN_TYPES."""
        return (result_image, status_string)

    # --- Optional but important ---
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Return value that changes when node should re-execute.
        ComfyUI caches results; return float('nan') to ALWAYS re-execute.
        Critical for: CRON Scheduler (time-dependent), Pipeline Controller (state-dependent)."""
        return float('nan')  # Never cache

    OUTPUT_NODE = True  # Set for nodes with side effects (Save As, Pipeline Controller)
```

### Node Registration (__init__.py)

```python
from .nodes.cron_scheduler import CronScheduler
from .nodes.pipeline_controller import PipelineController
from .nodes.save_as import SaveAs
from .nodes.api_call import ApiCall
from .nodes.bulk_prompter import BulkPrompter

NODE_CLASS_MAPPINGS = {
    "CronScheduler": CronScheduler,
    "PipelineController": PipelineController,
    "SaveAs": SaveAs,
    "ApiCall": ApiCall,
    "BulkPrompter": BulkPrompter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CronScheduler": "CRON Scheduler",
    "PipelineController": "Pipeline Controller",
    "SaveAs": "Save As",
    "ApiCall": "API Call",
    "BulkPrompter": "Bulk Prompter",
}

WEB_DIRECTORY = "./web"  # Optional: for frontend JS extensions

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
```

### PromptServer API Routes (for progress visibility)

```python
from aiohttp import web
from server import PromptServer

@PromptServer.instance.routes.get("/pipeline/status")
async def get_pipeline_status(request):
    """Custom API route for pipeline progress monitoring."""
    return web.json_response({"status": "running", "progress": 42})

@PromptServer.instance.routes.post("/pipeline/control")
async def control_pipeline(request):
    """Pause/resume/cancel pipeline."""
    data = await request.json()
    return web.json_response({"ok": True})
```

### Re-queuing via ComfyUI API (CRON Scheduler / Pipeline Controller)

```python
import urllib.request
import json

def queue_prompt(prompt_data, server_address="127.0.0.1:8188"):
    """Queue a workflow for execution via ComfyUI's built-in API."""
    data = json.dumps({"prompt": prompt_data}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{server_address}/prompt",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)

def is_queue_busy(server_address="127.0.0.1:8188"):
    """Check if ComfyUI queue has pending items (skip-if-busy guard)."""
    resp = urllib.request.urlopen(f"http://{server_address}/queue")
    data = json.loads(resp.read())
    return len(data.get("queue_running", [])) > 0 or len(data.get("queue_pending", [])) > 0
```

### ComfyUI Data Types

| Type String | Python Type | Notes |
|-------------|-------------|-------|
| `IMAGE` | `torch.Tensor` (B,H,W,C) float32 [0,1] | Batch dimension always present |
| `MASK` | `torch.Tensor` (B,H,W) float32 [0,1] | No channel dimension |
| `LATENT` | `dict` with `"samples"` key | Contains latent tensor |
| `STRING` | `str` | Use `{"multiline": True}` for text areas |
| `INT` | `int` | Supports min/max/step/default |
| `FLOAT` | `float` | Supports min/max/step/default |
| `BOOLEAN` | `bool` | Toggle |
| `COMBO` | `str` (from list) | `(["opt1", "opt2"],)` syntax |
| `*` | Any | Wildcard type — accepts anything |

## ComfyUI Registry (pyproject.toml)

For publishing to the ComfyUI Node Registry (comfyregistry.org):

```toml
[project]
name = "comfyui-pipeline-automation"
description = "Automated large-scale image generation pipeline for ComfyUI"
version = "1.0.0"
license = { file = "LICENSE" }
requires-python = ">=3.10"
dependencies = [
    "croniter>=2.0,<4.0",
    "piexif>=1.1.3",
    "mutagen>=1.47",
]

[project.urls]
Repository = "https://github.com/OWNER/comfyui-pipeline-automation"

[tool.comfy]
PublisherId = "your-publisher-id"
DisplayName = "Pipeline Automation"
Icon = ""
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Cron parsing | `croniter` | `apscheduler` | apscheduler is a full scheduler daemon with threading/async. You only need "parse cron expression, compute next run time." croniter is 1/10th the weight. |
| Cron parsing | `croniter` | Manual parsing | Cron syntax has edge cases (day-of-week + day-of-month interaction, leap seconds). Don't reinvent. |
| HTTP client | `urllib.request` (stdlib) | `requests` | Adds a dependency for minimal benefit. API Call node does sequential REST calls — urllib handles this. Add requests later only if you need session cookies or complex auth. |
| HTTP client | `urllib.request` | `httpx` | Async HTTP is unnecessary. Nodes execute synchronously in ComfyUI's execution engine. Async would require restructuring that fights ComfyUI's design. |
| Image metadata | `piexif` + Pillow PNG text chunks | `exiftool` (subprocess) | exiftool is a Perl binary — massive system dependency. piexif is pure Python for JPEG. Pillow handles PNG metadata natively via PngInfo. |
| State management | Filesystem (os/pathlib) | SQLite | PROJECT.md explicitly rules out databases. Filesystem-as-state is a design decision, not a limitation. |
| State management | Filesystem | Redis/memcached | Out of scope per PROJECT.md. External services are explicitly excluded. |
| Task scheduling | ComfyUI `/prompt` API re-queuing | Celery/RQ | ComfyUI IS the task queue. Re-queuing via its own API is the correct pattern. External task queues would fight ComfyUI's execution model. |
| Logging | Python `logging` stdlib | `loguru` | Adds a dependency. stdlib logging integrates with ComfyUI's existing logging setup. Use `logging.getLogger("pipeline_automation")` for namespaced logs. |
| Config format | JSON files | YAML/TOML | JSON is stdlib (no dependencies). Config files are simple key-value. YAML adds PyYAML dependency for no benefit. |
| Prompt templating | Python f-strings + `str.format_map` | Jinja2 | Naming templates are simple variable substitution (`{topic}_{resolution}_{index}`). Jinja2 is a heavyweight dependency for a trivial use case. |

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| `torch` (directly) | Your nodes orchestrate and save — they don't do inference. Don't import torch in node code unless converting between IMAGE tensors and PIL. If needed, import lazily. |
| `asyncio` in node execution | ComfyUI nodes execute synchronously in the main execution thread. Using asyncio inside `execute()` creates event loop conflicts. The CRON scheduler should use ComfyUI's `/prompt` API, not async timers. |
| Threading for parallelism | ComfyUI manages its own execution threading. Spawning threads from nodes causes race conditions with ComfyUI's caching and execution graph. |
| `watchdog` (filesystem watcher) | You don't need real-time filesystem watching. Pipeline Controller scans on each execution cycle. Polling on each queue iteration is simpler and more predictable. |
| Database ORMs (SQLAlchemy, etc.) | Filesystem is state. This is a design decision per PROJECT.md. |
| `click`/`argparse` | Nodes have no CLI. All configuration is via INPUT_TYPES widget parameters. |
| Type-checking at runtime (`pydantic`) | ComfyUI handles type validation via INPUT_TYPES. Adding pydantic creates import overhead for every node load. Use simple dataclasses or plain dicts. |

## Installation

```bash
# In ComfyUI/custom_nodes/ directory:
git clone <repo-url> comfyui-pipeline-automation
cd comfyui-pipeline-automation
pip install -r requirements.txt
```

### requirements.txt

```
croniter>=2.0,<4.0
piexif>=1.1.3
mutagen>=1.47
```

**Note:** Pillow, numpy, torch, and aiohttp are NOT listed because ComfyUI already provides them. Listing them risks version conflicts.

## Development Tools (Not Runtime Dependencies)

| Tool | Purpose | Why |
|------|---------|-----|
| `pytest` | Unit testing lib/ logic | Test mutation strategies, naming templates, manifest generation offline without ComfyUI running |
| `ruff` | Linting + formatting | Fast, replaces flake8+black+isort. Single tool. |
| `pyright` / `mypy` | Type checking | Optional but helpful for the lib/ layer where interfaces matter |

## Key Implementation Notes

1. **IS_CHANGED is critical.** CRON Scheduler and Pipeline Controller must return `float('nan')` from IS_CHANGED to prevent ComfyUI from caching their results. Without this, the scheduler runs once and never again.

2. **OUTPUT_NODE = True** is required for nodes with side effects (saving files, queuing prompts). Without it, ComfyUI may skip execution if no downstream node consumes the output.

3. **Hidden inputs** (`prompt`, `unique_id`, `extra_pnginfo`) give you access to the full workflow data — essential for workflow fingerprinting and metadata embedding.

4. **Server address discovery:** ComfyUI's PromptServer exposes `PromptServer.instance.port`. Use this instead of hardcoding 8188.

5. **Image format:** ComfyUI passes images as `torch.Tensor` with shape (B,H,W,C), dtype float32, range [0,1]. Convert to PIL with: `Image.fromarray((tensor[0].cpu().numpy() * 255).astype(np.uint8))`.

6. **Error handling in nodes:** If your node raises an exception, ComfyUI shows it in the UI and stops that execution. For batch pipelines, catch exceptions inside execute() and return error status strings instead of raising.

## Sources

- ComfyUI official repository: https://github.com/comfyanonymous/ComfyUI
- ComfyUI docs: https://docs.comfy.org
- ComfyUI example custom nodes: https://github.com/comfyanonymous/ComfyUI/tree/master/custom_nodes/example_node.py.example
- PROJECT.md constraints and decisions
- **Confidence note:** Web verification tools were unavailable during research. Library versions are based on training data (cutoff ~May 2025). Verify `croniter`, `piexif`, and `mutagen` latest versions before pinning in requirements.txt.
