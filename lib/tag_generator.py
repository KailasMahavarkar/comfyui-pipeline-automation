"""Three-layer tag generation pipeline.

Layer 1: Prompt extraction (always on, free, instant)
Layer 2: Topic tag bank lookup (always on, free, instant)
Layer 3: LLM generation (optional, once per topic)
"""

import json
import re
import logging

logger = logging.getLogger(__name__)

FILLER_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with",
    "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "that", "this", "these", "those", "it", "its", "very", "really",
    "quite", "just", "also", "so", "too", "much", "many", "some",
    "any", "no", "not", "only", "own", "same", "than", "then",
    "now", "here", "there", "when", "where", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "over", "such",
    "by", "as", "from", "up", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "out",
}


def extract_from_prompt(prompt: str) -> list[str]:
    """Layer 1: Extract tags from prompt text by splitting on commas and filtering."""
    clauses = [c.strip() for c in prompt.split(",")]
    tags = []

    for clause in clauses:
        # Remove weight notation
        clause = re.sub(r'\(([^)]+)\)\s*:\s*[\d.]+', r'\1', clause)
        clause = re.sub(r'[()]', '', clause)

        words = clause.strip().split()
        for word in words:
            clean = re.sub(r'[^a-zA-Z0-9_]', '', word).lower()
            if clean and clean not in FILLER_WORDS and len(clean) > 2:
                tags.append(clean)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique.append(tag)

    return unique


def lookup_topic_bank(topic: str, topic_tag_bank: dict | str | None) -> dict:
    """Layer 2: Look up curated tags from the topic tag bank.

    Args:
        topic: The topic string.
        topic_tag_bank: Dict or JSON string mapping topics to tag dicts.

    Returns:
        Dict with categorized tags, or empty dict if not found.
    """
    if not topic_tag_bank:
        return {}

    if isinstance(topic_tag_bank, str):
        try:
            topic_tag_bank = json.loads(topic_tag_bank)
        except (json.JSONDecodeError, ValueError):
            return {}

    return topic_tag_bank.get(topic, {})


def generate_via_llm(topic: str, base_prompt: str,
                     api_url: str, api_key: str, model: str,
                     temperature: float = 0.7, max_tokens: int = 200,
                     max_retries: int = 3) -> dict | None:
    """Layer 3: Call LLM API to generate categorized tags.

    Returns dict with content/style/mood keys, or None on failure.
    """
    import urllib.request
    import urllib.error

    system_msg = (
        "You are a tag generator for image organization. "
        "Given a topic and prompt, generate categorized tags. "
        "Return ONLY valid JSON with keys: content (list), style (list), mood (list). "
        "Each list should have 3-5 relevant tags. Tags should be lowercase, underscore-separated."
    )

    user_msg = f"Topic: {topic}\nPrompt: {base_prompt}\n\nGenerate categorized tags as JSON."

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # Extract content from OpenAI-compatible response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse the JSON from the response
            from .response_parser import auto_parse_json
            parsed = auto_parse_json(content)

            if isinstance(parsed, dict):
                return {
                    "content": parsed.get("content", []),
                    "style": parsed.get("style", []),
                    "mood": parsed.get("mood", []),
                }

        except Exception as e:
            logger.warning(f"LLM tag generation attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)

    return None


def generate_tags(topic: str, base_prompt: str, resolution: str = "",
                  topic_tag_bank: dict | str | None = None,
                  llm_config: dict | None = None) -> tuple[dict, dict]:
    """Run the full 3-layer tag generation pipeline.

    Args:
        topic: The topic string.
        base_prompt: The base prompt with topic resolved.
        resolution: Resolution string (e.g., "512x512") for technical tag.
        topic_tag_bank: Optional topic->tags mapping.
        llm_config: Optional dict with api_url, api_key, model keys.

    Returns:
        Tuple of (tags_dict, tag_sources_dict).
        tags_dict has keys: content, style, mood, technical.
        tag_sources has keys: prompt_extraction, topic_bank, llm_generated.
    """
    # Layer 1: Prompt extraction
    prompt_tags = extract_from_prompt(base_prompt)

    # Layer 2: Topic bank
    bank_data = lookup_topic_bank(topic, topic_tag_bank)
    bank_content = bank_data.get("content", [])
    bank_style = bank_data.get("style", [])
    bank_mood = bank_data.get("mood", bank_data.get("category", []))

    # Layer 3: LLM (optional)
    llm_tags = None
    llm_content = []
    llm_style = []
    llm_mood = []

    if llm_config and llm_config.get("api_url"):
        llm_tags = generate_via_llm(
            topic, base_prompt,
            api_url=llm_config["api_url"],
            api_key=llm_config.get("api_key", ""),
            model=llm_config.get("model", "gpt-3.5-turbo"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 200),
        )
        if llm_tags:
            llm_content = llm_tags.get("content", [])
            llm_style = llm_tags.get("style", [])
            llm_mood = llm_tags.get("mood", [])

    # Merge all layers (deduplicated)
    def _merge(*lists):
        seen = set()
        result = []
        for lst in lists:
            for item in lst:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
        return result

    tags = {
        "content": _merge(prompt_tags[:5], bank_content, llm_content),
        "style": _merge(bank_style, llm_style),
        "mood": _merge(bank_mood, llm_mood),
        "technical": [resolution] if resolution else [],
    }

    tag_sources = {
        "prompt_extraction": prompt_tags,
        "topic_bank": bank_content + bank_style + bank_mood,
        "llm_generated": llm_content + llm_style + llm_mood,
    }

    return tags, tag_sources


def flatten_tags(tags: dict) -> list[str]:
    """Flatten categorized tags dict into a single list."""
    flat = []
    for category in ("content", "style", "mood", "technical"):
        flat.extend(tags.get(category, []))
    return flat
