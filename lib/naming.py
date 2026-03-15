"""Filename template token resolver with preset support and counter state."""

import re
import threading
from datetime import datetime


PRESET_TEMPLATES = {
    "Simple": "{prefix}_{date}_{time}",
    "Detailed": "{prefix}_{topic}_{resolution}_{counter}",
    "Minimal": "{prefix}_{counter}",
    "Custom": None,
}

TOKENS = {
    "prefix", "topic", "date", "time", "datetime",
    "resolution", "width", "height", "counter", "batch", "format",
}

_counter_lock = threading.Lock()
_counter = 0


def reset_counter():
    global _counter
    with _counter_lock:
        _counter = 0


def _next_counter():
    global _counter
    with _counter_lock:
        val = _counter
        _counter += 1
        return val


def sanitize_name(name: str) -> str:
    """Convert string to filesystem-safe, lowercase form."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('._').lower()


def _sanitize(value: str) -> str:
    """Replace filesystem-unsafe characters (preserves case)."""
    value = re.sub(r'[<>:"/\\|?*]', '_', value)
    value = re.sub(r'\s+', '_', value)
    return value.strip('._')


def resolve_template(template: str, context: dict) -> str:
    """Resolve all tokens in a naming template.

    Args:
        template: A string with {token} placeholders.
        context: Dict with keys matching token names. Expected keys:
            prefix, topic, width, height, format, batch (int).
            date/time/datetime/resolution/counter are auto-derived.
    """
    now = datetime.now()

    width = context.get("width", 0)
    height = context.get("height", 0)

    values = {
        "prefix": context.get("prefix", "comfyui"),
        "topic": context.get("topic", "unknown"),
        "date": now.strftime("%Y%m%d"),
        "time": now.strftime("%H%M%S"),
        "datetime": now.strftime("%Y%m%d_%H%M%S"),
        "resolution": f"{width}x{height}" if width and height else "unknown",
        "width": str(width) if width else "unknown",
        "height": str(height) if height else "unknown",
        "counter": f"{_next_counter():04d}",
        "batch": f"{context.get('batch', 0):04d}",
        "format": context.get("format", "png"),
    }

    def _replace(match):
        token = match.group(1)
        if token in values:
            return _sanitize(str(values[token]))
        return "unknown"

    return re.sub(r'\{(\w+)\}', _replace, template)


def get_preset_template(preset_name: str) -> str | None:
    """Return the template string for a preset name, or None for Custom."""
    return PRESET_TEMPLATES.get(preset_name)


def resolve_with_preset(preset_name: str, custom_template: str | None, context: dict) -> str:
    """Resolve a filename using a preset or custom template."""
    template = PRESET_TEMPLATES.get(preset_name)
    if template is None:
        template = custom_template or "{prefix}_{counter}"
    return resolve_template(template, context)
