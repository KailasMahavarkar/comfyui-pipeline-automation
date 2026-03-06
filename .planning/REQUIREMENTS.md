# Requirements: ComfyUI Pipeline Automation Node Pack

**Defined:** 2026-03-06
**Core Value:** Unattended batch generation that survives crashes, resumes automatically, and produces organized, searchable outputs with full metadata traceability.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation Libraries

- [ ] **LIB-01**: Naming module resolves template tokens ({prefix}, {topic}, {date}, {time}, {resolution}, {counter}, {batch}, {format}) into filenames
- [ ] **LIB-02**: Naming module supports preset templates (Simple, Detailed, Minimal, Custom)
- [ ] **LIB-03**: Metadata module embeds flat tags + prompt in PNG tEXt, JPEG EXIF, WebP XMP, and GIF comment
- [ ] **LIB-04**: Sidecar module writes .json sidecar alongside each output with full categorized tags and provenance
- [ ] **LIB-05**: Manifest module appends rows to manifest.csv with thread-safe locking and auto-header creation
- [ ] **LIB-06**: Response parser extracts values from nested JSON using dot-path notation with auto-parse of stringified JSON
- [ ] **LIB-07**: Bulk prompter generates N prompt variants using 6 mutation strategies (synonym_swap, detail_injection, style_shuffle, weight_jitter, reorder, template_fill)
- [ ] **LIB-08**: Tag generator implements 3-layer pipeline: prompt extraction, topic bank lookup, and LLM generation
- [ ] **LIB-09**: Scanner detects gaps in topic x prompt x resolution matrix by comparing filesystem to planned entries
- [ ] **LIB-10**: Scanner performs Level 2 integrity checks (existence + size + header validation) on every run
- [ ] **LIB-11**: Scanner performs Level 3 integrity checks (Pillow decode) on files modified in last hour on restart
- [ ] **LIB-12**: Fingerprint module computes workflow fingerprint from node types, connections, checkpoint/LoRA names, and workflow_name
- [ ] **LIB-13**: Fingerprint module saves/loads/compares fingerprints and produces actionable collision error messages
- [ ] **LIB-14**: Scanner implements incremental caching (full scan on first run, in-memory updates after each save)
- [ ] **LIB-15**: All lib modules use pathlib for cross-platform filesystem compatibility

### Save As Node

- [ ] **SAVE-01**: User can save images with template-based naming using configurable tokens
- [ ] **SAVE-02**: User can choose naming presets (Simple, Detailed, Minimal) or Custom template
- [ ] **SAVE-03**: User can save in PNG, JPEG, or WebP format with configurable quality
- [ ] **SAVE-04**: User can organize output into subfolders using subfolder_template with same tokens
- [ ] **SAVE-05**: User can embed metadata (tags + prompt) into image file metadata per format
- [ ] **SAVE-06**: User can optionally write .json sidecar alongside each output
- [ ] **SAVE-07**: User can optionally append to manifest.csv with each save
- [ ] **SAVE-08**: Save As outputs comma-separated list of saved file paths

### API Call Node

- [ ] **API-01**: User can call any REST API with configurable URL, method, headers, and body
- [ ] **API-02**: User can use OpenAI-compatible preset that pre-fills request structure
- [ ] **API-03**: User can extract values from JSON responses using dot-path response_mapping
- [ ] **API-04**: API Call retries failed requests with configurable count and exponential backoff
- [ ] **API-05**: API Call strips markdown code blocks from LLM responses before parsing

### Bulk Prompter Node

- [ ] **BULK-01**: User can generate N prompt variants from a base prompt
- [ ] **BULK-02**: User can select which mutation strategies to apply via multi-dropdown
- [ ] **BULK-03**: Bulk Prompter ships with curated word banks (adjectives, styles, moods, scene_details)

### Pipeline Controller Node

- [ ] **PIPE-01**: Pipeline Controller scans filesystem and outputs parameters for the first missing entry in the matrix
- [ ] **PIPE-02**: Pipeline Controller generates prompt variants on first encounter of each topic and caches to .prompt_cache/
- [ ] **PIPE-03**: Pipeline Controller generates tags on first encounter of each topic using the 3-layer pipeline
- [ ] **PIPE-04**: Pipeline Controller outputs prompt, negative_prompt, width, height, metadata JSON, is_complete, and status
- [ ] **PIPE-05**: Pipeline Controller computes and validates workflow fingerprint on every run, blocking on mismatch
- [ ] **PIPE-06**: Pipeline Controller supports queue ordering modes: sequential, interleaved, shuffled
- [ ] **PIPE-07**: Pipeline Controller implements strike counter that skips entries after 3 failures
- [ ] **PIPE-08**: Pipeline Controller uses IS_CHANGED returning current gap index to bust ComfyUI cache
- [ ] **PIPE-09**: Pipeline Controller accepts reset_workflow toggle to force fresh start

### CRON Scheduler Node

