# Project Research Summary

**Project:** ComfyUI Pipeline Automation Node Pack
**Domain:** ComfyUI custom node development -- batch image generation automation
**Researched:** 2026-03-06
**Confidence:** MEDIUM

## Executive Summary

This project is a ComfyUI custom node pack that automates large-scale image generation (75,000+ images) through five nodes: CRON Scheduler, Pipeline Controller, Save As, API Call, and Bulk Prompter. The domain is well-understood -- ComfyUI's custom node API is stable and the patterns for building node packs are established. The recommended approach is to build pure-Python library modules first (scanner, naming, fingerprinting, prompt mutation) that can be unit tested without ComfyUI, then wrap them in node classes, and finally wire up the complex orchestration (Pipeline Controller + CRON Scheduler) last. The stack is deliberately lightweight: Python 3.10+, croniter for cron parsing, piexif/mutagen for metadata, and everything else from ComfyUI's bundled dependencies or Python stdlib.

The core architectural bet is filesystem-as-state: file existence IS the progress database. This eliminates crash recovery as a separate concern (restart = rescan = resume) and makes the system inspectable with basic file tools. No existing node pack combines scheduled automation, filesystem state management, crash recovery, organized output with metadata, and prompt variation into a single integrated pipeline. The closest competitors (Impact-Pack, efficiency-nodes) handle batch as "run N times with randomness" -- this project handles batch as "systematically complete a matrix, survive any failure, make every output traceable."

The primary risks are: (1) filesystem scan performance at 75K files requiring incremental caching from day one, (2) CRON background thread lifecycle management causing zombie threads or duplicate queuing, (3) IS_CHANGED misuse causing nodes to cache when they should re-execute (or vice versa), and (4) cross-platform filesystem behavior differences between Windows and Linux. All four are well-understood problems with known solutions documented in the pitfalls research. None are blockers, but all must be addressed in their respective phases rather than retrofitted.

## Key Findings

### Recommended Stack

The stack is intentionally minimal. ComfyUI already provides Pillow, numpy, torch, and aiohttp. The only new pip dependencies are croniter (cron expression parsing), piexif (JPEG EXIF writing), and mutagen (audio metadata). Everything else uses Python stdlib: pathlib for filesystem, json for config/sidecar, csv for manifests, hashlib for fingerprinting, logging for structured logs, urllib.request for HTTP. See `.planning/research/STACK.md` for full details.

**Core technologies:**
- **Python 3.10+**: Must target 3.10 as floor -- many ComfyUI users run embedded Python from portable installs
- **croniter >=2.0**: Lightweight cron expression evaluation; apscheduler is overkill since we only need "when is next run?" math
- **piexif + Pillow PngInfo**: JPEG EXIF and PNG tEXt metadata embedding without heavyweight exiftool dependency
- **ComfyUI /prompt and /queue APIs**: Re-queuing and skip-if-busy via ComfyUI's own HTTP API, not external schedulers
- **pathlib (stdlib)**: All filesystem operations; critical for cross-platform correctness
- **ffmpeg (system)**: Audio/video encoding; already expected by ComfyUI video workflows

### Expected Features

**Must have (table stakes):**
- Batch iteration across topic x prompt x resolution matrix -- this is the core promise
- Crash recovery / resume via filesystem state -- overnight runs must survive crashes
- Organized output naming with template tokens -- users must find files in 75K outputs
- Error handling that does not stop the batch -- retry + skip + strike counter
- CRON scheduling with skip-if-busy -- unattended operation is the entire point
- Progress visibility -- at minimum a status string output; log file is strongly recommended
- Workflow fingerprint collision detection -- prevents the silent disaster of mixed outputs

**Should have (differentiators):**
- 6 prompt mutation strategies (synonym swap, style shuffle, weight jitter, etc.)
- 3-layer tag generation pipeline (prompt extraction + topic bank + optional LLM)
- Sidecar JSON with full provenance per output
- Manifest CSV as global index of all outputs
- Queue ordering modes (sequential, interleaved, shuffled)
- File integrity checking on restart (header validation + Pillow decode)

**Defer (v2+):**
- LLM-based tag generation (Layer 3) -- adds external dependency complexity
- Audio/video output support -- ship image-only first
- Custom API route for remote monitoring -- polish feature
- Negative prompt variation -- most users want stable negatives
- Custom word bank paths -- ship with built-in banks first
- run_command mode in CRON -- secondary use case

See `.planning/research/FEATURES.md` for competitive analysis and dependency graph.

### Architecture Approach

The architecture follows ComfyUI's demand-driven DAG execution model: one /prompt call = one graph pass, no built-in loops. State advances via filesystem presence between executions. The CRON Scheduler uses a daemon background thread (module-level singleton) to re-queue the workflow on schedule. The Pipeline Controller reads filesystem state on each execution to find the next gap in the generation matrix. All shared logic lives in lib/ modules that are pure Python and testable without ComfyUI. See `.planning/research/ARCHITECTURE.md` for full component boundaries and data flow.

