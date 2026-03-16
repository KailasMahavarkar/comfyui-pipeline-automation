"""Prompt variation engine.

Three variant sources, same output format:
    mutations        - 6 local strategies, zero API calls (default fallback)
    llm              - one LLM call per topic, N variants returned and cached
    custom_list      - user-provided prompts, picked by variant_index

Mutation strategies:
    synonym_swap     - Replace descriptive words with synonyms from adjectives.txt
    detail_injection - Append random scene details from scene_details.txt
    style_shuffle    - Append/swap style modifiers from styles.txt
    weight_jitter    - Randomly adjust emphasis weights (1.0-1.4)
    reorder          - Shuffle clause order in prompt
    template_fill    - Fill {mood}, {detail}, {style} wildcards from banks
"""

import json
import logging
import random
import re
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

WORD_BANKS_DIR = Path(__file__).parent.parent / "word_banks"

ALL_STRATEGIES = [
    "synonym_swap", "detail_injection", "style_shuffle",
    "weight_jitter", "reorder", "template_fill",
]


def _load_lines(filename: str, custom_dir: str | None = None) -> list[str]:
    """Load non-empty, non-comment lines from a word bank file."""
    lines = []
    for base_dir in [WORD_BANKS_DIR, custom_dir]:
        if base_dir is None:
            continue
        path = Path(base_dir) / filename
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    lines.append(line)
    return lines


def _load_synonyms(custom_dir: str | None = None) -> dict[str, list[str]]:
    """Load adjective synonym mappings. Format: word=syn1,syn2,syn3"""
    synonyms = {}
    for line in _load_lines("adjectives.txt", custom_dir):
        if "=" in line:
            word, syns = line.split("=", 1)
            synonyms[word.strip().lower()] = [s.strip() for s in syns.split(",")]
    return synonyms


def _load_styles(custom_dir: str | None = None) -> list[str]:
    return _load_lines("styles.txt", custom_dir)


def _load_moods(custom_dir: str | None = None) -> list[str]:
    return _load_lines("moods.txt", custom_dir)


def _load_details(custom_dir: str | None = None) -> list[str]:
    return _load_lines("scene_details.txt", custom_dir)


# --- Strategy implementations ---

def _synonym_swap(prompt: str, synonyms: dict, rng: random.Random) -> str:
    """Replace random descriptive words with synonyms."""
    words = prompt.split()
    for i, word in enumerate(words):
        clean = re.sub(r'[^a-zA-Z]', '', word).lower()
        if clean in synonyms and rng.random() < 0.4:
            replacement = rng.choice(synonyms[clean])
            # Preserve original punctuation/casing pattern
            words[i] = word.replace(clean, replacement)
    return " ".join(words)


def _detail_injection(prompt: str, details: list[str], rng: random.Random) -> str:
    """Append a random scene detail to the prompt."""
    if not details:
        return prompt
    detail = rng.choice(details)
    return f"{prompt.rstrip(',. ')}, {detail}"


def _style_shuffle(prompt: str, styles: list[str], rng: random.Random) -> str:
    """Append or swap a style modifier."""
    if not styles:
        return prompt
    style = rng.choice(styles)

    # Check if prompt already has a style from the bank
    prompt_lower = prompt.lower()
    existing = [s for s in styles if s.lower() in prompt_lower]
    if existing:
        # Swap one existing style
        old = rng.choice(existing)
        return prompt.replace(old, style, 1)
    else:
        return f"{prompt.rstrip(',. ')}, {style}"


def _weight_jitter(prompt: str, rng: random.Random) -> str:
    """Add or adjust emphasis weights on random clauses."""
    clauses = [c.strip() for c in prompt.split(",")]
    for i in range(len(clauses)):
        if rng.random() < 0.3:
            clause = clauses[i]
            # Remove existing weight notation
            clause = re.sub(r'\(([^)]+)\)\s*:\s*[\d.]+', r'\1', clause)
            clause = re.sub(r'\(([^)]+)\)', r'\1', clause)
            # Apply new weight
            weight = round(rng.uniform(1.0, 1.4), 2)
            clauses[i] = f"({clause}:{weight})"
    return ", ".join(clauses)


def _reorder(prompt: str, rng: random.Random) -> str:
    """Shuffle clause order while keeping the first clause anchored."""
    clauses = [c.strip() for c in prompt.split(",")]
    if len(clauses) <= 2:
        return prompt
    # Keep first clause (usually the subject), shuffle the rest
    first = clauses[0]
    rest = clauses[1:]
    rng.shuffle(rest)
    return ", ".join([first] + rest)


def _template_fill(prompt: str, moods: list[str], details: list[str],
                   styles: list[str], rng: random.Random) -> str:
    """Fill {mood}, {detail}, {style} wildcards."""
    result = prompt
    if "{mood}" in result and moods:
        result = result.replace("{mood}", rng.choice(moods), 1)
    if "{detail}" in result and details:
        result = result.replace("{detail}", rng.choice(details), 1)
    if "{style}" in result and styles:
        result = result.replace("{style}", rng.choice(styles), 1)
    return result


