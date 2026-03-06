\# ComfyUI Pipeline Automation Node Pack — Build Plan



\*\*Project:\*\* comfyui-pipeline-automation

\*\*Version:\*\* 1.0

\*\*Date:\*\* March 5, 2026



---



\## 1. Executive Summary



A five-node custom node pack for ComfyUI that turns manual, one-at-a-time image generation into a fully automated, self-healing production pipeline. Designed to handle jobs at the scale of 150 topics × 50 prompt variants × 10 resolutions = 75,000 outputs — unattended, resumable, and fully traceable.



The three core pipeline nodes (CRON Scheduler, Pipeline Controller, Save As) give users an end-to-end batch system that runs overnight, recovers from crashes, and produces organized outputs with rich searchable metadata. Two additional standalone nodes (API Call, Bulk Prompter) serve as reusable utilities.



---



\## 2. Problem Statement



Three problems ComfyUI doesn't solve natively:



\*\*No automation.\*\* Every workflow run requires a manual "Queue Prompt" click. There is no way to schedule recurring runs or batch thousands of generations.



\*\*No organized output.\*\* Images save with random hashes or sequential counters. At scale, output folders become unsearchable. There is no metadata, no tagging, no traceability from output back to the prompt and parameters that produced it.



\*\*No state across runs.\*\* ComfyUI is stateless — each workflow execution has no memory of previous runs. Batch iteration (cycling through topics, prompts, resolutions) requires external tooling.



---



\## 3. Architecture



\### 3.1 Design Principles



\- \*\*Filesystem as state.\*\* No in-memory pointers, no databases. The output folder IS the source of truth. If a file exists, it's done. If it doesn't, it needs to be generated. This makes the system crash-proof and self-healing by design.

\- \*\*Stay inside ComfyUI.\*\* All logic lives in custom nodes. No external scripts, no separate services. Everything is visual and configurable through the node graph.

\- \*\*Centralized brain.\*\* Pipeline Controller is the single orchestrator. It owns topic iteration, prompt generation, tag generation, and gap detection. Other nodes are simple — they receive instructions and execute.

\- \*\*Non-destructive to ComfyUI.\*\* No monkey-patching internals. State management uses official mechanisms: `IS\_CHANGED` for cache busting, `PromptServer` for API routes, standard file I/O. Compatible with all existing nodes and workflows.



\### 3.2 Node Overview



| # | Node | Role | In Pipeline? | Standalone? |

|---|---|---|---|---|

| 1 | ⏰ CRON Scheduler | Re-queues workflow on cron schedule | Yes | Yes |

| 2 | 🎛️ Pipeline Controller | Filesystem scanning, prompt generation, tag generation, orchestration | Yes | No |

| 3 | 💾 Save As | Organized saving with naming templates, metadata, tags, sidecar, manifest | Yes | Yes |

| 4 | 🌐 API Call | Calls external LLM or any REST API | Optional | Yes |

| 5 | 📝 Bulk Prompter | Generates N prompt variants locally | Internal to Controller | Yes |



For the 75K pipeline, the user drops \*\*3 custom nodes\*\* in the graph: CRON Scheduler → Pipeline Controller → Save As. The rest of the graph is standard ComfyUI (CLIP Encode, KSampler, VAE Decode).



\### 3.3 Pipeline Data Flow



```

CRON tick

&nbsp; → Pipeline Controller:

&nbsp;     1. Compute workflow fingerprint → check collision

&nbsp;     2. Scan filesystem → find first gap

&nbsp;     3. If new topic:

&nbsp;          → Generate N prompt variants (Bulk Prompter logic)

&nbsp;          → Generate tags (3-layer pipeline)

&nbsp;          → Cache to .prompt\_cache/

&nbsp;     4. Read cached prompt + tags for current gap

&nbsp;     5. Output: topic, prompt, neg\_prompt, width, height, metadata, status

&nbsp; → CLIP Encode (prompt + negative)

&nbsp; → KSampler (user configures seed/steps/cfg directly)

&nbsp; → VAE Decode

&nbsp; → Save As:

&nbsp;     1. Resolve naming template → filename

&nbsp;     2. Create subfolder if needed

&nbsp;     3. Save media file

&nbsp;     4. Embed flat tags + prompt in image metadata

&nbsp;     5. Write sidecar JSON (if enabled)

&nbsp;     6. Append manifest.csv (if enabled)

&nbsp; → CRON checks is\_complete → stop or schedule next

```



\### 3.4 Wiring Diagram



