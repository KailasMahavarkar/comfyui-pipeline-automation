# Architecture Patterns

**Domain:** ComfyUI Custom Node Pack (Pipeline Automation)
**Researched:** 2026-03-06
**Confidence:** MEDIUM-HIGH (based on ComfyUI node API conventions and detailed build plan; web verification tools unavailable during this session)

## ComfyUI Execution Model

Understanding ComfyUI's execution model is prerequisite to every architectural decision in this project.

### How ComfyUI Executes Nodes

ComfyUI uses a **lazy, demand-driven DAG execution model**:

1. **Prompt submission:** The frontend sends the full workflow graph as JSON to `POST /prompt`.
2. **Topological sort:** The server walks the graph from output nodes backward, building an execution order based on data dependencies.
3. **Caching layer:** Each node's inputs are hashed. If a node's inputs haven't changed since the last run, it is skipped (cache hit). The `IS_CHANGED` classmethod overrides this -- returning a new value forces re-execution.
4. **Sequential execution:** Nodes execute one at a time in dependency order. There is no parallel node execution within a single prompt.
5. **One prompt = one pass:** A single `/prompt` call executes the graph exactly once. Looping requires re-queuing via the API.

**Critical implication for this project:** There is no built-in loop construct. The CRON Scheduler must re-queue the entire workflow via `POST /prompt` for each iteration. The Pipeline Controller must advance state externally (filesystem) because ComfyUI has no memory between prompt executions.

### Node Class Contract

Every ComfyUI custom node is a Python class with these required elements:

```python
class MyNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "param_name": ("TYPE", {"default": value}),
            },
            "optional": {
                "opt_param": ("TYPE", {}),
            },
            "hidden": {
                "prompt": "PROMPT",           # receives full workflow prompt
                "extra_pnginfo": "EXTRA_PNGINFO",  # workflow JSON for embedding
                "unique_id": "UNIQUE_ID",     # this node's unique ID
            },
        }

    RETURN_TYPES = ("STRING", "INT", "IMAGE")
    RETURN_NAMES = ("prompt", "width", "image")
    FUNCTION = "execute"           # method name ComfyUI calls
    CATEGORY = "pipeline"          # UI category
    OUTPUT_NODE = True             # marks as terminal (side effects allowed)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Return different value each time to bust cache
        return float("nan")

    def execute(self, param_name, opt_param=None):
        # Node logic here
        return (result_string, result_int, result_image)
```

### Key Mechanisms This Project Uses

| Mechanism | ComfyUI Feature | Used By |
|-----------|----------------|---------|
| Cache busting | `IS_CHANGED` returning `float("nan")` or changing value | CRON Scheduler, Pipeline Controller |
| Re-queuing | `POST /prompt` API with workflow JSON | CRON Scheduler |
| Queue checking | `GET /queue` API | CRON Scheduler (skip-if-busy) |
| Custom API routes | `PromptServer.instance.routes` (aiohttp) | Pipeline Controller (progress endpoint) |
| Workflow JSON access | `hidden: {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}` | Pipeline Controller (fingerprinting) |
| Side effects | `OUTPUT_NODE = True` | Save As, CRON Scheduler |
| Background threads | Python `threading.Thread(daemon=True)` | CRON Scheduler |

## Recommended Architecture

### System Boundary Diagram

