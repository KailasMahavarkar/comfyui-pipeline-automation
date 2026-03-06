# Domain Pitfalls

**Domain:** ComfyUI custom node pack -- pipeline automation with background threads, filesystem state, cron scheduling, and large-scale batch processing
**Researched:** 2026-03-06
**Confidence:** MEDIUM (based on ComfyUI architecture knowledge and common patterns in long-running Python automation; web verification tools were unavailable during this research session)

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or production-blocking issues.

---

### Pitfall 1: IS_CHANGED Returning Mutable/Unhashable Values

**What goes wrong:** ComfyUI's execution engine caches node outputs and uses `IS_CHANGED` to decide whether to re-execute. The return value is compared to the previous return value. If `IS_CHANGED` returns a mutable object (dict, list) or an unhashable type, the comparison can silently fail, causing the node to either always re-execute (wasting cycles) or never re-execute (stale state).

**Why it happens:** The `IS_CHANGED` classmethod is poorly documented. Developers return complex objects when they should return simple hashable scalars (str, int, float). The `float("nan")` trick (NaN != NaN, so always triggers re-execution) works but has a subtlety: if you accidentally return it from a node that SHOULD cache (like Save As), you force unnecessary downstream re-execution.

**Consequences:**
- Pipeline Controller returns stale gap index -- generates the same image repeatedly instead of advancing
- CRON Scheduler never re-executes, pipeline appears frozen
- At 75,000 items, even subtle caching bugs compound into hours of wasted GPU time

**Prevention:**
- Pipeline Controller: `IS_CHANGED` returns the current gap index (int) -- changes on every successful save, forcing re-scan
- CRON Scheduler: `IS_CHANGED` returns `float("nan")` -- always re-executes (it must check cron timing every run)
- Save As: Do NOT implement `IS_CHANGED` -- let ComfyUI's default caching handle it (it re-executes when inputs change)
- Bulk Prompter / API Call (standalone): Do NOT implement `IS_CHANGED` unless they need forced re-execution
- Write unit tests that verify IS_CHANGED return types are hashable scalars

**Detection:**
- Pipeline appears to generate the same file repeatedly (check filenames in log)
- Status output shows same gap index across multiple CRON ticks
- ComfyUI console shows "cached" for nodes that should be running

**Phase:** Phase 3 (Pipeline Nodes) -- this is where IS_CHANGED logic gets implemented for Controller and CRON

---

### Pitfall 2: Background Thread Lifecycle Mismanagement

**What goes wrong:** The CRON Scheduler spawns a daemon thread. If thread lifecycle is not carefully managed, you get: zombie threads that survive node re-execution, multiple threads scheduling simultaneously, threads that hold references to stale node state, or threads that prevent clean ComfyUI shutdown.

**Why it happens:** ComfyUI re-executes nodes by calling the main function again. It does NOT destroy and recreate the Python class instance -- class instances persist. So if the CRON node's execute method spawns a thread on each run without killing the previous one, threads accumulate. Python's GIL doesn't protect you here because threads are doing I/O (HTTP calls to /prompt), not CPU work.

**Consequences:**
- Multiple CRON threads fire simultaneously, queuing duplicate workflows
- Skip-if-busy guard sees its OWN queued prompt as "busy," creating a deadlock where nothing ever runs
- Stale thread references prevent garbage collection, causing memory leaks over 24+ hour runs
- On ComfyUI restart, old threads may briefly overlap with new ones

**Prevention:**
- Use a module-level singleton pattern for the scheduler thread, NOT instance-level:
  ```python
  _scheduler_thread = None
  _scheduler_lock = threading.Lock()
  ```
- Before spawning a new thread, acquire the lock, set a stop event on the old thread, join it (with timeout), THEN spawn the new one
- Use `threading.Event` for stop signaling, not boolean flags (Event is thread-safe, booleans are not atomic in practice)
- Set `daemon=True` so threads die when ComfyUI exits
- Add a thread health check: if the thread is alive but hasn't ticked in 2x the cron interval, log a warning and restart it