```

&nbsp; ⏰ CRON ←── is\_complete ──┐

&nbsp;   │                        │

&nbsp;   ↓ re-queues              │

&nbsp;                            │

&nbsp; 🎛️ Pipeline Controller ───┘

&nbsp;   │

&nbsp;   ├── prompt ──────→ CLIP Encode (pos)

&nbsp;   ├── negative ────→ CLIP Encode (neg)

&nbsp;   ├── width ───────→ Empty Latent

&nbsp;   ├── height ──────→ Empty Latent

&nbsp;   ├── metadata ────→ 💾 Save As

&nbsp;   │

&nbsp;   │   KSampler ← user configures directly

&nbsp;   │       │

&nbsp;   │   VAE Decode

&nbsp;   │       │

&nbsp;   └───────────────→ 💾 Save As ← IMAGE

```



4 wires from Pipeline Controller. KSampler remains fully standard.



---



\## 4. Node Specifications



\### 4.1 ⏰ CRON Scheduler



Starts a daemon background thread that re-queues the current workflow via ComfyUI's `/prompt` API on a cron schedule.



\*\*Inputs:\*\*



| Input | Type | Default | Description |

|---|---|---|---|

| `schedule\_preset` | Dropdown | `Custom` | Options: Custom, Every 1 min, Every 5 min, Every 15 min, Every 30 min, Hourly, Every 6 hours, Daily at midnight, Daily at 9 AM. When not Custom, overrides cron\_expression. |

| `cron\_expression` | STRING | `\*/5 \* \* \* \*` | Standard 5-field cron. Only used when preset = Custom. |

| `enabled` | BOOLEAN | False | Master on/off. Turning off kills background thread immediately. |

| `mode` | Dropdown | `requeue\_workflow` | `requeue\_workflow` / `run\_command` / `both` |

| `external\_command` | STRING | `""` | Shell command to run on each tick. 5-minute timeout. |

| `comfyui\_api\_url` | STRING | `http://127.0.0.1:8188` | ComfyUI server URL. |

| `max\_iterations` | INT | 0 | Max runs. 0 = unlimited. |

| `passthrough` | IMAGE | — | Optional, for inline wiring. |



\*\*Outputs:\*\*



| Output | Type | Description |

|---|---|---|

| `status` | STRING | e.g. `"ON | every 5 min | next: 2026-03-05T14:35:00 | runs: 12"` |

| `passthrough` | IMAGE | Unchanged pass-through. |



\*\*Key behaviors:\*\*



\- \*\*Skip-if-busy guard:\*\* Before re-queuing, calls `GET /queue`. If running or pending queue is non-empty, skips that tick and logs a warning. Prevents pile-up.

\- \*\*Single-instance lock:\*\* Only one scheduler thread per ComfyUI session. Re-executing kills old thread before starting new one.

\- \*\*DONE signal:\*\* Accepts `is\_complete` from Pipeline Controller. When True, stops scheduling.

\- \*\*Daemon thread:\*\* Dies automatically when ComfyUI process exits.



\*\*Cache busting:\*\* Uses `IS\_CHANGED` returning `float("nan")` to force re-execution every run.



---



\### 4.2 🎛️ Pipeline Controller



The brain of the pipeline. Scans the filesystem for gaps, generates prompts and tags for new topics, and outputs parameters for the next missing entry.



\*\*Inputs:\*\*



| Input | Type | Default | Description |

|---|---|---|---|

| `workflow\_name` | STRING | (required, no default) | Identifies this pipeline. Sanitized to filesystem-safe string. Used as root folder name. |

| `topic\_list` | STRING (multiline) | — | One topic per line. e.g. 150 topics. |

| `resolution\_list` | STRING (multiline) | — | One per line: `512x512`, `768x768`, `1024x576`, etc. |

| `prompts\_per\_topic` | INT | 50 | Number of prompt variants to generate per topic. |

| `base\_prompt\_template` | STRING | — | Base prompt with `{topic}` placeholder. e.g. `"a beautiful {topic}, highly detailed"` |

| `base\_negative\_prompt` | STRING | — | Shared negative prompt. |

| `queue\_order` | Dropdown | `sequential` | `sequential` / `interleaved` / `shuffled` |

| `vary\_negative` | BOOLEAN | False | When True, Bulk Prompter applies light variation to negative prompt. |

| `generate\_tags\_via\_llm` | BOOLEAN | True | When True, calls LLM for smart tags on first encounter of each topic. |

| `llm\_config` | STRING | — | API url + key + model for tag generation. |

| `custom\_word\_bank\_path` | STRING | `""` | Path to user's custom word bank .txt files. Merges with defaults. |

| `topic\_tag\_bank` | STRING (multiline) | `""` | Optional JSON mapping topics to curated tags. |

| `reset\_workflow` | BOOLEAN | False | Force fresh start. Deletes existing outputs and caches. |



\*\*Outputs:\*\*



| Output | Type | Wires to |