**Major components:**
1. **lib/ modules** (scanner, fingerprint, bulk_prompter, naming, metadata, sidecar, manifest, tag_generator, response_parser) -- Pure Python, no ComfyUI dependency, unit testable in isolation
2. **Pipeline Controller node** -- Orchestrates gap detection, prompt generation, metadata assembly; depends on nearly all lib/ modules
3. **CRON Scheduler node** -- Background thread lifecycle, re-queuing via /prompt API, skip-if-busy guard, done-signal handling
4. **Save As node** -- File writing, metadata embedding, sidecar/manifest output; OUTPUT_NODE = True
5. **Standalone nodes** (API Call, Bulk Prompter) -- Simpler wrappers around lib/ logic, independently useful

### Critical Pitfalls

1. **IS_CHANGED misuse** -- Pipeline Controller must return changing values (gap index) to bust cache; CRON must return float("nan"); Save As should NOT override IS_CHANGED. Wrong values cause the pipeline to repeat the same image or freeze entirely.
2. **Background thread lifecycle** -- Must use module-level singleton with threading.Event stop signal. Without this, re-execution spawns duplicate CRON threads that deadlock on skip-if-busy or queue duplicate work.
3. **Filesystem scan performance at 75K files** -- Must implement incremental caching from day one. Use os.scandir() not os.listdir(). Consider persisting the scan cache to disk for fast restarts.
4. **Cross-platform filesystem differences** -- Use pathlib everywhere, sanitize topic names aggressively, use os.replace() for atomic writes (works on both Windows and Linux), validate path lengths at pipeline start.
5. **Prompt cache invalidation** -- Include parameter hashes in cache files. When base_prompt_template or prompts_per_topic changes, detect the mismatch and regenerate. Corrupted caches must trigger regeneration, not crashes.

See `.planning/research/PITFALLS.md` for all 18 pitfalls with prevention strategies.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation Libraries
**Rationale:** All lib/ modules are pure Python with no ComfyUI dependency. They can be built and unit tested in complete isolation. The architecture research shows every node depends on these modules -- they must exist first.
**Delivers:** scanner.py, fingerprint.py, naming.py, bulk_prompter.py (with word banks), metadata.py, sidecar.py, manifest.py, response_parser.py, retry logic
**Addresses:** Filesystem gap scanning, template naming, prompt mutation, metadata embedding, workflow fingerprinting
**Avoids:** Pitfall 4 (scan performance -- design incremental caching from day one), Pitfall 6 (cross-platform -- use pathlib from the start), Pitfall 7 (cache invalidation -- include parameter hashes), Pitfall 15 (word bank encoding)

### Phase 2: Standalone Nodes
**Rationale:** Save As, API Call, and Bulk Prompter are simpler nodes that wrap lib/ modules. They validate that the libraries work correctly within ComfyUI's node contract. Users get immediate value (better save, prompt generation) while Pipeline Controller is still being built.
**Delivers:** Save As node (with naming, metadata, sidecar, manifest), API Call node, Bulk Prompter node, __init__.py registration
**Uses:** Pillow, piexif, mutagen (for Save As metadata embedding)
**Implements:** OUTPUT_NODE pattern, INPUT_TYPES contract, node registration with try/except isolation
**Avoids:** Pitfall 12 (registration breaking other nodes), Pitfall 13 (metadata embedding failures)

### Phase 3: Pipeline Orchestration Nodes
**Rationale:** Pipeline Controller and CRON Scheduler are the most complex nodes with the most ComfyUI-specific integration (IS_CHANGED, background threads, /prompt re-queuing, hidden inputs for fingerprinting). They depend on almost all lib/ modules and require the standalone nodes to be working.
**Delivers:** Pipeline Controller (gap detection, prompt orchestration, metadata assembly), CRON Scheduler (background thread, cron parsing, skip-if-busy)
**Uses:** croniter, ComfyUI /prompt and /queue APIs, hidden inputs (PROMPT, EXTRA_PNGINFO)
**Implements:** IS_CHANGED cache busting, module-level thread singleton, filesystem-as-state pattern
**Avoids:** Pitfall 1 (IS_CHANGED), Pitfall 2 (thread lifecycle), Pitfall 3 (scanner/save race condition), Pitfall 14 (queue race)

### Phase 4: Integration and Tag Pipeline
**Rationale:** Tag generation (especially LLM Layer 3) and the custom progress API route are enhancement features that build on the working pipeline. This phase connects all the pieces and adds the differentiating tag pipeline.
**Delivers:** tag_generator.py (3-layer pipeline), custom PromptServer API routes (/pipeline-automation/status), end-to-end workflow testing
**Avoids:** Pitfall 5 (route conflicts -- use namespaced paths), Pitfall 8 (execution thread blocking -- timeouts on LLM calls)