**Detection:**
- Multiple "Re-queuing workflow" log messages per cron tick
- Queue pile-up visible in ComfyUI's queue panel
- Memory usage climbs steadily over hours
- `threading.enumerate()` shows multiple scheduler threads

**Phase:** Phase 3 (CRON Scheduler node)

---

### Pitfall 3: Race Condition Between Scanner and Save

**What goes wrong:** Pipeline Controller scans the filesystem and identifies a gap. It outputs parameters for that gap. KSampler generates the image. Save As writes the file. But between the scan and the save, another process (or a rapid CRON re-queue) could also target the same gap. The result: duplicate work, file overwrites, or counter drift.

**Why it happens:** The filesystem scan and the file save are not atomic. With the skip-if-busy guard, this SHOULDN'T happen (only one workflow runs at a time). But edge cases exist: the queue check races with the prompt submission, or ComfyUI's internal execution pipeline has multiple prompts in flight.

**Consequences:**
- Two runs target the same gap, one overwrites the other (lost work)
- Counter desync between in-memory cache and filesystem reality
- Manifest CSV gets duplicate entries
- At scale, 1% duplicate rate = 750 wasted generations

**Prevention:**
- The skip-if-busy guard is the PRIMARY defense -- make it robust: check BOTH `queue_running` AND `queue_pending` from `/queue` response
- Save As should use atomic writes: write to a temp file (`{filename}.tmp`), then `os.rename()` to final path (rename is atomic on most filesystems)
- Pipeline Controller's in-memory file cache should be updated AFTER save confirmation, not before
- Add a file-exists check in Save As before writing -- if the target file already exists and passes integrity check, skip silently and log
- Manifest CSV appends should use file locking (`fcntl.flock` on Unix, `msvcrt.locking` on Windows) or a dedicated writer thread with a queue

**Detection:**
- Manifest CSV has duplicate rows for the same topic/variant/resolution
- File modification timestamps show two writes within seconds
- Progress counter jumps backward

**Phase:** Phase 1 (lib/scanner.py, lib/manifest.py) and Phase 2 (Save As node)

---

### Pitfall 4: Filesystem Scan Performance at Scale

**What goes wrong:** Scanning 75,000 files across 150 topics x 10 resolutions = 1,500 directories on every CRON tick becomes a bottleneck. On spinning disks or network drives, a full scan can take 10-30 seconds. This blocks the ComfyUI execution thread, making the UI unresponsive.

**Why it happens:** The build plan mentions "incremental scan optimization" but the implementation details matter enormously. A naive `os.listdir()` or `os.walk()` of 1,500 directories with 50 files each means 75,000 stat calls per scan. On Windows (NTFS), directory enumeration is slower than Linux (ext4). On network mounts, it's catastrophically slow.

**Consequences:**
- ComfyUI UI freezes for 10-30 seconds on each CRON tick
- Users think the application has crashed
- On network drives, scans can timeout, causing the entire pipeline to stall
- Full Pillow decode on restart (Level 3 integrity) for "files modified in the last hour" could mean thousands of files after an overnight run

**Prevention:**
- Build the incremental cache as a serialized state file (`.scan_cache.json`) that persists across restarts, not just in-memory
- On restart, load the cache, then ONLY scan directories with modification times newer than the cache timestamp
- Use `os.scandir()` instead of `os.listdir()` -- it returns DirEntry objects with cached stat info, 2-10x faster
- For Level 3 integrity on restart, cap the number of files validated (e.g., last 100 files, not "all files from last hour")
- Run the full initial scan in a background thread, serving a "scanning..." status until ready
- Consider writing a `.last_completed` marker file after each save -- on restart, only scan from that point forward

**Detection:**
- ComfyUI UI becomes unresponsive at the start of each generation cycle
- First run after restart takes minutes before producing any output
- Log shows "Scanning..." for extended periods

**Phase:** Phase 1 (lib/scanner.py) -- this must be designed correctly from the start, retrofitting is painful

---

### Pitfall 5: PromptServer Route Registration Conflicts