|---|---|---|

| `prompt` | STRING | CLIP Text Encode (positive) |

| `negative\_prompt` | STRING | CLIP Text Encode (negative) |

| `width` | INT | Empty Latent Image |

| `height` | INT | Empty Latent Image |

| `metadata` | STRING | Save As (single JSON blob) |

| `is\_complete` | BOOLEAN | CRON Scheduler (stop signal) |

| `status` | STRING | Display/debugging |



\*\*The metadata output\*\* is a single JSON string containing everything Save As needs for the sidecar:



```json

{

&nbsp; "prompt": "a golden sunset over calm ocean waves...",

&nbsp; "negative\_prompt": "blurry, watermark, text...",

&nbsp; "tags": {

&nbsp;   "content": \["sunset", "ocean", "waves"],

&nbsp;   "style": \["cinematic", "photorealistic"],

&nbsp;   "mood": \["serene", "peaceful"],

&nbsp;   "technical": \["512x512"]

&nbsp; },

&nbsp; "tag\_sources": {

&nbsp;   "prompt\_extraction": \["sunset", "ocean"],

&nbsp;   "topic\_bank": \["beach", "horizon"],

&nbsp;   "llm\_generated": \["light\_rays", "warm\_palette"]

&nbsp; },

&nbsp; "pipeline": {

&nbsp;   "workflow\_name": "realistic\_landscapes",

&nbsp;   "topic": "sunset\_beach",

&nbsp;   "variant\_index": 23,

&nbsp;   "variant\_strategy": "synonym\_swap",

&nbsp;   "total\_variants": 50,

&nbsp;   "global\_index": 23451,

&nbsp;   "global\_total": 75000

&nbsp; }

}

```



\*\*Key behaviors:\*\*



\- \*\*Filesystem scanning (gap detection):\*\* Each run, scans the output folder, compares against the planned matrix (topics × resolutions × prompts\_per\_topic), and outputs parameters for the first missing entry. See section 6.2 for integrity checking.

\- \*\*Prompt generation:\*\* On first encounter of a topic with no cached prompts, calls Bulk Prompter logic internally to generate N variants. Caches results to `.prompt\_cache/{topic}.json`.

\- \*\*Tag generation:\*\* On first encounter of a topic, runs the 3-layer tag pipeline (prompt extraction → topic bank → LLM). Caches alongside prompts.

\- \*\*Workflow fingerprint + collision detection:\*\* On first run, computes a fingerprint from the workflow's node types and connections and saves it to `.workflow\_fingerprint`. On subsequent runs, compares current fingerprint to saved. Mismatch = hard block with actionable error message. See section 6.1.

\- \*\*Cache busting:\*\* `IS\_CHANGED` returns the current gap index so ComfyUI always re-executes.

\- \*\*Incremental scan optimization:\*\* Full filesystem scan on first run/restart. After each successful save, updates an in-memory cache of existing files. Per-run cost drops to near zero after startup.



---



\### 4.3 💾 Save As



Universal save node for image, audio, and video with template-based naming, embedded metadata, optional sidecar JSON, and optional manifest CSV.



\*\*Inputs:\*\*



| Input | Type | Default | Description |

|---|---|---|---|

| `output\_type` | Dropdown | `image` | `image` / `audio` / `video` |

| `format` | Dropdown | `png` | `png` / `jpeg` / `webp` / `wav` / `mp3` / `mp4` / `gif` |

| `quality` | INT | 95 | 1–100 for lossy formats. |

| `image` | IMAGE | — | Required for image/video. |

| `audio` | AUDIO | — | Required for audio. |

| `fps` | INT | 24 | For video output. |

| `naming\_preset` | Dropdown | `Detailed` | `Custom` / `Simple ({prefix}\_{date}\_{time})` / `Detailed ({prefix}\_{topic}\_{resolution}\_{counter})` / `Minimal ({prefix}\_{counter})` |

| `naming\_template` | STRING | — | Free-text override when preset = Custom. |

| `filename\_prefix` | STRING | `comfyui` | Fills `{prefix}` token. |

| `subfolder\_template` | STRING | `{topic}/{resolution}` | Supports same tokens as naming\_template. |

| `metadata` | STRING | — | JSON string from Pipeline Controller. |

| `embed\_metadata` | BOOLEAN | True | Embed flat tags + prompt in file metadata. |

| `write\_sidecar` | BOOLEAN | False | Write .json sidecar alongside each output. |

| `write\_manifest` | BOOLEAN | False | Append to manifest.csv in workflow root. |



\*\*Outputs:\*\*



| Output | Type | Description |

|---|---|---|

| `saved\_paths` | STRING | Comma-separated list of saved files. |