```
+------------------------------------------------------------------+
|  ComfyUI Process                                                  |
|                                                                   |
|  +-----------------------+     +-----------------------------+    |
|  | ComfyUI Server        |     | Execution Engine            |    |
|  | (aiohttp)             |     |                             |    |
|  |                       |     |  Topological Sort           |    |
|  | /prompt  (queue work) |<--->|  Cache Check (IS_CHANGED)   |    |
|  | /queue   (check busy) |     |  Sequential Node Execution  |    |
|  | /pipeline/status (*)  |     |                             |    |
|  +-----------+-----------+     +----+----+----+----+----+----+    |
|              |                      |    |    |    |    |         |
|              |                      v    v    v    v    v         |
|  +-----------v-----------+     +----+----+----+----+----+----+    |
|  | CRON Background       |     | Node Execution Order:        |   |
|  | Thread (daemon)       |     |                              |   |
|  |                       |     |  1. CRON Scheduler           |   |
|  | - croniter schedule   |     |  2. Pipeline Controller      |   |
|  | - POST /prompt        |     |  3. CLIP Encode (pos)        |   |
|  | - GET /queue check    |     |  4. CLIP Encode (neg)        |   |
|  | - single instance     |     |  5. Empty Latent Image       |   |
|  +-----------------------+     |  6. KSampler                 |   |
|                                |  7. VAE Decode               |   |
|                                |  8. Save As                  |   |
|                                +------------------------------+   |
|                                                                   |
+------------------------------------------------------------------+
         |                    |
         v                    v
+------------------+   +------------------+
| Filesystem       |   | External APIs    |
| (State Store)    |   | (Optional)       |
|                  |   |                  |
| output/          |   | LLM API          |
|   {workflow}/    |   | (tag generation) |
|     .prompt_cache|   |                  |
|     .failures    |   |                  |
|     .fingerprint |   |                  |
|     .progress.log|   |                  |
|     {topic}/     |   |                  |
|       {res}/     |   |                  |
+------------------+   +------------------+
```

(*) Custom API route registered via PromptServer

### Component Boundaries

| Component | Responsibility | Communicates With | State |
|-----------|---------------|-------------------|-------|
| `cron_scheduler.py` | Background thread lifecycle, re-queuing via HTTP, skip-if-busy guard, done-signal handling | ComfyUI `/prompt` and `/queue` APIs, Pipeline Controller (via `is_complete` output) | Thread reference (module-level singleton) |
| `pipeline_controller.py` | Matrix computation, gap detection orchestration, prompt/tag generation orchestration, metadata assembly | All `lib/` modules, filesystem | In-memory file cache (reset on restart) |
| `save_as.py` | File writing, metadata embedding, sidecar/manifest writing | `lib/naming`, `lib/metadata`, `lib/sidecar`, `lib/manifest`, filesystem | Counter (per-session) |
| `api_call.py` | HTTP requests to external APIs, retry logic, response parsing | `lib/response_parser`, external HTTP endpoints | None (stateless) |
| `bulk_prompter_node.py` | Thin wrapper exposing `lib/bulk_prompter` as a standalone node | `lib/bulk_prompter` | None (stateless) |
| `lib/scanner.py` | Filesystem walking, plan-vs-reality diffing, file integrity validation | Filesystem only | Incremental cache (in-memory, per Pipeline Controller instance) |
| `lib/fingerprint.py` | Workflow hash computation, save/load/compare | Filesystem (`.workflow_fingerprint` file) | None |
| `lib/bulk_prompter.py` | Prompt mutation strategies, word bank loading | `word_banks/` directory | Loaded word banks (cached on first use) |
| `lib/tag_generator.py` | 3-layer tag pipeline, LLM integration | `lib/response_parser`, external LLM API | None |
| `lib/naming.py` | Template token resolution, preset mapping | None | Counter state |
| `lib/metadata.py` | Per-format metadata embedding (PNG tEXt, JPEG EXIF, etc.) | Pillow, piexif, mutagen | None |
| `lib/sidecar.py` | JSON sidecar file writing | Filesystem | None |
| `lib/manifest.py` | CSV append with thread safety | Filesystem | File lock |
| `lib/response_parser.py` | Dot-path JSON navigation, markdown stripping | None | None |

### Data Flow

#### Per-Execution Data Flow (Single Prompt Run)

