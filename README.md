# ComfyUI Pipeline Automation

[![CI](https://github.com/KailasMahavarkar/comfyui-pipeline-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/KailasMahavarkar/comfyui-pipeline-automation/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Automated batch image generation for ComfyUI. Turns manual one-at-a-time workflows into unattended, crash-proof production pipelines that can generate thousands of organized, metadata-rich outputs overnight.

## Installation

Clone into your ComfyUI `custom_nodes` directory and run the setup script:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/KailasMahavarkar/comfyui-pipeline-automation.git
cd comfyui-pipeline-automation
python setup.py
```

Restart ComfyUI. All nodes appear under **Pipeline Automation** in the node menu.

### Requirements

- Pillow >= 9.0.0
- numpy >= 1.20.0
- piexif >= 1.1.3

## Pipeline Flow

![Pipeline Flow](docs/pipeline-flow.png)

| Color | Meaning |
|-------|---------|
| **Blue** | Pipeline nodes (Gap Scanner, Prompt Generator, CRON Scheduler, Save As) |
| **Purple** | LLM nodes (LLM Config) |
| **Green** | Optional primitives (Prompt List, Tag Bank, Webhook) |
| **Gray** | Standard ComfyUI nodes (CLIP Encode, KSampler, VAE Decode, Empty Latent) |

### How It Works

1. **Gap Scanner** scans the output folder and finds the next missing topic/resolution/variant combo
2. **Prompt Generator** picks the prompt for that slot using a priority system:
   - If `prompt_list` provided → uses that list, picks by `variant_index`
   - If `llm_config` connected → one LLM call generates all variants per topic, cached
   - Otherwise → local mutation strategies generate variants, cached
3. **LLM Config** (optional) provides connection settings for both variant generation and tag generation
4. Standard ComfyUI nodes (CLIP Encode, KSampler, VAE Decode) generate the image
5. **CRON Scheduler** sits in the execution chain and re-queues the workflow on schedule
6. **Save As** saves with organized naming, embedded metadata, and optional sidecar/manifest
7. On next run, Gap Scanner advances to the next missing entry
8. When all gaps are filled, `is_complete` goes true and CRON Scheduler stops

The filesystem is the source of truth — if ComfyUI crashes, restart and the pipeline resumes exactly where it left off.

## Nodes

### Gap Scanner

Scans the output directory against a planned generation matrix (topics × resolutions × prompts per topic) and emits the next missing entry. Acts as the single source of truth for shared pipeline settings via `PIPELINE_CONFIG`.

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `workflow_name` | STRING | — | Name for this workflow run |
| `topic_list` | STRING | — | Topics to generate (one per line) |
| `resolution_list` | STRING | `512x512` | Resolutions to cover (one per line) |
| `prompts_per_topic` | INT | `50` | Number of prompt variants per topic |
| `output_dir` | STRING | `output` | Base output directory |
| `format` | ENUM | `png` | Image format: png, jpeg, webp |
| `reset_workflow` | BOOLEAN | `false` | Clear cached state and restart |

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `topic` | STRING | Next topic to generate |
| `resolution` | STRING | Resolution string (e.g. `512x512`) |
| `width` | INT | Parsed width |
| `height` | INT | Parsed height |
| `variant_index` | INT | Which prompt variant to use (0-indexed) |
| `is_complete` | BOOLEAN | True when all gaps are filled |
| `status` | STRING | Progress info with percentage |
| `pipeline_config` | PIPELINE_CONFIG | Shared settings dict |

---

### Prompt Generator

Given a topic and variant index, returns the correct prompt for that slot. Supports three variant sources in priority order — the pipeline doesn't care how the prompt was produced, only that it gets the right one.

**Variant source priority:**

| Priority | Source | When | Cached |
|----------|--------|------|--------|
| 1 | `prompt_list` | User provides prompts (newline or JSON array) | No |
| 2 | `llm_config` | LLM connected — one call generates all N variants per topic | Yes |
| 3 | Mutations | Default — 6 local strategies (synonym swap, detail injection, style shuffle, weight jitter, reorder, template fill) | Yes |

If LLM fails, falls back to mutations silently. Tags are always generated via the 3-layer pipeline (prompt extraction, topic bank, optional LLM).

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `topic` | STRING | — | Topic from Gap Scanner |
| `variant_index` | INT | `0` | Which variant to select |
| `base_prompt_template` | STRING | `a beautiful {topic}, highly detailed` | Template with `{topic}` placeholder |
| `base_negative_prompt` | STRING | `blurry, watermark, text, low quality` | Negative prompt |
| `prompts_per_topic` | INT | `50` | How many variants to generate |
| `pipeline_config` | PIPELINE_CONFIG | — | Optional shared settings |
| `resolution` | STRING | `512x512` | For resolution-aware tags |
| `llm_config` | LLM_CONFIG | — | Optional: enables LLM variant generation and LLM tag generation |
| `prompt_list` | PROMPT_LIST | — | Custom prompts from Prompt List node — overrides all generation |
| `tag_bank` | TAG_BANK | — | Custom word banks and topic tags from Tag Bank node |

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `prompt` | STRING | The selected prompt variant |
| `negative_prompt` | STRING | Negative prompt |
| `metadata` | STRING | JSON with tags, pipeline state, provenance |

---

### LLM Config

Structured LLM connection settings with provider presets. Outputs a typed `LLM_CONFIG` object — no manual JSON required. When connected to Prompt Generator, enables both LLM-based variant generation (one call per topic) and LLM-based tag generation.

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | ENUM | — | OpenRouter, OpenAI, Ollama, LM Studio, Custom |
| `model` | STRING | `anthropic/claude-3-haiku` | Model identifier |
| `api_key` | STRING | — | API key (not needed for Ollama/LM Studio) |
| `api_url_override` | STRING | — | Override auto-detected URL |
| `temperature` | FLOAT | `0.7` | Sampling temperature (0.0–2.0) |
| `max_tokens` | INT | `200` | Max response tokens |

**Provider URL mapping:**

| Provider | Auto-fills URL |
|----------|---------------|
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` |
| OpenAI | `https://api.openai.com/v1/chat/completions` |
| Ollama | `http://localhost:11434/v1/chat/completions` |
| LM Studio | `http://localhost:1234/v1/chat/completions` |
| Custom | User-provided |

---

### CRON Scheduler

Re-queues the current workflow on a schedule via a background thread. Skips ticks when ComfyUI's queue is busy. Stops automatically when `is_complete` is true. Marked as `OUTPUT_NODE` so it always executes — no passthrough wiring needed.

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `schedule_preset` | ENUM | — | Every 1 min, Every 5 min, Every 15 min, Every 30 min, Hourly, Every 6 hours, Every 12 hours, Daily |
| `interval_seconds` | INT | `60` | Custom interval in seconds (10–86400) |
| `enabled` | BOOLEAN | `false` | Enable/disable scheduling |
| `mode` | ENUM | `requeue_workflow` | requeue_workflow, run_command, both |
| `comfyui_api_url` | STRING | `http://127.0.0.1:8188` | ComfyUI API endpoint |
| `max_iterations` | INT | `0` | Max iterations (0 = unlimited) |
| `external_command` | STRING | — | Shell command for run_command mode |
| `is_complete` | BOOLEAN | `false` | Stops scheduler when true |

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `status` | STRING | Scheduler state |

---

### Save As

Saves images with template-based filenames, organized subfolders, and rich metadata.

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | IMAGE | — | Image to save |
| `format` | ENUM | `png` | png, jpeg, webp |
| `quality` | INT | `95` | Compression quality (1–100) |
| `naming_preset` | ENUM | `Simple` | Simple, Detailed, Minimal, Custom |
| `filename_prefix` | STRING | `comfyui` | Filename prefix |
| `subfolder_template` | STRING | `{topic}/{resolution}` | Subfolder path template |
| `embed_metadata` | BOOLEAN | `true` | Embed metadata into image |
| `write_sidecar` | BOOLEAN | `false` | Write .json sidecar file |
| `write_manifest` | BOOLEAN | `false` | Append to manifest.csv |
| `pipeline_config` | PIPELINE_CONFIG | — | Overrides format and output_dir |
| `naming_template` | STRING | — | Custom naming template |
| `metadata` | STRING | — | JSON metadata from Prompt Generator |
| `output_dir` | STRING | `output` | Base output directory |

**Features:**
- **Naming tokens**: `{topic}`, `{resolution}`, `{date}`, `{time}`, `{counter}`, `{seed}`
- **Metadata embedding**: PNG tEXt, JPEG EXIF, WebP XMP
- **Sidecar JSON**: Full metadata including tags, provenance, and pipeline state
- **Manifest CSV**: Append-only global index of all outputs

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `saved_paths` | STRING | Comma-separated saved file paths |

---

### Webhook

Calls any REST API with configurable retry and exponential backoff. Use for notifications, triggering external workflows, or fetching data. Supports dot-path response extraction and `{topic}` template substitution in the body. Has a passthrough input so it can sit anywhere in the graph.

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | STRING | — | API endpoint |
| `method` | ENUM | `POST` | POST, GET, PUT, PATCH |
| `body` | STRING | — | Request body template (supports `{topic}`) |
| `headers` | STRING | — | Custom headers (JSON) |
| `response_mapping` | STRING | — | Dot-path extraction (e.g. `result=data.status`) |
| `api_key` | STRING | — | Bearer token (added to Authorization header) |
| `timeout` | INT | `30` | Request timeout (seconds) |
| `max_retries` | INT | `3` | Max retry attempts |
| `retry_delay` | INT | `2` | Base delay between retries (seconds) |
| `topic` | STRING | — | Available in body template as `{topic}` |
| `passthrough` | * | — | Any-type passthrough |

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `response` | STRING | Raw response body |
| `status_code` | INT | HTTP status code |
| `extracted` | STRING | JSON of dot-path extracted fields |

---

### Prompt List

Accepts user-provided prompts and outputs a typed `PROMPT_LIST` object. When connected to Prompt Generator, overrides all other variant generation (LLM and mutations). Supports newline-separated text or a JSON array of strings.

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `prompts` | STRING | — | Prompts (one per line or JSON array) |

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `prompt_list` | PROMPT_LIST | Parsed prompt list for Prompt Generator |

---

### Tag Bank

Bundles custom word bank paths and per-topic curated tags into a typed `TAG_BANK` object. When connected to Prompt Generator, provides custom synonyms/styles for mutation strategies and curated tags for metadata enrichment.

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `custom_word_bank_path` | STRING | — | Path to custom word bank directory |
| `topic_tag_bank` | STRING | — | Per-topic curated tags (JSON mapping) |

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `tag_bank` | TAG_BANK | Word bank config for Prompt Generator |

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
| Prompt Generator | `prompt` | STRING | CLIP Text Encode | `text` |
| Prompt Generator | `negative_prompt` | STRING | CLIP Text Encode (neg) | `text` |
| Prompt Generator | `metadata` | STRING | Save As | `metadata` |

## Custom Types

Four dict-based types are passed between nodes:

**PIPELINE_CONFIG:**
```python
{
    "workflow_name": "my_workflow",
    "output_dir": "output",
    "format": "png",
    "prompts_per_topic": 50
}
```

**LLM_CONFIG:**
```python
{
    "provider": "OpenRouter",
    "api_url": "https://openrouter.ai/api/v1/chat/completions",
    "api_key": "sk-...",
    "model": "anthropic/claude-3-haiku",
    "temperature": 0.7,
    "max_tokens": 200
}
```

**PROMPT_LIST:**
```python
{
    "prompts": ["a sunset over the ocean", "a mountain landscape at dawn", ...]
}
```

**TAG_BANK:**
```python
{
    "word_bank_path": "/path/to/custom/word_banks",
    "topic_tags": "{\"sunset\": {\"content\": [\"beach\", \"horizon\"]}}"
}
```

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

Save As, Webhook, and LLM Config work independently in any workflow — no pipeline required. Drop them into any ComfyUI graph and they function as standalone utility nodes.

## License

MIT