\*\*Naming template tokens:\*\*



| Token | Resolves to |

|---|---|

| `{prefix}` | filename\_prefix input value |

| `{topic}` | Topic from metadata |

| `{date}` | YYYYMMDD |

| `{time}` | HHMMSS |

| `{datetime}` | YYYYMMDD\_HHMMSS |

| `{resolution}` | `{width}x{height}` from image tensor |

| `{width}` | Image width |

| `{height}` | Image height |

| `{counter}` | Auto-incrementing per session |

| `{batch}` | Batch index (0000, 0001...) |

| `{format}` | File extension |



Unresolved tokens are replaced with `unknown`.



\*\*Metadata embedding per format:\*\*



| Format | Method |

|---|---|

| PNG | tEXt chunk under key `comfyui\_metadata` |

| JPEG | EXIF `ImageDescription` field via piexif |

| WebP | XMP data blob |

| WAV | ID3 COMM tag via mutagen |

| MP3 | ID3 COMM + TXXX custom tags via mutagen |

| MP4 | ffmpeg `-metadata comment=...` |

| GIF | GIF comment extension |



\*\*Sidecar JSON structure:\*\*



```json

{

&nbsp; "prompt": "a golden sunset over calm ocean waves...",

&nbsp; "negative\_prompt": "blurry, watermark, text...",

&nbsp; "tags": {

&nbsp;   "content": \["sunset", "ocean", "waves", "beach", "horizon", "sky"],

&nbsp;   "style": \["cinematic", "photorealistic", "warm\_palette"],

&nbsp;   "mood": \["serene", "peaceful", "contemplative"],

&nbsp;   "technical": \["512x512"]

&nbsp; },

&nbsp; "tag\_sources": {

&nbsp;   "prompt\_extraction": \["sunset", "ocean", "waves"],

&nbsp;   "topic\_bank": \["beach", "horizon"],

&nbsp;   "llm\_generated": \["light\_rays", "warm\_palette"]

&nbsp; },

&nbsp; "pipeline": {

&nbsp;   "workflow\_name": "realistic\_landscapes",

&nbsp;   "topic": "sunset\_beach",

&nbsp;   "variant\_index": 23,

&nbsp;   "variant\_strategy": "synonym\_swap",

&nbsp;   "total\_variants": 50,

&nbsp;   "global\_index": 23451,

&nbsp;   "global\_total": 75000

&nbsp; },

&nbsp; "file": {

&nbsp;   "filename": "sunset\_beach\_512x512\_023.png",

&nbsp;   "format": "png",

&nbsp;   "path": "realistic\_landscapes/sunset\_beach/512x512/sunset\_beach\_512x512\_023.png",

&nbsp;   "saved\_at": "2026-03-05T14:30:22"

&nbsp; }

}

```



Note: `workflow.json` is saved once at the workflow root, NOT embedded per file.



\*\*Manifest CSV format:\*\*



```csv

topic,resolution,variant\_index,filename,path,tags,saved\_at

sunset\_beach,512x512,23,sunset\_beach\_512x512\_023.png,sunset\_beach/512x512/sunset\_beach\_512x512\_023.png,sunset|ocean|waves|cinematic|serene,2026-03-05T14:30:22

```



---



\### 4.4 🌐 API Call (Standalone)



Calls external LLM or any REST API. OpenAI-compatible as default preset with generic override for any endpoint.



\*\*Inputs:\*\*



| Input | Type | Default | Description |

|---|---|---|---|

| `api\_preset` | Dropdown | `openai\_compatible` | `openai\_compatible` / `generic` |

| `api\_url` | STRING | — | Endpoint URL |

| `api\_key` | STRING | `""` | Bearer token (optional) |

| `method` | Dropdown | `POST` | `POST` / `GET` |

| `request\_template` | STRING (multiline) | — | JSON body with `{topic}` placeholder support |

| `response\_mapping` | STRING (multiline) | — | Dot-path notation for extracting values from response |

| `headers` | STRING (multiline) | `""` | Custom headers as JSON (for generic mode) |

| `topic` | STRING | — | Injected into request\_template |

| `timeout` | INT | 30 | Request timeout in seconds |

| `max\_retries` | INT | 3 | Configurable retry count |

| `retry\_delay` | INT | 2 | Seconds between retries, doubles each attempt (exponential backoff) |



\*\*Outputs:\*\*



| Output | Type | Description |

|---|---|---|

| `prompt` | STRING | Extracted prompt value |

| `negative\_prompt` | STRING | Extracted negative\_prompt value |

| `metadata` | STRING | Full JSON dict of all extracted key:values |

| `raw\_response` | STRING | Complete API response for debugging |



\*\*Key behaviors:\*\*