```
1. ComfyUI calls CRON Scheduler.execute()
   - Starts/restarts background daemon thread (if enabled)
   - Returns: status string, passthrough image, is_complete flag
   - Background thread independently manages re-queuing

2. ComfyUI calls Pipeline Controller.execute()
   - Receives: workflow_name, topic_list, resolution_list, etc.
   - Hidden inputs: PROMPT (full workflow graph), EXTRA_PNGINFO (workflow JSON)

   Internal flow:
   a. fingerprint.compute(PROMPT) -> compare to .workflow_fingerprint -> block or allow
   b. scanner.scan(output_dir) -> find first gap in matrix
   c. If new topic:
      - bulk_prompter.generate(base_prompt, topic, N) -> cache to .prompt_cache/
      - tag_generator.generate(prompt, topic, llm_config) -> cache alongside
   d. Read cached prompt + tags for current gap
   e. Assemble metadata JSON

   Returns: prompt, negative_prompt, width, height, metadata (JSON), is_complete, status

3. Standard ComfyUI nodes process (CLIP, KSampler, VAE) -- no custom code involved

4. ComfyUI calls Save As.execute()
   - Receives: image tensor, metadata JSON, naming config

   Internal flow:
   a. naming.resolve(template, metadata) -> filename + subfolder
   b. Save image/audio/video to disk
   c. metadata.embed(file_path, format, tags+prompt) -> write metadata into file
   d. If sidecar enabled: sidecar.write(file_path, metadata_dict)
   e. If manifest enabled: manifest.append(csv_path, entry)

   Returns: saved_paths string
```

#### Background Thread Data Flow (CRON)

```
CRON Background Thread (daemon, runs independently of node execution):
  loop:
    1. Sleep until next cron tick (croniter)
    2. GET /queue -> check if busy
    3. If busy: skip, log warning
    4. If not busy: POST /prompt with saved workflow JSON
    5. Check is_complete flag (set during last execution) -> stop if done
    6. Check max_iterations -> stop if reached
```

#### State Flow (Cross-Execution Persistence)

```
Run N:
  Pipeline Controller scans filesystem -> finds gap at index 42
  Outputs params for entry 42
  Save As writes entry 42 to disk

Run N+1:
  Pipeline Controller scans filesystem -> entry 42 now exists -> finds gap at index 43
  Outputs params for entry 43
  Save As writes entry 43 to disk

(State advances via filesystem presence, not in-memory counters)
```

### Inter-Node Communication

ComfyUI nodes communicate **only through typed outputs wired to inputs**. There is no shared memory, no event bus, no direct method calls between nodes during execution.

| From | To | Via | Data |
|------|----|-----|------|
| CRON Scheduler | Pipeline Controller | No direct wire needed (both execute per-run) | CRON manages re-queuing; Controller manages state |
| Pipeline Controller | CLIP Encode (standard) | `prompt` STRING output | Generated prompt text |
| Pipeline Controller | CLIP Encode (standard) | `negative_prompt` STRING output | Negative prompt text |
| Pipeline Controller | Empty Latent (standard) | `width`, `height` INT outputs | Resolution for this entry |
| Pipeline Controller | Save As | `metadata` STRING output | Full JSON blob with tags, pipeline state, etc. |
| Pipeline Controller | CRON Scheduler | `is_complete` BOOLEAN output | Stop signal when all gaps filled |
| VAE Decode (standard) | Save As | `image` IMAGE output | Decoded image tensor |

**Important:** The `is_complete` signal from Pipeline Controller to CRON Scheduler flows through ComfyUI's wiring, but the CRON background thread reads it from the last execution's result. This means the CRON thread needs to store the last `is_complete` value at module level so the background thread can access it.

## Patterns to Follow

### Pattern 1: Module-Level Singleton for Background Threads

**What:** Use a module-level variable to ensure only one CRON daemon thread exists per ComfyUI session. Kill the old thread before starting a new one.

**When:** CRON Scheduler node -- any node that spawns background threads.

**Why:** ComfyUI may re-execute a node multiple times. Without a singleton, each execution spawns a new thread, causing duplicate re-queues.

