# Roadmap: ComfyUI Pipeline Automation Node Pack

## Overview

This roadmap delivers a five-node ComfyUI custom node pack for automated, crash-proof batch image generation at scale. The build order follows dependency chains: pure Python library modules first (testable without ComfyUI), then standalone nodes that wrap those modules, then the complex orchestration layer (Pipeline Controller + CRON Scheduler), then monitoring and progress visibility, and finally end-to-end integration validation across the full pipeline.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation Libraries** - Pure Python lib/ modules for scanning, naming, metadata, fingerprinting, and prompt mutation
- [ ] **Phase 2: Standalone Nodes** - Save As, API Call, and Bulk Prompter nodes wrapping lib/ modules
- [ ] **Phase 3: Pipeline Orchestration** - Pipeline Controller and CRON Scheduler nodes with filesystem state and background threading
- [ ] **Phase 4: Progress and Monitoring** - Status output, progress log, and custom API route for pipeline visibility
- [ ] **Phase 5: End-to-End Integration** - Full pipeline validation with CRON, Pipeline Controller, and Save As completing a batch unattended

## Phase Details

### Phase 1: Foundation Libraries
**Goal**: All shared library modules exist, are tested, and correctly handle cross-platform filesystem operations
**Depends on**: Nothing (first phase)
**Requirements**: LIB-01, LIB-02, LIB-03, LIB-04, LIB-05, LIB-06, LIB-07, LIB-08, LIB-09, LIB-10, LIB-11, LIB-12, LIB-13, LIB-14, LIB-15
**Success Criteria** (what must be TRUE):
  1. Naming module resolves all 8 template tokens into valid filenames and supports all 4 preset templates
  2. Metadata module embeds and reads back tags from PNG, JPEG, and WebP files without corruption
  3. Scanner detects missing entries in a topic x prompt x resolution matrix and validates file integrity (header check + Pillow decode)
  4. Fingerprint module computes identical hashes for the same workflow and different hashes when node connections or models change, and produces clear collision error messages
  5. Bulk prompter generates distinct prompt variants using each of the 6 mutation strategies from shipped word banks
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Standalone Nodes
**Goal**: Users can install the pack and use Save As, API Call, and Bulk Prompter as independent ComfyUI nodes
**Depends on**: Phase 1
**Requirements**: SAVE-01, SAVE-02, SAVE-03, SAVE-04, SAVE-05, SAVE-06, SAVE-07, SAVE-08, API-01, API-02, API-03, API-04, API-05, BULK-01, BULK-02, BULK-03, INTG-01
**Success Criteria** (what must be TRUE):
  1. User can drop Save As node into a workflow and save images with template-based naming, embedded metadata, optional sidecar JSON, and manifest CSV entries
  2. User can drop API Call node into a workflow and get a parsed response from an external REST API with retry on failure
  3. User can drop Bulk Prompter node into a workflow and receive N distinct prompt variants from a base prompt
  4. All 5 nodes appear in ComfyUI's node menu and load without errors or interference with other installed nodes
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Pipeline Orchestration
**Goal**: Pipeline Controller and CRON Scheduler work together to iterate through a generation matrix unattended, surviving crashes and resuming automatically
**Depends on**: Phase 2
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, PIPE-08, PIPE-09, CRON-01, CRON-02, CRON-03, CRON-04, CRON-05, CRON-06, CRON-07, INTG-02
**Success Criteria** (what must be TRUE):
  1. Pipeline Controller outputs the correct next gap (prompt, dimensions, metadata) from the generation matrix on each execution, advancing through the full matrix over successive runs
  2. Pipeline Controller blocks execution with a clear error when a workflow fingerprint mismatch is detected
  3. CRON Scheduler re-queues the workflow on schedule, skips when ComfyUI is busy, and stops when the pipeline signals completion
  4. After a simulated crash (process kill), restarting the workflow resumes from where it left off with no duplicate or missing outputs
  5. Pipeline Controller skips entries that have failed 3 times and continues with the rest of the matrix
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Progress and Monitoring
**Goal**: Users can observe pipeline progress in real time through status output, log files, and an API endpoint
**Depends on**: Phase 3
**Requirements**: PROG-01, PROG-02, PROG-03
**Success Criteria** (what must be TRUE):
  1. Pipeline Controller status output shows current topic, prompt, and resolution progress with percentage and ETA
  2. Progress log file records structured events (START, PROGRESS, TOPIC_COMPLETE, SKIP, HALT) that can be tailed during a run
  3. GET /pipeline-automation/status returns JSON with current progress details accessible from any HTTP client
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: End-to-End Integration
**Goal**: The full CRON -> Pipeline Controller -> Save As pipeline completes a real batch unattended and produces correct, organized, traceable outputs
**Depends on**: Phase 4
**Requirements**: INTG-03
**Success Criteria** (what must be TRUE):
  1. A workflow with CRON Scheduler, Pipeline Controller, and Save As completes a 3x3x2 matrix (18 images) end-to-end without manual intervention
  2. All 18 output files have correct template-based names, embedded metadata, and manifest CSV entries
  3. Interrupting and restarting the batch mid-run produces exactly 18 total outputs with no duplicates
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Libraries | 0/? | Not started | - |
| 2. Standalone Nodes | 0/? | Not started | - |
| 3. Pipeline Orchestration | 0/? | Not started | - |
| 4. Progress and Monitoring | 0/? | Not started | - |
| 5. End-to-End Integration | 0/? | Not started | - |