\- \*\*Response mapping\*\* uses dot-path notation: `choices.0.message.content.prompt`

\- \*\*Auto-parses stringified JSON\*\* inside response fields (common with LLMs wrapping JSON in `message.content`)

\- \*\*Strips markdown code blocks\*\* from LLM responses before parsing

\- \*\*Exponential backoff\*\* on retries: delay × 2^attempt



---



\### 4.5 📝 Bulk Prompter (Standalone)



Generates N prompt variants from a base prompt using local mutation strategies. Zero API calls.



\*\*Inputs:\*\*



| Input | Type | Default | Description |

|---|---|---|---|

| `base\_prompt` | STRING | — | Seed prompt to mutate |

| `num\_variants` | INT | 10 | How many variants to generate |

| `strategies` | Multi-dropdown | all enabled | `synonym\_swap` / `detail\_injection` / `style\_shuffle` / `weight\_jitter` / `reorder` / `template\_fill` |



\*\*Outputs:\*\*



| Output | Type | Description |

|---|---|---|

| `variants` | STRING | JSON array of all generated prompts |

| `count` | INT | Number of variants generated |



\*\*Mutation strategies:\*\*



| Strategy | What it does | Draws from |

|---|---|---|

| `synonym\_swap` | Replaces descriptive words with synonyms | `adjectives.txt` |

| `detail\_injection` | Appends random compatible scene details | `scene\_details.txt` |

| `style\_shuffle` | Appends/swaps style modifiers | `styles.txt` |

| `weight\_jitter` | Randomly adjusts emphasis weights (1.0–1.4 range) | No word bank |

| `reorder` | Shuffles clause order in prompt | No word bank |

| `template\_fill` | Fills `{mood}`, `{detail}`, `{style}` wildcards | All banks |



Note: When called internally by Pipeline Controller, the logic is identical but operates on the base\_prompt\_template with `{topic}` resolved.



---



\## 5. Tag Generation System



\### 5.1 Three-Layer Pipeline



Tags are generated once per topic (150 times total, not 75K) and cached.



\*\*Layer 1: Prompt extraction (always on, free, instant)\*\*



Splits prompt by commas, strips filler words, normalizes. Produces 5–8 tags.



```

Input:  "a golden sunset over calm ocean waves, cinematic lighting"

Output: \[sunset, golden, ocean, waves, calm, cinematic, lighting]

```



\*\*Layer 2: Topic tag bank (always on, free, instant)\*\*



Reads curated tags from the optional `topic\_tag\_bank` JSON input. Produces 5–7 tags if available.



```json

{

&nbsp; "sunset\_beach": {

&nbsp;   "content": \["sunset", "beach", "ocean", "waves", "sand", "horizon", "sky"],

&nbsp;   "mood": \["serene", "warm", "peaceful"],

&nbsp;   "category": \["landscape", "nature"]

&nbsp; }

}

```



\*\*Layer 3: LLM generation (on-the-fly, once per topic)\*\*



Calls the LLM API with the base prompt and topic. Asks for categorized tags. Produces 8–10 tags.



If the LLM call fails: retries 3 times, then falls back to Layers 1 + 2 only. Logs the failure in tag\_sources.



\### 5.2 Tag Categories



All tags are categorized into four groups:



| Category | Examples |

|---|---|

| `content` | sunset, ocean, waves, beach, horizon, sky |

| `style` | cinematic, photorealistic, warm\_palette, film\_grain |

| `mood` | serene, peaceful, contemplative |

| `technical` | 512x512 (derived from resolution) |



\### 5.3 Tag Storage



\- \*\*Sidecar JSON:\*\* Full categorized tags + provenance (tag\_sources)

\- \*\*Embedded metadata:\*\* Flat tag list (all categories merged)

\- \*\*Manifest CSV:\*\* Pipe-delimited flat list



---



\## 6. Safety Mechanisms



\### 6.1 Workflow Fingerprint + Collision Detection



\*\*Purpose:\*\* Prevent two different workflows from writing to the same `workflow\_name` folder.



\*\*Fingerprint includes:\*\*



| Included | Excluded |

|---|---|

| Node types present in graph | Seeds / random values |

| Node connections (edges) | Prompt text / negative prompt |

| Checkpoint / model filenames | CFG scale, steps, sampler |

| LoRA names | LoRA weights |

| workflow\_name | Quality, format settings |

| Output type | Filename prefix, subfolder |



\*\*Behavior:\*\*



\- First run: compute fingerprint, save to `output/{workflow\_name}/.workflow\_fingerprint`

\- Every subsequent run: compute current fingerprint, compare to saved

\- \*\*Match\*\* → same workflow resuming → allow

\- \*\*Mismatch\*\* → different workflow reusing name → hard block with error:



