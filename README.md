# ComfyUI Pipeline Automation (⚠️ WIP)

Automated batch image generation for ComfyUI. Turns manual one-at-a-time workflows into unattended, crash-proof production pipelines that can generate thousands of organized, metadata-rich outputs overnight.

## Installation

Clone into your ComfyUI `custom_nodes` directory and install dependencies:

```bash
cd ComfyUI/custom_nodes
git clone <repo-url> comfyui-pipeline-automation
cd comfyui-pipeline-automation
pip install -r requirements.txt
```

Restart ComfyUI. All five nodes appear under **Pipeline Automation** in the node menu.

## Nodes

### CRON Scheduler

Re-queues the current workflow on a schedule via a background thread. Supports preset intervals (every 1/5/15/30 min, hourly, daily) or custom cron expressions. Skips ticks when ComfyUI's queue is busy to prevent pile-up. Stops automatically when the pipeline signals completion.

### Pipeline Controller

The brain of the pipeline. Given a list of topics, resolutions, and a prompt template, it:

- Builds a generation matrix (topics × resolutions × prompts per topic)
- Scans the output folder to find the first missing entry
- Generates prompt variants and tags on first encounter of each topic (cached for reuse)
- Outputs the next prompt, dimensions, and metadata for downstream nodes
- Detects workflow fingerprint collisions to prevent cross-workflow contamination

### Save As

Saves images with template-based filenames, organized subfolders, and rich metadata:

- **Naming presets**: Simple, Detailed, Minimal, or Custom templates with tokens like `{topic}`, `{resolution}`, `{date}`, `{counter}`
- **Metadata embedding**: Tags and prompt written into PNG tEXt, JPEG EXIF, or WebP XMP
- **Sidecar JSON**: Full metadata including tags, provenance, and pipeline state (optional)
- **Manifest CSV**: Append-only global index of all outputs (optional)

### API Call

Calls any REST API (OpenAI-compatible preset or generic mode). Supports configurable retry with exponential backoff, dot-path response mapping, and auto-parsing of stringified JSON in LLM responses.

### Bulk Prompter

Generates N prompt variants from a base prompt using local mutation strategies: synonym swap, detail injection, style shuffle, weight jitter, clause reorder, and template fill. Zero API calls — uses bundled word banks.

## Pipeline Workflow

For automated batch generation, wire three nodes:

```
CRON Scheduler → Pipeline Controller → [your generation nodes] → Save As
```

1. **CRON Scheduler** re-queues the workflow on each tick
2. **Pipeline Controller** finds the next gap and outputs prompt + dimensions
3. Standard ComfyUI nodes (CLIP Encode, KSampler, VAE Decode) generate the image
4. **Save As** saves with organized naming and metadata
5. On next tick, Pipeline Controller advances to the next missing entry

The filesystem is the source of truth — if ComfyUI crashes, restart and the pipeline resumes exactly where it left off.

## Output Structure

```
output/
└── my_workflow/
    ├── .workflow_fingerprint
    ├── .prompt_cache/
    │   └── sunset_beach.json
    ├── sunset_beach/
    │   └── 512x512/
    │       ├── sunset_beach_512x512_001.png
    │       └── sunset_beach_512x512_001.json   (sidecar, optional)
    └── manifest.csv                            (optional)
```

## Standalone Use

Save As, API Call, and Bulk Prompter work independently in any workflow — no pipeline required.
