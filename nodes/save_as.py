"""Save As node — organized saving with naming templates, metadata, sidecar, manifest."""

import json
import os
import numpy as np
from datetime import datetime
from PIL import Image

from ..lib.naming import resolve_with_preset
from ..lib.metadata import embed_metadata as do_embed_metadata
from ..lib.sidecar import write_sidecar as do_write_sidecar
from ..lib.manifest import append_manifest
from ..lib.tag_generator import flatten_tags


class SaveAs:
    """Universal save node for image with template-based naming, embedded metadata,
    optional sidecar JSON, and optional manifest CSV."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_paths",)
    FUNCTION = "save"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "format": (["png", "jpeg", "webp"],),
                "quality": ("INT", {"default": 95, "min": 1, "max": 100}),
                "naming_preset": (["Simple", "Detailed", "Minimal", "Custom"],),
                "filename_prefix": ("STRING", {"default": "comfyui"}),
                "subfolder_template": ("STRING", {"default": "{topic}/{resolution}"}),
                "embed_metadata": ("BOOLEAN", {"default": True}),
                "write_sidecar": ("BOOLEAN", {"default": False}),
                "write_manifest": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "naming_template": ("STRING", {"default": ""}),
                "metadata": ("STRING", {"default": ""}),
                "output_dir": ("STRING", {"default": "output"}),
            },
        }

    def save(self, image, format, quality, naming_preset, filename_prefix,
             subfolder_template, embed_metadata, write_sidecar, write_manifest,
             naming_template="", metadata="", output_dir="output"):

        # Parse metadata JSON
        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError:
                pass

        saved_paths = []
        batch_size = image.shape[0]

        for batch_idx in range(batch_size):
            # Convert tensor to PIL Image
            img_array = image[batch_idx].cpu().numpy()
            img_array = (img_array * 255).clip(0, 255).astype(np.uint8)
            pil_image = Image.fromarray(img_array)

            width, height = pil_image.size

            # Build naming context
            topic = meta_dict.get("pipeline", {}).get("topic", "unknown")
            context = {
                "prefix": filename_prefix,
                "topic": topic,
                "width": width,
                "height": height,
                "format": format,
                "batch": batch_idx,
            }

            # Resolve filename
            filename = resolve_with_preset(naming_preset, naming_template or None, context)
            filename = f"{filename}.{format}"

            # Resolve subfolder
            subfolder = subfolder_template
            for key, val in context.items():
                subfolder = subfolder.replace(f"{{{key}}}", str(val))
            subfolder = subfolder.replace("{resolution}", f"{width}x{height}")

            # Build full path
            workflow_name = meta_dict.get("pipeline", {}).get("workflow_name", "")
            if workflow_name:
                full_dir = os.path.join(output_dir, workflow_name, subfolder)
            else:
                full_dir = os.path.join(output_dir, subfolder)

            os.makedirs(full_dir, exist_ok=True)
            save_path = os.path.join(full_dir, filename)

            # Save with metadata embedding
            if embed_metadata and meta_dict:
                flat_tags = flatten_tags(meta_dict.get("tags", {}))
                embed_data = {
                    "prompt": meta_dict.get("prompt", ""),
                    "tags": flat_tags,
                }
                do_embed_metadata(pil_image, embed_data, save_path, fmt=format, quality=quality)
            else:
                if format == "png":
                    pil_image.save(save_path, format="PNG")
                elif format in ("jpeg", "jpg"):
                    pil_image.save(save_path, format="JPEG", quality=quality)
                elif format == "webp":
                    pil_image.save(save_path, format="WEBP", quality=quality)

            # Write sidecar
            if write_sidecar and meta_dict:
                file_info = {
                    "file": {
                        "filename": filename,
                        "format": format,
                        "path": os.path.relpath(save_path, output_dir),
                        "saved_at": datetime.now().isoformat(),
                    }
                }
                do_write_sidecar(save_path, meta_dict, extra=file_info)

            # Append manifest
            if write_manifest:
                manifest_dir = os.path.join(output_dir, workflow_name) if workflow_name else output_dir
                manifest_path = os.path.join(manifest_dir, "manifest.csv")
                flat_tags = flatten_tags(meta_dict.get("tags", {}))
                row = {
                    "topic": topic,
                    "resolution": f"{width}x{height}",
                    "variant_index": meta_dict.get("pipeline", {}).get("variant_index", 0),
                    "filename": filename,
                    "path": os.path.relpath(save_path, output_dir),
                    "tags": "|".join(flat_tags),
                    "saved_at": datetime.now().isoformat(),
                }
                append_manifest(manifest_path, row)

            saved_paths.append(save_path)

        return (",".join(saved_paths),)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
