"""API key lookup — reads named keys from input/automation_api_keys.json."""

import json
import os
import logging

logger = logging.getLogger(__name__)

try:
    import folder_paths
    _KEY_FILE = os.path.join(folder_paths.get_input_directory(), "automation_api_keys.json")
except ImportError:
    _KEY_FILE = os.path.join("input", "automation_api_keys.json")

_DEFAULT_KEYS = {
    "openrouter": "",
    "openai": "",
    "ollama_local": "",
    "ollama_cloud": "",
    "lm_studio": "",
}

# In-memory cache: (mtime, parsed_dict)
_cache: tuple[float, dict[str, str]] = (0.0, {})
_initialized = False


def _ensure_key_file():
    """Create the key file with empty placeholders if it doesn't exist."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    if os.path.exists(_KEY_FILE):
        return

    try:
        os.makedirs(os.path.dirname(_KEY_FILE), exist_ok=True)
        with open(_KEY_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_KEYS, f, indent=2, ensure_ascii=False)
        logger.info("Created %s — add your API keys there", _KEY_FILE)
    except OSError as e:
        logger.warning("Could not create %s: %s", _KEY_FILE, e)


def _load_keys() -> dict[str, str]:
    """Load and cache api_keys.json, refreshing when file mtime changes."""
    global _cache

    _ensure_key_file()

    try:
        mtime = os.path.getmtime(_KEY_FILE)
    except OSError:
        return {}

    cached_mtime, cached_data = _cache
    if mtime == cached_mtime:
        return cached_data

    try:
        with open(_KEY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read %s: %s", _KEY_FILE, e)
        return {}

    if not isinstance(data, dict):
        logger.warning("%s is not a JSON object", _KEY_FILE)
        return {}

    _cache = (mtime, data)
    return data


def get_api_key(name: str) -> str:
    """Look up an API key by name. Returns empty string if not found."""
    if not name or not name.strip():
        return ""
    keys = _load_keys()
    return str(keys.get(name.strip(), ""))


def clear_cache() -> None:
    """Reset the in-memory cache. Useful for testing."""
    global _cache, _initialized
    _cache = (0.0, {})
    _initialized = False