```python
import threading

_scheduler_thread = None
_scheduler_stop_event = threading.Event()

class CRONScheduler:
    def execute(self, schedule, enabled, **kwargs):
        global _scheduler_thread, _scheduler_stop_event

        # Kill existing thread
        if _scheduler_thread and _scheduler_thread.is_alive():
            _scheduler_stop_event.set()
            _scheduler_thread.join(timeout=5)

        if not enabled:
            return ("OFF", None, False)

        _scheduler_stop_event = threading.Event()
        _scheduler_thread = threading.Thread(
            target=self._run_schedule,
            args=(schedule, _scheduler_stop_event),
            daemon=True  # dies when ComfyUI exits
        )
        _scheduler_thread.start()
        return (status, passthrough, is_complete)
```

### Pattern 2: IS_CHANGED for Stateful Nodes

**What:** Override `IS_CHANGED` to control when ComfyUI re-executes a node vs. using cached results.

**When:** Any node whose output should differ between runs even with identical inputs (Pipeline Controller, CRON Scheduler).

```python
class PipelineController:
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Option A: Always re-execute (use for CRON Scheduler)
        return float("nan")

        # Option B: Re-execute when state changes (use for Pipeline Controller)
        # Return the current gap index so it changes each run
        # return str(current_gap_index)
```

**Important subtlety:** `IS_CHANGED` receives the same keyword arguments as the main `FUNCTION`. It runs BEFORE execution to decide whether to use cache. For Pipeline Controller, returning `float("nan")` is safest -- the filesystem scan is the actual state check and it needs to run every time.

### Pattern 3: PromptServer API Routes via aiohttp

**What:** Register custom HTTP endpoints on ComfyUI's server for external monitoring.

**When:** Progress API route (`GET /pipeline/status`).

```python
from aiohttp import web
from server import PromptServer

# Register at module load time (not inside a node class)
@PromptServer.instance.routes.get("/pipeline/status")
async def get_pipeline_status(request):
    return web.json_response({
        "workflow_name": _current_status.get("workflow_name", ""),
        "progress": _current_status.get("progress", 0),
        "total": _current_status.get("total", 0),
        # ...
    })
```

**Important:** Routes are registered at import time (module level), not during node execution. The route handler reads from a module-level state dict that the Pipeline Controller updates during execution.

### Pattern 4: Hidden Inputs for Workflow Access

**What:** Use ComfyUI's hidden input mechanism to access the full workflow graph and metadata.

**When:** Pipeline Controller needs the workflow graph for fingerprinting and the workflow JSON for saving.

```python
@classmethod
def INPUT_TYPES(cls):
    return {
        "required": { ... },
        "hidden": {
            "prompt": "PROMPT",              # full node graph as dict
            "extra_pnginfo": "EXTRA_PNGINFO", # workflow JSON (for UI)
            "unique_id": "UNIQUE_ID",         # this node's ID
        },
    }
```

### Pattern 5: OUTPUT_NODE for Side-Effect Nodes

**What:** Mark nodes that perform side effects (file writing, HTTP calls) as output nodes.

**When:** Save As (writes files), CRON Scheduler (spawns threads, makes HTTP calls).

**Why:** ComfyUI's execution engine only executes the subgraph that leads to output nodes. Without `OUTPUT_NODE = True`, a node with no downstream consumers will never execute.

```python
class SaveAs:
    OUTPUT_NODE = True
    # ...
```

### Pattern 6: Filesystem-as-State with Incremental Caching

**What:** Use file existence as the source of truth, but maintain an in-memory cache of known files for performance after the initial scan.

**When:** Pipeline Controller's gap detection across 75,000 potential entries.

```python
class Scanner:
    def __init__(self):
        self._known_files = set()  # in-memory cache
        self._initial_scan_done = False

    def scan(self, output_dir, planned_matrix):
        if not self._initial_scan_done:
            # Full walk on first call or after restart
            self._known_files = self._walk_directory(output_dir)
            self._initial_scan_done = True

        # Find first gap
        for entry in planned_matrix:
            if entry.path not in self._known_files:
                return entry  # first gap found

        return None  # all done

    def mark_complete(self, path):
        """Called by Save As after successful write"""
        self._known_files.add(path)
```