**What goes wrong:** Custom API routes registered via `PromptServer.instance.routes` can conflict with other custom nodes that register the same path, with future ComfyUI routes, or can fail silently if registered at the wrong time in the server lifecycle.

**Why it happens:** ComfyUI's `PromptServer` uses aiohttp. Routes are registered during node module import (in `__init__.py` or at module level). If two node packs register `GET /pipeline/status`, the second one silently wins. There's no namespace isolation. Additionally, if the route handler references node state that hasn't been initialized yet, you get NoneType errors on first request.

**Consequences:**
- Route silently overwritten by another node pack -- monitoring appears to work but returns wrong data
- NoneType errors when polling `/pipeline/status` before any pipeline run has started
- aiohttp route registration errors on ComfyUI startup break ALL custom nodes in the pack

**Prevention:**
- Use a namespaced route path: `/pipeline-automation/status` instead of `/pipeline/status`
- Register routes in a try/except block that logs but doesn't crash -- route registration failure should never prevent nodes from working
- Route handlers must handle the "no pipeline running" state gracefully -- return `{"status": "idle", "message": "No pipeline active"}` instead of crashing
- Store pipeline state in a module-level dict, not on node instances (instances may not exist when route is called)
- Add a simple health check route: `GET /pipeline-automation/health` that always returns 200

**Detection:**
- HTTP 500 errors when polling the status endpoint
- Status endpoint returns data from a different node pack
- ComfyUI startup logs show route registration warnings

**Phase:** Phase 4 (Progress & Polish) -- but the module-level state pattern must be established in Phase 3

---

### Pitfall 6: Cross-Platform Filesystem Assumptions

**What goes wrong:** Code that works on Linux fails on Windows (or vice versa) due to path separator differences, filename character restrictions, case sensitivity, file locking behavior, and maximum path length limits.

**Why it happens:** The pipeline generates deeply nested paths like `output/realistic_landscapes/sunset_beach/512x512/sunset_beach_512x512_023.json`. On Windows, the default max path is 260 characters. Topic names from user input may contain characters illegal on Windows (`<>:"/\|?*`). NTFS is case-insensitive but case-preserving, so `Sunset_Beach` and `sunset_beach` are the same directory.

**Consequences:**
- `FileNotFoundError` or `OSError` on Windows with long paths
- Silent file overwrites when topics differ only by case on Windows
- Path separator bugs when constructing URLs for API responses vs filesystem paths
- Atomic rename (`os.rename`) behavior differs: on Windows, it fails if the target exists; on Linux, it overwrites

**Prevention:**
- Use `pathlib.Path` everywhere, never string concatenation for paths
- Sanitize topic names aggressively: lowercase, replace spaces with underscores, strip non-alphanumeric characters, truncate to 50 chars
- For atomic writes on Windows, use `os.replace()` instead of `os.rename()` (replace is atomic and overwrites on both platforms)
- Test the full path length at pipeline start -- if `output_root + workflow_name + longest_topic + resolution + filename` exceeds 250 chars, warn the user
- Add a path length validator in Pipeline Controller's execute method that runs before any generation starts

**Detection:**
- Errors only appear on Windows but not Linux (or vice versa)
- Topic names with special characters cause crashes
- Two topics that differ only by case produce merged/overwritten outputs

**Phase:** Phase 1 (lib/naming.py, lib/scanner.py) -- bake this in from the start

---

### Pitfall 7: Prompt Cache Corruption and Invalidation

**What goes wrong:** The `.prompt_cache/{topic}.json` files store generated prompts and tags. If these files get corrupted (partial write during crash), contain outdated data (user changed `prompts_per_topic` or `base_prompt_template`), or are deleted manually, the pipeline behavior becomes unpredictable.

**Why it happens:** The prompt cache is written once per topic on first encounter. But "first encounter" detection is based on file existence. If the user changes `prompts_per_topic` from 50 to 100, the cache still has 50 prompts. The pipeline will only generate 50 variants per topic instead of 100, with no warning. Similarly, if `base_prompt_template` changes, cached prompts use the old template.

