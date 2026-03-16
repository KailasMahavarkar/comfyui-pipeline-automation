"""Two-layer tag generation pipeline.

Layer 1: Prompt extraction (always on, free, instant)
Layer 2: Topic tag bank lookup (always on, free, instant)
"""

import json
import re

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


def generate_tags(topic: str, base_prompt: str, resolution: str = "",
                  topic_tag_bank: dict | str | None = None) -> tuple[dict, dict]:
    """Run the 2-layer tag generation pipeline.

    Layer 1: Extract meaningful words from the prompt.
    Layer 2: Look up curated tags from topic bank.

    Args:
        topic: The topic string.
        base_prompt: The base prompt with topic resolved.
        resolution: Resolution string (e.g., "512x512") for technical tag.
        topic_tag_bank: Optional topic->tags mapping.

    Returns:
        Tuple of (tags_dict, tag_sources_dict).
    """
    # Layer 1: Prompt extraction
    prompt_tags = extract_from_prompt(base_prompt)

    # Layer 2: Topic bank
    bank_data = lookup_topic_bank(topic, topic_tag_bank)
    bank_content = bank_data.get("content", [])
    bank_style = bank_data.get("style", [])
    bank_mood = bank_data.get("mood", bank_data.get("category", []))

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
        "content": _merge(prompt_tags[:5], bank_content),
        "style": list(bank_style),
        "mood": list(bank_mood),
        "technical": [resolution] if resolution else [],
    }

    tag_sources = {
        "prompt_extraction": prompt_tags,
        "topic_bank": bank_content + bank_style + bank_mood,
    }

    return tags, tag_sources


def flatten_tags(tags: dict) -> list[str]:
    """Flatten categorized tags dict into a single list."""
    flat = []
    for category in ("content", "style", "mood", "technical"):
        flat.extend(tags.get(category, []))
    return flat