# --- Public API ---

def generate_variants(base_prompt: str, num_variants: int = 10,
                      strategies: list[str] | None = None,
                      custom_word_bank_path: str | None = None,
                      seed: int | None = None) -> list[dict]:
    """Generate N prompt variants from a base prompt.

    Args:
        base_prompt: The seed prompt to mutate.
        num_variants: How many variants to produce.
        strategies: List of strategy names to use. None = all.
        custom_word_bank_path: Optional path to custom word bank directory.
        seed: Optional RNG seed for reproducibility.

    Returns:
        List of dicts with keys: prompt, strategy, variant_index.
    """
    if strategies is None:
        strategies = list(ALL_STRATEGIES)

    rng = random.Random(seed)

    # Load word banks once
    synonyms = _load_synonyms(custom_word_bank_path)
    styles = _load_styles(custom_word_bank_path)
    moods = _load_moods(custom_word_bank_path)
    details = _load_details(custom_word_bank_path)

    variants = []
    used_prompts = {base_prompt}

    strategy_fns = {
        "synonym_swap": lambda p: _synonym_swap(p, synonyms, rng),
        "detail_injection": lambda p: _detail_injection(p, details, rng),
        "style_shuffle": lambda p: _style_shuffle(p, styles, rng),
        "weight_jitter": lambda p: _weight_jitter(p, rng),
        "reorder": lambda p: _reorder(p, rng),
        "template_fill": lambda p: _template_fill(p, moods, details, styles, rng),
    }

    max_attempts = num_variants * 3
    attempts = 0

    while len(variants) < num_variants and attempts < max_attempts:
        attempts += 1

        # Pick a random strategy
        strategy = rng.choice(strategies)
        fn = strategy_fns.get(strategy)
        if fn is None:
            continue

        variant_prompt = fn(base_prompt)

        # Ensure uniqueness
        if variant_prompt in used_prompts:
            continue

        used_prompts.add(variant_prompt)
        variants.append({
            "prompt": variant_prompt,
            "strategy": strategy,
            "variant_index": len(variants),
        })

    return variants


def generate_variants_via_llm(base_prompt: str, num_variants: int,
                               topic: str, llm_config: dict) -> list[dict]:
    """Generate N prompt variants via a single LLM call.

    Makes one API call, asks the LLM for num_variants distinct prompts, and
    returns them in the same format as generate_variants. Returns [] on any
    failure so the caller can fall back to mutation-based generation.

    Args:
        base_prompt: Resolved base prompt (topic already substituted).
        num_variants: How many variants to request.
        topic: Topic string (used in the LLM prompt for context).
        llm_config: LLM_CONFIG dict with api_url, api_key, model, temperature.

    Returns:
        List of dicts with keys: prompt, strategy="llm", variant_index.
    """
    from .response_parser import auto_parse_json

    api_url = llm_config.get("api_url", "")
    api_key = llm_config.get("api_key", "")
    model = llm_config.get("model", "gpt-3.5-turbo")
    temperature = llm_config.get("temperature", 0.7)

    if not api_url:
        return []

    system_msg = (
        "You are an image prompt variation generator. "
        f"Generate {num_variants} distinct image generation prompts based on the given topic and base prompt. "
        "Return ONLY a JSON array of strings. Each string must be a complete, standalone prompt. "
        "Vary style, mood, composition, and details across variants."
    )
    user_msg = (
        f"Topic: {topic}\n"
        f"Base prompt: {base_prompt}\n\n"
        f"Return a JSON array of {num_variants} prompt strings."
    )

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": temperature,
        "max_tokens": 4096,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = auto_parse_json(content)

        if not isinstance(parsed, list):
            logger.warning("LLM variant generation: response was not a JSON array")
            return []

        variants = []
        for i, item in enumerate(parsed):
            if isinstance(item, str) and item.strip():
                variants.append({
                    "prompt": item.strip(),
                    "strategy": "llm",
                    "variant_index": i,
                })

        logger.info("LLM generated %d prompt variants for topic '%s'", len(variants), topic)
        return variants

    except Exception as e:
        logger.warning("LLM variant generation failed for topic '%s': %s", topic, e)
        return []


def parse_prompt_list(prompt_list: str) -> list[dict]:
    """Parse a user-provided prompt list into the standard variant format.

    Accepts either a JSON array of strings or newline-separated prompts.
    Empty lines are ignored.

    Args:
        prompt_list: Raw string input from the user.

    Returns:
        List of dicts with keys: prompt, strategy="custom_list", variant_index.
    """
    stripped = prompt_list.strip()
    lines: list[str] = []

    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                lines = [str(p).strip() for p in parsed if str(p).strip()]
        except json.JSONDecodeError:
            pass

    if not lines:
        lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]

    return [
        {"prompt": p, "strategy": "custom_list", "variant_index": i}
        for i, p in enumerate(lines)
    ]