**Consequences:**
- Pipeline generates fewer variants than expected (silent data loss)
- Old prompts persist after template changes, producing inconsistent outputs
- Corrupted cache file causes JSON parse error, blocking that topic entirely
- No way to regenerate prompts for a single topic without deleting the cache file manually

**Prevention:**
- Include a hash of the generation parameters (`base_prompt_template`, `prompts_per_topic`, strategy config) in the cache file
- On each run, compare the stored hash to current parameters. Mismatch = regenerate cache for that topic (with a log warning)
- Write cache files atomically (write to `.tmp`, then rename)
- Wrap all cache reads in try/except with a "regenerate on corruption" fallback
- Add a `force_regenerate_prompts` input (or tie it to `reset_workflow`) for explicit cache clearing
- Store the cache schema version in the file so future code changes can migrate old caches

**Detection:**
- `prompts_per_topic` doesn't match the number of variants being generated
- Changing `base_prompt_template` has no visible effect on output prompts
- JSON decode errors in the log for specific topics

**Phase:** Phase 1 (lib/bulk_prompter.py cache logic) and Phase 3 (Pipeline Controller)

---

## Moderate Pitfalls

---

### Pitfall 8: ComfyUI Execution Thread Blocking

**What goes wrong:** Node execute methods run on ComfyUI's main execution thread. Any blocking operation (network call, heavy filesystem I/O, sleep) in execute() freezes the entire ComfyUI UI and blocks other workflows.

