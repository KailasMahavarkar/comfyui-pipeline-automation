# Architecture

## Nodes (6)

### Core Pipeline (4)

| Node | Job | Inputs | Outputs |
|------|-----|--------|---------|
| **Gap Scanner** | Scans filesystem, emits next missing slot | workflow_name, topic_list, resolution_list, prompts_per_topic | width, height, is_complete, status, pipeline_config |
| **Prompt Generator** | Picks variant for current slot via mutations | pipeline_config, base_prompt_template, base_negative_prompt | prompt, negative_prompt, metadata |
| **CRON Scheduler** | Re-queues workflow on interval | is_complete, schedule_preset, comfyui_api_url | status |
| **Save As** | Saves image with structured naming + metadata | image, format, quality, naming_preset, metadata | saved_paths |

### Optional (2)

| Node | Job | Inputs | Outputs |
|------|-----|--------|---------|
| **Prompt Refiner** | LLM enhances prompt + generates negative | prompt, negative_prompt, metadata, provider, model, api_key | refined_prompt, refined_negative, metadata (passthrough) |
| **Webhook** | REST API calls with retry | url, method | response, status_code, extracted |

## Data Flow

### Without Prompt Refiner

```
Gap Scanner → pipeline_config → Prompt Generator → prompt          → CLIP Encode (+)
            → width           → Empty Latent      → negative_prompt → CLIP Encode (−)
            → height          → Empty Latent      → metadata        → Save As
            → is_complete     → CRON Scheduler
```

### With Prompt Refiner

```
Gap Scanner → pipeline_config → Prompt Generator → prompt          → Prompt Refiner → refined_prompt  → CLIP Encode (+)
            → width           → Empty Latent      → negative_prompt → Prompt Refiner → refined_negative → CLIP Encode (−)
            → height          → Empty Latent      → metadata        → Prompt Refiner → metadata         → Save As
            → is_complete     → CRON Scheduler
```

## Custom Types

### PIPELINE_CONFIG

Produced by Gap Scanner. Consumed by Prompt Generator. Carries all per-execution state.

```python
{
    "workflow_name": "nature_photos",
    "output_dir": "output",
    "format": "png",
    "prompts_per_topic": 5,
    "topic": "sunset beach",
    "resolution": "512x512",
    "variant_index": 3,
}
```

### Metadata (JSON string)

Produced by Prompt Generator. Passes through Prompt Refiner. Consumed by Save As.

```python
{
    "prompt": "sunset beach, sharp focus, golden hour lighting",
    "negative_prompt": "blurry, low quality, watermark",
    "tags": {"content": [...], "style": [...], "mood": [...], "technical": [...]},
    "tag_sources": {"prompt_extraction": [...], "topic_bank": [...]},
    "pipeline": {
        "workflow_name": "nature_photos",
        "output_dir": "output",
        "format": "png",
        "topic": "sunset_beach",
        "resolution": "512x512",
        "variant_index": 3,
        "variant_strategy": "style_shuffle",
        "total_variants": 5
    }
}
```

## Output Structure

```
output/
└── nature_photos/                    ← workflow_name
    ├── .prompt_cache/                ← mutation variants cached per topic
    │   ├── sunset_beach.json
    │   └── coral_reef.json
    ├── sunset_beach/                 ← topic (sanitized)
    │   └── 512x512/                  ← resolution
    │       ├── comfyui_20260317_143052.png
    │       ├── comfyui_20260317_143201.png
    │       └── ...
    ├── coral_reef/
    │   └── 512x512/
    │       └── ...
    └── manifest.csv                  ← optional global index
```

**Scanner counts files per `topic/resolution/` directory.** Filename format doesn't matter. 5 files = 5 variants done.

## Pipeline Loop

```
User presses Queue Prompt
  → Execution 1: Gap Scanner finds variant_index=0 → generate → save
  → CRON re-queues
  → Execution 2: Gap Scanner finds variant_index=1 → generate → save
  → ...
  → Execution N: Gap Scanner finds no gaps → is_complete=True → CRON stops
```

**Crash recovery:** Restart ComfyUI, press Queue. Scanner rescans filesystem, picks up where it left off.

**Cancel:** Click Cancel in ComfyUI. CRON detects incomplete execution via /history, stops re-queuing.

## Naming Presets

| Preset | Template | Example |
|--------|----------|---------|
| Simple | `{prefix}_{date}_{time}` | `comfyui_20260317_143052.png` |
| Detailed | `{prefix}_{topic}_{resolution}_{counter}` | `comfyui_sunset_512x512_0003.png` |
| Minimal | `{prefix}_{counter}` | `comfyui_0003.png` |
| Custom | user-defined | anything |

**Tokens:** `{prefix}`, `{topic}`, `{date}`, `{time}`, `{datetime}`, `{resolution}`, `{width}`, `{height}`, `{counter}`, `{batch}`, `{format}`

## Prompt Generation

### Mutation Strategies (6)

| Strategy | What it does |
|----------|-------------|
| synonym_swap | Replaces adjectives with synonyms from word bank |
| detail_injection | Appends random scene detail |
| style_shuffle | Swaps/appends style modifier |
| weight_jitter | Adds `(clause:1.2)` emphasis weights |
| reorder | Shuffles clause order (keeps subject first) |
| template_fill | Fills `{mood}`, `{detail}`, `{style}` wildcards |

All 50 variants generated once per topic, cached to `.prompt_cache/{topic}.json`.

### Prompt Refiner (LLM)

- 1 API call per image when connected
- Writes natural scene descriptions (2-3 sentences), not comma-separated keywords
- Generates context-aware negative prompt
- Cached per input prompt (crash recovery doesn't re-call)
- Falls back to original prompt on failure
- Content safety: transforms dark themes into wholesome scenes

### Tag Generation (2 layers)

| Layer | Source | Cost |
|-------|--------|------|
| 1 | Extract words from prompt | Free, instant |
| 2 | Topic bank lookup | Free, instant |

## Metadata Embedding

| Format | Method |
|--------|--------|
| PNG | tEXt chunk (`comfyui_metadata` key) |
| JPEG | EXIF ImageDescription |
| WebP | XMP dc:description |

## Provider Presets (Prompt Refiner)

| Provider | URL |
|----------|-----|
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` |
| OpenAI | `https://api.openai.com/v1/chat/completions` |
| Ollama | `http://localhost:11434/v1/chat/completions` |
| LM Studio | `http://localhost:1234/v1/chat/completions` |
| Custom | user-provided via `api_url_override` |

## Lib Modules

| Module | Purpose |
|--------|---------|
| `scanner.py` | GapScanner class — filesystem gap detection with integrity checking |
| `prompt_mutations.py` | 6 mutation strategies + variant generation |
| `tag_generator.py` | 2-layer tag extraction pipeline |
| `naming.py` | Filename template resolution with presets |
| `metadata.py` | Per-format metadata embedding (PNG/JPEG/WebP) |
| `sidecar.py` | JSON sidecar writer/reader |
| `manifest.py` | Thread-safe CSV manifest |
| `response_parser.py` | JSON parsing, dot-path walking, code block stripping |
