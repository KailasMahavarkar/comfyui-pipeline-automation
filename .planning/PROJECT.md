# ComfyUI Pipeline Automation Node Pack

## What This Is

A five-node custom node pack for ComfyUI that turns manual, one-at-a-time image generation into a fully automated, self-healing production pipeline. Handles jobs at scale (150 topics x 50 prompt variants x 10 resolutions = 75,000 outputs) — unattended, resumable, and fully traceable.

## Core Value

Unattended batch generation that survives crashes, resumes automatically, and produces organized, searchable outputs with full metadata traceability.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] CRON Scheduler node that re-queues workflows on a cron schedule with skip-if-busy guard
- [ ] Pipeline Controller node that scans filesystem for gaps, generates prompts/tags, and orchestrates the full matrix
- [ ] Save As node with template-based naming, embedded metadata, optional sidecar JSON, and manifest CSV
- [ ] API Call standalone node for external LLM/REST API calls with retry logic
- [ ] Bulk Prompter standalone node for local prompt variation using 6 mutation strategies
- [ ] Filesystem-as-state architecture — crash-proof, self-healing, no databases
- [ ] Workflow fingerprint + collision detection to prevent cross-workflow contamination
- [ ] 3-layer tag generation pipeline (prompt extraction, topic bank, LLM)
- [ ] File integrity checking (header validation, Pillow decode for recent files on restart)
- [ ] Strike counter for repeated failures with skip-after-3 logic
- [ ] Progress visibility via status output, log file, and custom API route
- [ ] Support for image, audio, and video output formats

### Out of Scope

- Database-backed state management — filesystem is the source of truth by design
- External scripts or services — everything lives inside ComfyUI custom nodes
- Monkey-patching ComfyUI internals — uses official mechanisms only (IS_CHANGED, PromptServer, file I/O)

## Context

- ComfyUI custom nodes are Python classes with specific class methods (INPUT_TYPES, RETURN_TYPES, etc.)
- Nodes register via `__init__.py` with NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS
- State management uses `IS_CHANGED` for cache busting and `PromptServer` for API routes
- The pipeline uses ComfyUI's `/prompt` API for re-queuing and `/queue` API for busy detection
- Output goes to ComfyUI's standard output directory
- Word banks ship with the pack (~510 entries across 4 files)

## Constraints

- **Tech stack**: Pure Python, ComfyUI custom node API, no external services
- **Dependencies**: croniter, Pillow, numpy, mutagen (audio), piexif (JPEG), ffmpeg (system, for audio/video)
- **Compatibility**: Must work alongside all existing ComfyUI nodes without interference
- **Architecture**: Pipeline Controller is the single orchestrator — other nodes are simple receivers

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Filesystem as state | Crash-proof, self-healing, no pointer drift | — Pending |
| Pipeline Controller owns full matrix | Single brain, one scan, no node coordination | — Pending |
| Workflow fingerprint + hard block | Prevents cross-workflow contamination | — Pending |
| Bulk Prompter logic shared via lib/ | Avoids 74,850 no-op node executions | — Pending |
| Tag generation on first encounter per topic | 150 LLM calls not 75K | — Pending |
| Naming template presets + free-text override | Flexible for power users, easy for beginners | — Pending |
| Retry -> fallback -> skip -> log error strategy | Batch never stops unless physically impossible | — Pending |
| Workflow JSON saved once at root, not per file | Prevents 75K x 50KB = 3.7GB duplication | — Pending |

---
*Last updated: 2026-03-06 after initialization*