### Phase 5: Hardening and Scale Testing
**Rationale:** The 75K-scale target requires explicit testing for memory leaks, scan performance degradation, manifest size, and overnight stability. This cannot be validated during development -- it requires dedicated endurance testing.
**Delivers:** Long-running stability validation, memory profiling, performance benchmarks, edge case coverage (manual file deletion, parameter changes mid-run, corrupt files)
**Avoids:** Pitfall 9 (memory leaks), Pitfall 16 (counter desync after manual deletion), Pitfall 18 (strike counter persistence across parameter changes)

### Phase Ordering Rationale

- **lib/ before nodes** because pure Python modules are testable without ComfyUI and all nodes depend on them. The architecture research confirms this as the correct build order.
- **Standalone nodes before pipeline nodes** because they validate the lib/ layer and the ComfyUI node contract with simpler integration points. If Save As has a bug in metadata embedding, discovering it while also debugging Pipeline Controller creates unnecessary complexity.
- **Pipeline orchestration is the hardest phase** because it combines filesystem state, ComfyUI caching (IS_CHANGED), background threading, and HTTP API integration. Isolating this complexity to Phase 3 with all dependencies already working reduces risk.
- **Tag pipeline and progress API are enhancements** that do not block the core value proposition (unattended batch generation with crash recovery). Deferring them keeps the critical path shorter.
- **Scale testing as a dedicated phase** because 75K-file performance cannot be validated incrementally. It requires a focused test run and profiling.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** CRON Scheduler background thread pattern needs verification against current ComfyUI source. IS_CHANGED behavior with float("nan") is widely documented but should be confirmed. The interaction between skip-if-busy and ComfyUI's queue management needs careful design.
- **Phase 4:** LLM API integration patterns for tag generation (if pursuing Layer 3). PromptServer route registration timing should be verified against current ComfyUI startup sequence.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Pure Python library code. Scanner, naming, fingerprinting, metadata embedding are all well-documented patterns. No ComfyUI-specific concerns.
- **Phase 2:** ComfyUI node registration is a well-established pattern with ample examples in the ecosystem. Save/metadata/API call patterns are straightforward.
- **Phase 5:** Testing and profiling -- standard engineering practices, no domain-specific research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Minimal dependencies, mostly stdlib. Library versions need verification (training data cutoff May 2025). ComfyUI bundled deps are well-known. |
| Features | MEDIUM | Competitive landscape based on May 2025 knowledge. New node packs may have emerged. Core value proposition (integrated pipeline) is genuinely novel based on known ecosystem. |
| Architecture | MEDIUM-HIGH | ComfyUI node contract (INPUT_TYPES, IS_CHANGED, OUTPUT_NODE) is stable and well-established. Hidden input names and PromptServer patterns should be verified against current source. |
| Pitfalls | MEDIUM | Pitfalls are derived from architecture knowledge and general systems engineering. ComfyUI-specific pitfalls (IS_CHANGED caching, thread lifecycle) need source code verification. |

**Overall confidence:** MEDIUM

### Gaps to Address

- **ComfyUI API verification:** Hidden input names ("PROMPT", "EXTRA_PNGINFO", "UNIQUE_ID"), IS_CHANGED float("nan") behavior, and PromptServer route registration should be verified against current ComfyUI source before Phase 2-3 implementation.
- **Ecosystem re-scan:** The competitive landscape was assessed with May 2025 training data. Check ComfyUI Registry and GitHub for new pipeline/automation packs that may have launched since then.
- **Library version pinning:** Verify latest stable versions of croniter, piexif, and mutagen before writing requirements.txt.
- **Windows-specific testing:** Several pitfalls (path length, atomic rename, file locking) are Windows-specific. If the primary deployment target is Windows, these need early validation.
- **ComfyUI Registry publishing:** pyproject.toml format for the ComfyUI Registry (comfyregistry.org) should be verified against current registry requirements.

## Sources

### Primary (HIGH confidence)
- PROJECT.md / build-plan.md -- direct project specification and constraints
- Python stdlib documentation -- pathlib, json, csv, hashlib, logging, threading
- ComfyUI node class contract -- stable API established across hundreds of community node packs

### Secondary (MEDIUM confidence)
- ComfyUI execution model -- based on established community knowledge and source code analysis through May 2025
- ComfyUI PromptServer patterns -- aiohttp route registration, /prompt and /queue APIs
- croniter, piexif, mutagen library capabilities -- based on training data, versions need verification

### Tertiary (LOW confidence)
- ComfyUI Registry publishing format -- may have changed since May 2025
- Competitive landscape -- new node packs may exist that were not in training data

---
*Research completed: 2026-03-06*
*Ready for roadmap: yes*