```

BLOCKED: workflow\_name "my\_project" is already in use by a different workflow.



Existing fingerprint (created 2026-03-04):

&nbsp; - Nodes: KSampler, CLIP Encode, SDXL Checkpoint

&nbsp; - Checkpoint: dreamshaperXL.safetensors



Current fingerprint:

&nbsp; - Nodes: KSampler, CLIP Encode, Flux Checkpoint

&nbsp; - Checkpoint: flux\_dev.safetensors



Options:

&nbsp; 1. Choose a different workflow\_name

&nbsp; 2. Delete output/my\_project/ to release the name

&nbsp; 3. Set reset\_workflow=True to overwrite

```



\### 6.2 File Integrity Checking



The scanner must determine whether an existing file counts as "done."



\*\*Default (every run): Level 2 — existence + size + header\*\*



\- File must exist

\- File must be > 1KB

\- First bytes must match expected format header:

&nbsp; - PNG: `\\x89PNG\\r\\n\\x1a\\n`

&nbsp; - JPEG: `\\xff\\xd8`

&nbsp; - WebP: bytes 8–12 = `WEBP`

\- Cost: ~0.1ms per file



\*\*On restart: Level 3 for recent files\*\*



\- Files modified in the last hour get full Pillow decode validation

\- Catches truncated image data from mid-write crashes

\- Older files get Level 2 only



\*\*Corrupt files:\*\* Deleted and treated as gaps. Next run regenerates.



\### 6.3 Strike Counter



Tracks repeated failures per entry in `output/{workflow\_name}/.failures.json`:



```json

{

&nbsp; "sunset\_beach/512x512/sunset\_beach\_512x512\_023": {

&nbsp;   "attempts": 3,

&nbsp;   "last\_error": "2026-03-05T18:42:15",

&nbsp;   "skipped": true

&nbsp; }

}

```



\- Attempts 1–3: Retry (different seed each time for random seed mode)

\- After 3 failures: Mark as skipped, move to next gap

\- Skipped entries are logged for later investigation



\### 6.4 Skip-If-Busy Guard



CRON Scheduler calls `GET /queue` before re-queuing. If running or pending queue is non-empty, skips that tick. Prevents generation pile-up when jobs take longer than the cron interval.



---



\## 7. Error Handling



| Failure | Strategy | Batch continues? |

|---|---|---|

| LLM API fails (tag generation) | Retry 3×, fall back to Layer 1+2 tags only | Yes |

| Black/corrupt image generation | Retry 3× with new seed, then skip via strike counter | Yes |

| Disk full | Hard stop, halt signal to CRON | No |

| ComfyUI crash | Automatic resume via filesystem scan on restart | Yes |

| Network drop during LLM call | Retry 3× with backoff, fall back to local tags | Yes |



\*\*Design principle:\*\* The batch never stops unless it physically cannot continue (disk full). Everything else is retry → fallback → skip → log.



---



\## 8. Progress Visibility



Three levels, all implemented:



\*\*Level A: Status output\*\*



Pipeline Controller `status` output string:



```

realistic\_landscapes | topic 4/150 (sunset\_beach) | prompt 23/50 | res 3/10 | global 1,823/75,000 (2.4%) | ETA: 14h 22m | 3 skipped | 0 errors

```



Wire to a Display node in ComfyUI UI.



\*\*Level B: Progress log file\*\*



Written to `output/{workflow\_name}/.progress.log`:



```

\[2026-03-05 14:30:22] START | 75,000 total entries

\[2026-03-05 14:35:18] PROGRESS | 100/75,000 (0.1%) | ~2.1 img/min | ETA: 595h

\[2026-03-05 15:00:05] TOPIC\_COMPLETE | sunset\_beach (500/500)

\[2026-03-05 15:00:06] TOPIC\_START | mountain\_fog

\[2026-03-05 15:30:12] SKIP | mountain\_fog\_768x768\_041 | 3 failed attempts

\[2026-03-05 18:42:15] HALT | Disk full

```



Viewable via `tail -f`, works headless and over SSH.



\*\*Level C: Custom API route\*\*



Registered on ComfyUI's server:



```

GET /pipeline/status → JSON response with full progress details

```



Pollable from browser, phone, or external dashboard.



---



\## 9. Runtime Filesystem Structure



