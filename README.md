# ComfyUI Pipeline Automation

Automated batch image generation for ComfyUI. Turns manual one-at-a-time workflows into unattended, crash-proof production pipelines that can generate thousands of organized, metadata-rich outputs overnight.

## Installation

Clone into your ComfyUI `custom_nodes` directory and install dependencies:

```bash
cd ComfyUI/custom_nodes
git clone <repo-url> comfyui-pipeline-automation
cd comfyui-pipeline-automation
pip install -r requirements.txt
```

Restart ComfyUI. All nodes appear under **Pipeline Automation** in the node menu.

## Nodes

### Gap Scanner

Scans the output directory against a planned generation matrix (topics x resolutions x prompts per topic) and emits the next missing entry. Acts as the single source of truth for shared pipeline settings via `PIPELINE_CONFIG`.

| Output | Type | Description |
|--------|------|-------------|
| `topic` | STRING | Next topic to generate |
| `resolution` | STRING | Resolution string (e.g. `512x512`) |
| `width` | INT | Parsed width |
| `height` | INT | Parsed height |
| `variant_index` | INT | Which prompt variant to use |
| `is_complete` | BOOLEAN | True when all gaps are filled |
| `status` | STRING | Progress info |
| `pipeline_config` | PIPELINE_CONFIG | Shared settings (workflow_name, output_dir, format, prompts_per_topic) |

### Prompt Generator

Takes a topic and variant index, generates prompt variants using local mutation strategies (synonym swap, detail injection, style shuffle, weight jitter, clause reorder, template fill), and optionally generates tags via LLM. Caches results to disk per topic. Accepts `PIPELINE_CONFIG` for shared settings.

| Output | Type | Description |
|--------|------|-------------|
| `prompt` | STRING | The selected prompt variant |
| `negative_prompt` | STRING | Negative prompt |
| `metadata` | STRING | JSON with tags, pipeline state, provenance |

### LLM Config

Structured LLM connection settings with provider presets. Outputs a typed `LLM_CONFIG` object — no manual JSON required. Can be shared between Prompt Generator (for tag generation) and API Call (for custom LLM calls).

| Provider | Auto-fills URL |
|----------|---------------|
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` |
| OpenAI | `https://api.openai.com/v1/chat/completions` |
| Ollama | `http://localhost:11434/v1/chat/completions` |
| LM Studio | `http://localhost:1234/v1/chat/completions` |
| Custom | User-provided |

### CRON Scheduler

Re-queues the current workflow on a schedule via a background thread. Supports preset intervals (every 1/5/15/30 min, hourly, daily) or custom cron expressions. Skips ticks when ComfyUI's queue is busy. Stops automatically when `is_complete` is true. Passthrough accepts any type (IMAGE, LATENT, STRING, etc.) so it can sit anywhere in the graph.

### Save As

Saves images with template-based filenames, organized subfolders, and rich metadata. Accepts `PIPELINE_CONFIG` for format and output_dir.

- **Naming presets**: Simple, Detailed, Minimal, or Custom templates with tokens like `{topic}`, `{resolution}`, `{date}`, `{counter}`
- **Metadata embedding**: Tags and prompt written into PNG tEXt, JPEG EXIF, or WebP XMP
- **Sidecar JSON**: Full metadata including tags, provenance, and pipeline state (optional)
- **Manifest CSV**: Append-only global index of all outputs (optional)

### API Call

Calls any REST API (OpenAI-compatible preset or generic). Supports configurable retry with exponential backoff, dot-path response mapping, and auto-parsing of stringified JSON. Optionally accepts `LLM_CONFIG` to share connection settings with other nodes. Standalone utility node.

### Bulk Prompter

Generates N prompt variants from a base prompt using local mutation strategies. Zero API calls — uses bundled word banks. Standalone utility node.

## Wiring Map

| Source | Output | Type | Target | Input |
|--------|--------|------|--------|-------|
| Gap Scanner | `topic` | STRING | Prompt Generator | `topic` |
| Gap Scanner | `resolution` | STRING | Prompt Generator | `resolution` |
| Gap Scanner | `variant_index` | INT | Prompt Generator | `variant_index` |
| Gap Scanner | `width` | INT | Empty Latent Image | `width` |
| Gap Scanner | `height` | INT | Empty Latent Image | `height` |
| Gap Scanner | `is_complete` | BOOLEAN | CRON Scheduler | `is_complete` |
| Gap Scanner | `pipeline_config` | PIPELINE_CONFIG | Prompt Generator | `pipeline_config` |
| Gap Scanner | `pipeline_config` | PIPELINE_CONFIG | Save As | `pipeline_config` |
| LLM Config | `llm_config` | LLM_CONFIG | Prompt Generator | `llm_config` |
| LLM Config | `llm_config` | LLM_CONFIG | API Call | `llm_config` |
| Prompt Generator | `prompt` | STRING | CLIP Text Encode | `text` |
| Prompt Generator | `negative_prompt` | STRING | CLIP Text Encode (neg) | `text` |
| Prompt Generator | `metadata` | STRING | Save As | `metadata` |
| CRON Scheduler | `passthrough` | * | Save As | `image` |

## Pipeline Workflow

![Pipeline Flow](docs/pipeline-flow.png)

**Blue** = pipeline nodes. **Grey** = built-in ComfyUI. **Purple** = standalone utility. **Dashed** = optional connection.

### Step by step

1. **Gap Scanner** scans the output folder, finds the next missing topic/resolution/variant combo
2. **Prompt Generator** generates (or loads cached) prompt variants for that topic, picks the one at `variant_index`
3. **LLM Config** (optional) provides connection settings for LLM-based tag generation
4. Standard ComfyUI nodes (CLIP Encode, KSampler, VAE Decode) generate the image
5. **CRON Scheduler** sits in the execution chain (via any-type passthrough) and re-queues the workflow on schedule
6. **Save As** saves with organized naming, embedded metadata, and optional sidecar/manifest
7. On next run, Gap Scanner advances to the next missing entry
8. When all gaps are filled, `is_complete` goes true and CRON Scheduler stops

The filesystem is the source of truth — if ComfyUI crashes, restart and the pipeline resumes exactly where it left off.

## Output Structure

```
output/
└── my_workflow/
    ├── .prompt_cache/
    │   └── sunset_beach.json
    ├── sunset_beach/
    │   └── 512x512/
    │       ├── sunset_beach_512x512_001.png
    │       └── sunset_beach_512x512_001.json   (sidecar, optional)
    └── manifest.csv                            (optional)
```

## Standalone Use

Save As, API Call, Bulk Prompter, and LLM Config work independently in any workflow — no pipeline required.
