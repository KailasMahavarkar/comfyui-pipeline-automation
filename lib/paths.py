"""Cross-platform path resolution for ComfyUI custom nodes."""

import os


def _get_comfyui_base() -> str:
    """Get ComfyUI's base directory."""
    try:
        import folder_paths
        return folder_paths.base_path
    except ImportError:
        return os.getcwd()


def resolve_output_dir(output_dir: str) -> str:
    """Resolve output_dir to an absolute path.

    If the user provides an absolute path, use it as-is.
    If relative (e.g. "output"), resolve it from ComfyUI's base directory.
    """
    if os.path.isabs(output_dir):
        return output_dir
    return os.path.join(_get_comfyui_base(), output_dir)