```

output/

├── realistic\_landscapes/                           ← workflow\_name

│   ├── workflow.json                               ← saved once

│   ├── .workflow\_fingerprint                       ← collision detection

│   ├── .failures.json                              ← strike counter

│   ├── .progress.log                               ← progress log

│   ├── .prompt\_cache/

│   │   ├── sunset\_beach.json                       ← 50 prompts + tags

│   │   ├── mountain\_fog.json

│   │   └── ... (150 files)

│   ├── sunset\_beach/

│   │   ├── 512x512/

│   │   │   ├── sunset\_beach\_512x512\_001.png

│   │   │   ├── sunset\_beach\_512x512\_001.json       ← sidecar (optional)

│   │   │   └── ... (50 files)

│   │   ├── 768x768/

│   │   │   └── ...

│   │   └── ... (10 resolution folders)

│   ├── mountain\_fog/

│   │   └── ...

│   ├── ... (150 topic folders)

│   └── manifest.csv                                ← global index

```



---



\## 10. Code Structure



```

comfyui-pipeline-automation/

├── \_\_init\_\_.py                     ← Registers all 5 nodes

├── cron\_scheduler.py               ← ⏰ CRON Scheduler node

├── pipeline\_controller.py          ← 🎛️ Pipeline Controller node

├── save\_as.py                      ← 💾 Save As node

├── api\_call.py                     ← 🌐 API Call node (standalone)

├── bulk\_prompter\_node.py           ← 📝 Bulk Prompter node (standalone)

├── lib/

│   ├── \_\_init\_\_.py

│   ├── bulk\_prompter.py            ← Prompt variation engine (shared logic)

│   ├── tag\_generator.py            ← 3-layer tag pipeline

│   ├── scanner.py                  ← Filesystem gap detection + integrity checks

│   ├── fingerprint.py              ← Workflow fingerprint + collision check

│   ├── naming.py                   ← Filename template token resolver

│   ├── metadata.py                 ← Per-format metadata embedding

│   ├── sidecar.py                  ← .json sidecar writer

│   ├── manifest.py                 ← CSV manifest append

│   └── response\_parser.py          ← Dot-path JSON walker (for API Call)

├── word\_banks/

│   ├── adjectives.txt              ← ~200 entries, categorized

│   ├── styles.txt                  ← ~100 entries

│   ├── moods.txt                   ← ~60 entries

│   └── scene\_details.txt           ← ~150 entries

├── requirements.txt

└── README.md

```



---



\## 11. Build Phases



\### Phase 1: Foundation (lib/ modules)



Build the shared library layer first. Everything else depends on it.



| Order | Module | Description | Dependencies | Est. Complexity |

|---|---|---|---|---|

| 1.1 | `lib/naming.py` | Template token parser, preset→template mapping, counter state | None | Low |

| 1.2 | `lib/metadata.py` | Per-format metadata embedding functions (PNG, JPEG, WebP, WAV, MP3, MP4, GIF) | Pillow, piexif, mutagen | Medium |

| 1.3 | `lib/sidecar.py` | JSON sidecar writer — receives metadata dict + filepath, writes .json | None | Low |

| 1.4 | `lib/manifest.py` | CSV append writer — thread-safe, creates header on first write | None | Low |

| 1.5 | `lib/response\_parser.py` | Dot-path JSON walker, auto-parse stringified JSON, markdown code block stripping | None | Low |

| 1.6 | `lib/bulk\_prompter.py` | Prompt variation engine — all 6 mutation strategies | word\_banks/ | Medium |

| 1.7 | `lib/tag\_generator.py` | 3-layer tag pipeline — prompt extraction, topic bank, LLM call | response\_parser | Medium |

| 1.8 | `lib/scanner.py` | Filesystem gap detection — plan vs reality comparison, Level 2/3 integrity checks, incremental cache | None | Medium-High |

| 1.9 | `lib/fingerprint.py` | Workflow fingerprint computation, save/load/compare, collision error messages | None | Low |



\*\*Deliverable:\*\* All lib/ modules with unit tests. No ComfyUI dependency yet — pure Python, testable in isolation.



\### Phase 2: Standalone Nodes



Build the two standalone nodes that have no state dependencies.



| Order | Node | Description | Dependencies |

|---|---|---|---|

| 2.1 | 💾 Save As (`save\_as.py`) | Full save node with naming templates, metadata embedding, sidecar, manifest | lib/naming, lib/metadata, lib/sidecar, lib/manifest |

| 2.2 | 🌐 API Call (`api\_call.py`) | REST API caller with OpenAI preset + generic mode, retry logic | lib/response\_parser |

| 2.3 | 📝 Bulk Prompter (`bulk\_prompter\_node.py`) | Standalone prompt variation node | lib/bulk\_prompter |

| 2.4 | `\_\_init\_\_.py` | Node registration for Phase 2 nodes | — |



\*\*Deliverable:\*\* Three working nodes that can be used independently in any ComfyUI workflow. Test each in ComfyUI manually.



\### Phase 3: Pipeline Nodes



Build the stateful orchestration layer.



| Order | Node | Description | Dependencies |