- [ ] **CRON-01**: CRON Scheduler re-queues the current workflow via ComfyUI /prompt API on a configurable cron schedule
- [ ] **CRON-02**: CRON Scheduler supports schedule presets (Every 1/5/15/30 min, Hourly, Every 6 hours, Daily) plus Custom cron expression
- [ ] **CRON-03**: CRON Scheduler implements skip-if-busy guard via /queue API before re-queuing
- [ ] **CRON-04**: CRON Scheduler stops when Pipeline Controller signals is_complete=True
- [ ] **CRON-05**: CRON Scheduler uses single-instance daemon thread with module-level singleton
- [ ] **CRON-06**: CRON Scheduler supports max_iterations limit (0=unlimited)
- [ ] **CRON-07**: CRON Scheduler uses IS_CHANGED returning float("nan") to force re-execution

### Progress & Monitoring

- [ ] **PROG-01**: Pipeline Controller status output shows topic progress, prompt progress, resolution progress, global progress with percentage and ETA
- [ ] **PROG-02**: Progress log file (.progress.log) records START, PROGRESS, TOPIC_COMPLETE, TOPIC_START, SKIP, and HALT events
- [ ] **PROG-03**: Custom API route GET /pipeline-automation/status returns JSON progress details

### Integration

- [ ] **INTG-01**: All 5 nodes register correctly in ComfyUI via NODE_CLASS_MAPPINGS
- [ ] **INTG-02**: Pipeline Controller outputs wire directly to standard ComfyUI nodes (CLIP Encode, Empty Latent Image)
- [ ] **INTG-03**: CRON → Pipeline Controller → Save As pipeline completes a small batch (3 topics x 3 prompts x 2 resolutions = 18 images) end-to-end

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Audio/Video Support

- **AV-01**: Save As supports WAV, MP3, MP4, and GIF output formats
- **AV-02**: Metadata embedding for audio formats (ID3 tags via mutagen)
- **AV-03**: Metadata embedding for video formats (ffmpeg -metadata)

### Advanced Features

- **ADV-01**: User can provide custom word bank paths that merge with defaults
- **ADV-02**: Negative prompt variation toggle in Pipeline Controller
- **ADV-03**: CRON Scheduler run_command mode for external shell commands

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Database-backed state | Filesystem IS the database by design. Adds complexity, breaks crash recovery model |
| ComfyUI internal monkey-patching | Breaks on updates, incompatible with other packs |
| External service dependencies | Everything lives inside custom nodes. LLM API is optional |
| Custom UI widgets | Complex to maintain, breaks across ComfyUI versions |
| Image post-processing (upscaling, face fix) | Well-served by existing nodes |
| Prompt engineering / quality optimization | Subjective, model-dependent |
| Model management | ComfyUI-Manager handles this |
| Multi-GPU / distributed generation | Massive complexity, niche use case |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LIB-01 | Phase 1 | Pending |
| LIB-02 | Phase 1 | Pending |
| LIB-03 | Phase 1 | Pending |
| LIB-04 | Phase 1 | Pending |
| LIB-05 | Phase 1 | Pending |
| LIB-06 | Phase 1 | Pending |
| LIB-07 | Phase 1 | Pending |
| LIB-08 | Phase 1 | Pending |
| LIB-09 | Phase 1 | Pending |
| LIB-10 | Phase 1 | Pending |
| LIB-11 | Phase 1 | Pending |
| LIB-12 | Phase 1 | Pending |
| LIB-13 | Phase 1 | Pending |
| LIB-14 | Phase 1 | Pending |
| LIB-15 | Phase 1 | Pending |
| SAVE-01 | Phase 2 | Pending |
| SAVE-02 | Phase 2 | Pending |
| SAVE-03 | Phase 2 | Pending |
| SAVE-04 | Phase 2 | Pending |
| SAVE-05 | Phase 2 | Pending |
| SAVE-06 | Phase 2 | Pending |
| SAVE-07 | Phase 2 | Pending |
| SAVE-08 | Phase 2 | Pending |
| API-01 | Phase 2 | Pending |
| API-02 | Phase 2 | Pending |
| API-03 | Phase 2 | Pending |
| API-04 | Phase 2 | Pending |
| API-05 | Phase 2 | Pending |
| BULK-01 | Phase 2 | Pending |
| BULK-02 | Phase 2 | Pending |
| BULK-03 | Phase 2 | Pending |
| PIPE-01 | Phase 3 | Pending |
| PIPE-02 | Phase 3 | Pending |
| PIPE-03 | Phase 3 | Pending |
| PIPE-04 | Phase 3 | Pending |
| PIPE-05 | Phase 3 | Pending |
| PIPE-06 | Phase 3 | Pending |
| PIPE-07 | Phase 3 | Pending |
| PIPE-08 | Phase 3 | Pending |
| PIPE-09 | Phase 3 | Pending |
| CRON-01 | Phase 3 | Pending |
| CRON-02 | Phase 3 | Pending |
| CRON-03 | Phase 3 | Pending |
| CRON-04 | Phase 3 | Pending |
| CRON-05 | Phase 3 | Pending |
| CRON-06 | Phase 3 | Pending |
| CRON-07 | Phase 3 | Pending |
| PROG-01 | Phase 4 | Pending |
| PROG-02 | Phase 4 | Pending |
| PROG-03 | Phase 4 | Pending |
| INTG-01 | Phase 2 | Pending |
| INTG-02 | Phase 3 | Pending |
| INTG-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 51 total
- Mapped to phases: 51
- Unmapped: 0

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-06 after initial definition*