**Prevention:**
- LLM API calls for tag generation should have aggressive timeouts (10s connect, 30s read)
- Never use `time.sleep()` in execute methods -- the CRON sleep belongs in the background thread only
- Filesystem scanning should be bounded (see Pitfall 4)
- If a single execute() call takes >5 seconds consistently, consider moving the heavy work to a background thread and having the node poll for results (but this conflicts with ComfyUI's synchronous execution model, so prefer making operations faster instead)

**Phase:** Phase 3 (Pipeline Controller execute method)

---

### Pitfall 9: Memory Leaks in Long-Running Sessions

**What goes wrong:** Over a 24+ hour run generating 75,000 images, in-memory data structures grow unbounded. The incremental file cache, the prompt cache, log buffers, and metadata dicts accumulate without cleanup.

**Prevention:**
- The in-memory file existence cache (set of known files) is legitimately large at scale: 75K strings x ~100 chars = ~7.5MB. This is acceptable.
- But don't cache file CONTENTS in memory -- only paths/existence
- Don't accumulate metadata dicts from previous runs -- each execute() should build fresh metadata for the current gap only
- Log file writes should flush immediately (`file.flush()`) and not buffer in memory
- Use `__del__` or `atexit` handlers cautiously -- they're unreliable in Python. Prefer explicit cleanup in the stop/disable path.
- Profile memory usage during the Phase 5 long-running test with a 1000-item batch before attempting 75K

**Phase:** Phase 5 (Long-running test) -- but design with this in mind from Phase 1

---

### Pitfall 10: Manifest CSV Concurrent Write Corruption

**What goes wrong:** If manifest CSV is appended without file locking and two processes (or a rapid re-queue race) write simultaneously, rows interleave and the CSV becomes unparseable.

**Prevention:**
- Use a threading lock for all manifest writes (module-level `_manifest_lock = threading.Lock()`)
- Open the file in append mode with line buffering (`open(path, 'a', buffering=1)`)
- Write the complete row as a single `file.write()` call (not multiple writes for fields)
- On Windows, be aware that file locking semantics differ from Unix -- `msvcrt.locking` is advisory, not mandatory
- Consider using a write queue: buffer rows and flush every N writes or every T seconds

**Phase:** Phase 1 (lib/manifest.py)

---

### Pitfall 11: Workflow Fingerprint False Positives

**What goes wrong:** The fingerprint is too sensitive or too loose. Too sensitive: adding a Display node for debugging changes the fingerprint, blocking the pipeline. Too loose: swapping SDXL for SD1.5 doesn't change the fingerprint, allowing incompatible outputs to mix.

**Prevention:**
- Include in fingerprint: checkpoint/model names, LoRA names, node types that affect generation (KSampler, CLIP, VAE), workflow_name
- Exclude from fingerprint: Display nodes, Preview nodes, Reroute nodes, Note/comment nodes, any node with `OUTPUT_NODE = True` that isn't Save As
- Exclude: all parameter values (seeds, steps, CFG, prompts) -- these change constantly
- Document exactly what's included/excluded so users understand why they're getting blocked
- The error message must be actionable (the build plan already gets this right -- keep that format)

**Phase:** Phase 1 (lib/fingerprint.py)

---

### Pitfall 12: Node Registration Breaking Other Custom Nodes

**What goes wrong:** Errors in `__init__.py` during node registration (import errors, missing dependencies, syntax errors) prevent ALL nodes in the pack from loading. Worse, some errors can crash ComfyUI's custom node loading entirely, affecting other installed node packs.

**Prevention:**
- Wrap each node import in `__init__.py` with individual try/except blocks:
  ```python
  NODE_CLASS_MAPPINGS = {}
  try:
      from .save_as import SaveAsNode
      NODE_CLASS_MAPPINGS["SaveAs"] = SaveAsNode
  except Exception as e:
      print(f"[Pipeline Automation] Failed to load SaveAs: {e}")
  ```
- Check for optional dependencies (mutagen, piexif) at import time and gracefully disable features that need them
- Never do heavy initialization at import time -- defer to first execute() call
- Test node loading with `python -c "import comfyui_pipeline_automation"` in CI

**Phase:** Phase 2 (when __init__.py is first created)

---

### Pitfall 13: Metadata Embedding Failures Silently Dropping Data

**What goes wrong:** Pillow's PNG tEXt chunk API, piexif for JPEG, mutagen for audio -- each has different size limits, encoding requirements, and failure modes. Large metadata blobs get silently truncated. Unicode characters in prompts cause encoding errors. Some formats don't support the expected metadata fields at all.

**Prevention:**
- PNG tEXt chunks: limit total metadata to <1MB (PNG spec allows it but some viewers choke)
- JPEG EXIF ImageDescription: limited to ~64KB. If metadata exceeds this, truncate the prompt and log a warning
- Always encode metadata as UTF-8 and handle encoding errors with `errors='replace'`
- Test metadata embedding with prompts containing: emoji, CJK characters, very long prompts (>4KB), special characters like quotes and backslashes
- After writing, immediately read back the metadata and verify it round-trips correctly (at least in tests, not in production)
- Fall back to sidecar JSON if embedded metadata fails -- never lose metadata silently

**Phase:** Phase 1 (lib/metadata.py) and Phase 2 (Save As node)

---

### Pitfall 14: The /queue Busy Check Race Window

**What goes wrong:** CRON Scheduler checks `/queue`, sees it's empty, submits a new prompt. But between the check and the submission, another source (user clicking "Queue Prompt", another scheduler instance, an API client) also submits. Now two prompts are running.

**Prevention:**
- Accept this as a known edge case with low probability -- document it
- Make the pipeline idempotent: if two runs target the same gap, the second one should detect the file already exists (written by the first) and skip
- Save As's file-exists check (Pitfall 3) is the safety net here
- Do NOT try to solve this with complex locking -- the cure would be worse than the disease

**Phase:** Phase 3 (CRON Scheduler)

---

## Minor Pitfalls

---

### Pitfall 15: Word Bank File Encoding Issues

**What goes wrong:** Word bank .txt files saved with BOM markers, Windows line endings, or non-UTF-8 encoding cause parsing failures or invisible characters in prompts.

**Prevention:**
- Read all word bank files with `open(path, 'r', encoding='utf-8-sig')` (handles BOM transparently)
- Strip `\r` from line endings explicitly
- Ship word bank files as UTF-8 without BOM in the repository
- Validate word bank entries on load: strip whitespace, skip blank lines, warn on non-ASCII characters

**Phase:** Phase 1 (lib/bulk_prompter.py)

---

### Pitfall 16: Counter Desync After Manual File Deletion

**What goes wrong:** User manually deletes some output files to re-generate them. The in-memory file cache still thinks they exist. The pipeline skips those gaps until the next full rescan (restart).

**Prevention:**
- On each CRON tick, Pipeline Controller should check if the last-generated file still exists before advancing. If not, trigger a targeted rescan of the current topic/resolution directory.
- The periodic full rescan interval should be configurable (e.g., every 100 iterations)
- Document clearly: "To re-generate specific files, delete them and restart ComfyUI (or wait for the next full rescan)"

**Phase:** Phase 3 (Pipeline Controller)

---

### Pitfall 17: CRON Expression Validation

**What goes wrong:** Invalid cron expressions (`*/0 * * * *`, `61 * * * *`, `* * * * * *` with 6 fields) cause croniter to throw exceptions, crashing the scheduler thread silently.

**Prevention:**
- Validate the cron expression in `INPUT_TYPES` or at the start of execute(), before spawning the thread
- Wrap `croniter()` construction in try/except with a clear error message
- Default to the safe preset (`*/5 * * * *`) if custom expression is invalid
- The presets (Every 1 min, Every 5 min, etc.) bypass validation since they're hardcoded and known-good

**Phase:** Phase 3 (CRON Scheduler)

---

### Pitfall 18: Strike Counter Persistence Across Parameter Changes

**What goes wrong:** A topic/variant fails 3 times and gets marked as "skipped" in `.failures.json`. User fixes the underlying issue (e.g., changes checkpoint, adjusts prompt). The strike counter still shows 3 strikes, so the entry is permanently skipped.

**Prevention:**
- Include a hash of relevant generation parameters in the strike counter entry
- When parameters change (detected via hash mismatch), reset strikes for affected entries
- Alternatively, tie strike reset to `reset_workflow` toggle
- Add a "clear strikes" option or auto-clear strikes older than 24 hours

**Phase:** Phase 1 (strike counter logic in lib/scanner.py) and Phase 3 (Pipeline Controller)

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation |
|-------|---------------|------------|
| Phase 1: Foundation (lib/) | Pitfall 4 (scan performance), Pitfall 6 (cross-platform), Pitfall 7 (cache invalidation) | Design scanner with incremental caching from day one. Use pathlib everywhere. Include parameter hashes in prompt cache. |
| Phase 2: Standalone Nodes | Pitfall 12 (registration breaking), Pitfall 13 (metadata embedding) | Isolate node imports with try/except. Test metadata round-trip with edge-case strings. |
| Phase 3: Pipeline Nodes | Pitfall 1 (IS_CHANGED), Pitfall 2 (thread lifecycle), Pitfall 3 (race conditions) | Write IS_CHANGED tests early. Use singleton thread pattern. Implement atomic writes. |
| Phase 4: Progress & Polish | Pitfall 5 (route conflicts) | Use namespaced routes. Handle "no pipeline running" state. |
| Phase 5: Hardening | Pitfall 9 (memory leaks), Pitfall 14 (queue race) | Profile memory during long runs. Verify idempotency under concurrent queue submissions. |

---

## Sources

- ComfyUI source code analysis (execution engine caching, PromptServer aiohttp routes, node lifecycle)
- Python threading documentation (daemon threads, Event signaling, GIL behavior for I/O-bound threads)
- NTFS vs ext4 filesystem behavior (path length limits, case sensitivity, atomic rename semantics)
- PIL/Pillow metadata embedding limitations (PNG tEXt chunks, EXIF size limits)
- aiohttp route registration patterns
- General production batch processing patterns (idempotency, atomic writes, crash recovery)

**Confidence note:** These pitfalls are derived from ComfyUI architecture knowledge and general Python/systems engineering experience. Web-based verification was unavailable during this research session. The pitfalls specific to ComfyUI's IS_CHANGED behavior, PromptServer routing, and node execution lifecycle are MEDIUM confidence -- they should be verified against ComfyUI's current source code before implementation.
