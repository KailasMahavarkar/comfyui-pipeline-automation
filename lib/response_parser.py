"""Dot-path JSON walker with auto-parse and markdown stripping for API responses."""

import json
import re


def strip_code_blocks(text: str) -> str:
    """Strip markdown code blocks (```json ... ``` or ``` ... ```) from text."""
    # Match ```json\n...\n``` or ```\n...\n```
    pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def auto_parse_json(value: str) -> dict | list | str:
    """Try to parse a string as JSON, stripping code blocks first."""
    if not isinstance(value, str):
        return value

    cleaned = strip_code_blocks(value).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return value


def walk_dot_path(data: dict | list, path: str):
    """Walk a dot-separated path through nested dicts/lists.

    Examples:
        walk_dot_path({"a": {"b": [1,2,3]}}, "a.b.1") -> 2
        walk_dot_path(resp, "choices.0.message.content") -> "..."
    """
    parts = path.split(".")
    current = data

    for part in parts:
        if current is None:
            return None

        # Try as integer index for lists
        if isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx]
                continue
            except (ValueError, IndexError):
                return None

        # Try as dict key
        if isinstance(current, dict):
            current = current.get(part)
            # Auto-parse stringified JSON in intermediate values
            if isinstance(current, str) and part != parts[-1]:
                parsed = auto_parse_json(current)
                if parsed is not current:
                    current = parsed
        else:
            return None

    # Auto-parse the final value too
    if isinstance(current, str):
        parsed = auto_parse_json(current)
        if isinstance(parsed, (dict, list)):
            return parsed

    return current


def extract_mappings(response: dict, mapping_text: str) -> dict:
    """Extract multiple values from a response using dot-path mappings.

    Args:
        response: The parsed JSON response.
        mapping_text: Multi-line string with "key=dot.path" per line.
            e.g. "prompt=choices.0.message.content.prompt"

    Returns:
        Dict of extracted key:value pairs.
    """
    result = {}
    for line in mapping_text.strip().splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue

        key, path = line.split("=", 1)
        key = key.strip()
        path = path.strip()

        value = walk_dot_path(response, path)
        if value is not None:
            result[key] = value

    return result