**Critical note:** The in-memory cache resets when ComfyUI restarts. This is correct behavior -- the filesystem scan on restart also performs integrity checking on recent files (Level 3 validation).

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing State in Node Instance Variables Across Executions

**What:** Relying on `self.some_counter` to persist between workflow executions.

**Why bad:** ComfyUI may or may not reuse the same node instance between executions. The execution engine creates nodes fresh in some scenarios. Instance state is unreliable for cross-execution persistence.

**Instead:** Use module-level variables for in-process state (thread references, caches) and filesystem for durable state (progress, completed work).

### Anti-Pattern 2: Blocking the Execution Thread for Long Operations

**What:** Making the node's `execute()` method block for minutes waiting on external APIs or heavy computation.

**Why bad:** ComfyUI executes nodes sequentially. A blocking node freezes the entire execution pipeline and prevents the UI from updating. For the LLM calls in tag generation, this is acceptable (they're short, ~2-5 seconds with retry), but never block indefinitely.

**Instead:** For the CRON scheduler's waiting, use a daemon background thread. For API calls, use timeouts (the 30-second default in API Call node). Never have an infinite wait in `execute()`.

### Anti-Pattern 3: Monkey-Patching ComfyUI Internals

**What:** Replacing or modifying ComfyUI's built-in classes, methods, or execution behavior.

**Why bad:** Breaks on ComfyUI updates, conflicts with other custom nodes, makes debugging nightmarish.

**Instead:** Use only the official extension points: `INPUT_TYPES`, `IS_CHANGED`, `PromptServer.instance.routes`, `OUTPUT_NODE`, hidden inputs, and the `/prompt` + `/queue` HTTP APIs.

### Anti-Pattern 4: Node-to-Node Communication Outside the Graph

**What:** Having nodes communicate through global variables, shared queues, or direct method calls bypassing ComfyUI's wiring system.

**Why bad:** Breaks ComfyUI's caching model, creates invisible dependencies, makes the graph non-portable.

**Instead:** All inter-node data flows through typed outputs wired to inputs. The one exception is module-level state for the CRON background thread and the progress API route, which exist outside the graph by necessity.

### Anti-Pattern 5: Writing to ComfyUI's Internal Directories

**What:** Storing state files in ComfyUI's `custom_nodes/` directory or other internal paths.

**Why bad:** Gets wiped on node updates, not portable, pollutes the codebase.

**Instead:** All runtime state goes under `output/{workflow_name}/` -- the user's output directory. Configuration and caches live alongside the generated outputs.

## Component Dependency Graph and Build Order

```
lib/response_parser.py          (no deps)          -- BUILD FIRST
lib/naming.py                   (no deps)          -- BUILD FIRST
lib/sidecar.py                  (no deps)          -- BUILD FIRST
lib/manifest.py                 (no deps)          -- BUILD FIRST
lib/fingerprint.py              (no deps)          -- BUILD FIRST
lib/metadata.py                 (pillow, piexif, mutagen)  -- BUILD FIRST
    |
    v
lib/bulk_prompter.py            (word_banks/)      -- BUILD SECOND
lib/tag_generator.py            (response_parser)  -- BUILD SECOND
lib/scanner.py                  (no lib deps)      -- BUILD SECOND
    |
    v
bulk_prompter_node.py           (lib/bulk_prompter)     -- BUILD THIRD
api_call.py                     (lib/response_parser)   -- BUILD THIRD
save_as.py                      (lib/naming, metadata, sidecar, manifest)  -- BUILD THIRD
    |
    v
pipeline_controller.py          (lib/scanner, fingerprint, bulk_prompter, tag_generator, naming)  -- BUILD FOURTH
cron_scheduler.py               (croniter, ComfyUI APIs)  -- BUILD FOURTH
    |
    v
__init__.py                     (all nodes)  -- BUILD LAST (but update incrementally)
API route registration          (PromptServer)  -- BUILD WITH PIPELINE CONTROLLER
```

**Build order rationale:**

1. **lib/ modules first** because they are pure Python with no ComfyUI dependency. They can be unit tested in isolation without running ComfyUI.
2. **Standalone nodes second** (Save As, API Call, Bulk Prompter) because they are simpler, independently useful, and validate that the lib/ modules work correctly within the ComfyUI node contract.
3. **Pipeline nodes last** (Pipeline Controller, CRON Scheduler) because they depend on nearly all lib/ modules and require the most complex integration with ComfyUI's execution model.

## Node Registration Pattern

The `__init__.py` file is the entry point ComfyUI uses to discover and load custom nodes:

```python
from .cron_scheduler import CRONScheduler
from .pipeline_controller import PipelineController
from .save_as import SaveAs
from .api_call import APICall
from .bulk_prompter_node import BulkPrompter

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

WEB_DIRECTORY = "./web"  # only if custom UI widgets are needed
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
```

**During development:** Register nodes incrementally. Phase 2 registers only Save As, API Call, and Bulk Prompter. Phase 3 adds Pipeline Controller and CRON Scheduler.

## Scalability Considerations

| Concern | At 100 files | At 10K files | At 75K files |
|---------|-------------|-------------|-------------|
| Filesystem scan | Instant (<50ms) | ~500ms full walk | ~3-5 seconds full walk; use incremental cache after first scan |
| Prompt cache | 1-3 topic files | 50-100 topic files | 150 topic files (~50KB each, trivial) |
| Manifest CSV | Tiny | ~500KB | ~4MB, append-only so no read overhead |
| Memory (in-memory file set) | Negligible | ~1MB | ~8-10MB for 75K path strings |
| Directory listing | Fast | Fast (flat per-resolution folder has max 50 files) | Fast -- the nested structure keeps per-directory counts low |

**The nested folder structure is critical for scalability.** `{topic}/{resolution}/` means no single directory ever has more than ~50 files (prompts_per_topic). Without nesting, 75,000 files in one directory would be catastrophically slow on Windows.

## Thread Safety Considerations

| Resource | Contention Risk | Mitigation |
|----------|----------------|------------|
| Manifest CSV | CRON re-queue could trigger concurrent writes | File lock (threading.Lock) in manifest.py |
| `.failures.json` | Read during scan, write after failure | Single-threaded execution model means no contention within a run; use atomic write (write temp, rename) for crash safety |
| `.progress.log` | Written by Pipeline Controller, read by tail/API | Append-only, no lock needed |
| CRON thread | Only one should exist | Module-level singleton with stop event |
| Module-level status dict | Written by Pipeline Controller, read by API route | Use threading.Lock or accept slightly stale reads (acceptable for monitoring) |

## Sources

- ComfyUI custom node API conventions (based on established patterns in the ComfyUI ecosystem)
- Project build plan (`build-plan.md` in repository root -- detailed specification document)
- ComfyUI execution model understanding (established community knowledge; unable to verify against current official docs due to tool restrictions during this session)

**Confidence notes:**
- HIGH confidence on node class contract (INPUT_TYPES, RETURN_TYPES, IS_CHANGED, OUTPUT_NODE, FUNCTION, CATEGORY) -- these are stable, well-established APIs
- HIGH confidence on PromptServer route registration pattern -- standard aiohttp
- HIGH confidence on filesystem-as-state architecture -- this is a design choice, not a framework dependency
- MEDIUM confidence on hidden input names ("PROMPT", "EXTRA_PNGINFO", "UNIQUE_ID") -- these are established but should be verified against current ComfyUI source
- MEDIUM confidence on exact IS_CHANGED behavior with `float("nan")` -- widely documented in community but verify against source