|---|---|---|---|

| 3.1 | 🎛️ Pipeline Controller (`pipeline\_controller.py`) | Full orchestrator — scanning, prompt gen, tag gen, collision detection, metadata assembly | lib/scanner, lib/fingerprint, lib/bulk\_prompter, lib/tag\_generator, lib/naming |

| 3.2 | ⏰ CRON Scheduler (`cron\_scheduler.py`) | Background thread scheduler with skip-if-busy, presets, DONE signal | croniter |



\*\*Deliverable:\*\* Complete pipeline. Wire up CRON → Controller → Save As with standard ComfyUI nodes in between. Test with a small batch (3 topics × 3 prompts × 2 resolutions = 18 images).



\### Phase 4: Progress \& Polish



| Order | Task | Description |

|---|---|---|

| 4.1 | API route | Register `GET /pipeline/status` on ComfyUI server |

| 4.2 | Progress log | Implement `.progress.log` writer with configurable interval |

| 4.3 | Word banks | Curate and populate all 4 word bank files (~510 entries total) |

| 4.4 | README | Full documentation with installation, usage, examples, troubleshooting |

| 4.5 | Scale test | Run 150 topics × 10 prompts × 3 resolutions = 4,500 images end-to-end |



\### Phase 5: Hardening



| Order | Task | Description |

|---|---|---|

| 5.1 | Crash recovery test | Kill ComfyUI mid-batch, restart, verify clean resume |

| 5.2 | Corrupt file test | Inject zero-byte and truncated files, verify scanner catches them |

| 5.3 | Collision test | Run two different workflows with same name, verify hard block |

| 5.4 | Disk full test | Fill disk mid-batch, verify clean halt |

| 5.5 | LLM failure test | Block API access, verify graceful fallback to local tags |

| 5.6 | Long-running test | 24+ hour unattended run, verify stability |



---



\## 12. Dependencies



| Package | Purpose | Required? |

|---|---|---|

| `croniter` | Cron expression parsing | Always |

| `Pillow` | Image I/O + integrity checks | Always |

| `numpy` | Tensor conversion | Always |

| `mutagen` | Audio metadata (ID3/WAV tags) | For audio formats |

| `piexif` | JPEG EXIF writing | For JPEG |

| `ffmpeg` (system) | MP3 conversion + MP4 encoding | For audio/video |



---



\## 13. Key Design Decisions Log



| # | Decision | Choice | Rationale |

|---|---|---|---|

| 1 | State management | Filesystem as state | Crash-proof, self-healing, no pointer drift |

| 2 | Multi-topic iteration | Pipeline Controller owns full matrix | Single brain, one scan, no node coordination |

| 3 | Collision detection | Workflow fingerprint + hard block | Prevents cross-workflow contamination |

| 4 | Workflow name | Required manual input | Forces intentional naming |

| 5 | Bulk Prompter integration | Logic shared via lib/, called internally by Controller | Avoids 74,850 no-op node executions |

| 6 | Negative prompt variation | Optional toggle, default constant | Most workflows want stable negatives |

| 7 | Tag generation | On-the-fly, first encounter per topic | No setup ceremony, 150 LLM calls not 75K |

| 8 | Tag categories | content / style / mood / technical | Enables filtered search across 75K outputs |

| 9 | Tag storage | Categorized in sidecar, flat in embedded + manifest | Full provenance in sidecar, searchability everywhere |

| 10 | Naming template | Dropdown presets + free-text override | Flexible for power users, easy for beginners |

| 11 | Sidecar JSON | Optional, default off | Reliable fallback for limited formats |

| 12 | Manifest CSV | Optional | Global index for large batches |

| 13 | Queue ordering | User choice: sequential / interleaved / shuffled | Different use cases need different ordering |

| 14 | CRON presets | Presets + raw cron | Accessible to non-cron users |

| 15 | API Call design | OpenAI-compatible default + generic override | Covers most LLMs + any REST API |

| 16 | Retry logic | Configurable count with exponential backoff | User controls resilience vs speed |

| 17 | Error handling | Retry → fallback → skip → log. Hard stop only on disk full | Batch never stops unless physically impossible |

| 18 | File integrity | Level 2 default (header check), Level 3 for recent on restart | Catches crashes without scanning overhead |

| 19 | Workflow JSON storage | Once at workflow root, not per-file | Prevents 75K × 50KB = 3.7GB duplication |

| 20 | Generation params | Not in sidecar, user controls KSampler directly | Clean separation — Controller handles what, KSampler handles how |

| 21 | Progress visibility | Status output + log file + API route | Covers UI, terminal, and remote monitoring |

| 22 | Prompt/neg\_prompt in sidecar | Yes, always included | Core to traceability |

