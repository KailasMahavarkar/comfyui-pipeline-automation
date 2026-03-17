# ComfyUI Pipeline Automation

[![CI](https://github.com/KailasMahavarkar/comfyui-pipeline-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/KailasMahavarkar/comfyui-pipeline-automation/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Automated batch image generation for ComfyUI. Turns manual one-at-a-time workflows into unattended, crash-proof production pipelines that can generate thousands of organized, metadata-rich outputs overnight.

## Installation

Clone into your ComfyUI `custom_nodes` directory:

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

### API Key Setup

On first load, the node pack creates `ComfyUI/input/automation_api_keys.json` with empty placeholders:

```json
{
  "openrouter": "",
  "openai": "",
  "ollama_local": "",
  "ollama_cloud": "",
  "lm_studio": ""
}
```

Fill in your keys. The file is never stored in workflow JSON — only the key **name** is saved, so workflows are safe to share.

## Pipeline Flow

![Pipeline Flow](docs/pipeline-flow.png)

### How It Works

1. **Gap Scanner** scans the output folder and finds the next missing topic/resolution/variant combo
2. **Prompt Generator** picks the prompt for that slot using local mutation strategies, cached to disk
3. **Prompt Refiner** (optional) enhances the prompt via an LLM, using config from a **Provider Node**
4. Standard ComfyUI nodes (CLIP Encode, KSampler, VAE Decode) generate the image
5. **Save As** saves with organized naming, embedded metadata, and optional sidecar/manifest
6. **CRON Scheduler** re-queues the workflow on schedule
7. On next run, Gap Scanner advances to the next missing entry
8. When all gaps are filled, `is_complete` goes true and CRON Scheduler stops

The filesystem is the source of truth — if ComfyUI crashes, restart and the pipeline resumes exactly where it left off.

## Nodes

| Node | What it does |
|------|-------------|
| **Gap Scanner** | Scans output directory, finds next missing topic/resolution/variant, emits `PIPELINE_CONFIG` |
| **Prompt Generator** | Generates prompt variants via local mutation strategies from `PIPELINE_CONFIG` |
| **Prompt Refiner** | Enhances prompts via LLM, takes `LLM_CONFIG` from a Provider node |
| **OpenRouter Provider** | Builds `LLM_CONFIG` for OpenRouter API |
| **OpenAI Provider** | Builds `LLM_CONFIG` for OpenAI API |
| **Ollama Provider** | Builds `LLM_CONFIG` for Ollama (local or cloud) |
| **CRON Scheduler** | Re-queues workflow on schedule, stops when pipeline is complete |
| **Save As** | Saves images with template naming, embedded metadata, sidecar JSON, manifest CSV |
| **Webhook** | Calls any REST API with retry, response extraction, and `{topic}` templating |

Full input/output reference: [docs/nodes.md](docs/nodes.md)

## Output Structure

```
output/
└── my_workflow/
    ├── .prompt_cache/
    │   └── sunset_beach.json
    ├── sunset_beach/
    │   └── 512x512/
    │       ├── comfyui_20240101_120000.png
    │       └── comfyui_20240101_120000.json   (sidecar, optional)
    └── manifest.csv                            (optional)
```

## Standalone Use

Save As, Webhook, and the Provider nodes work independently in any workflow — no pipeline required.

## License

MIT
