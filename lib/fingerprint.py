"""Workflow fingerprint computation, save/load/compare, and collision detection."""

import hashlib
import json
import os
from datetime import datetime


def compute_fingerprint(workflow: dict) -> str:
    """Compute a deterministic SHA-256 fingerprint from a workflow.

    Includes: node types, connections (edges), checkpoint/model filenames,
              LoRA names, workflow_name, output type.
    Excludes: seeds, prompt text, CFG scale, steps, sampler, weights,
              quality/format settings, filename prefix, subfolder.
    """
    canonical = _extract_canonical(workflow)
    canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _extract_canonical(workflow: dict) -> dict:
    """Extract the fingerprint-relevant parts of a workflow."""
    nodes = []
    edges = []

    # Handle both API format and workflow format
    node_data = workflow.get("nodes") or workflow

    if isinstance(node_data, dict):
        # API format: {node_id: {class_type, inputs, ...}}
        for node_id, node in sorted(node_data.items()):
            if not isinstance(node, dict):
                continue

            class_type = node.get("class_type", "")
            nodes.append(class_type)

            # Extract model/checkpoint references from inputs
            inputs = node.get("inputs", {})
            for key, value in sorted(inputs.items()):
                if isinstance(value, str) and _is_model_reference(key):
                    nodes.append(f"{class_type}.{key}={value}")

                # Track connections (links to other nodes)
                if isinstance(value, list) and len(value) == 2:
                    try:
                        src_id = str(value[0])
                        src_slot = str(value[1])
                        edges.append(f"{src_id}:{src_slot}->{node_id}")
                    except (TypeError, IndexError):
                        pass

    elif isinstance(node_data, list):
        # UI format: [{id, type, inputs, outputs, ...}]
        for node in node_data:
            if not isinstance(node, dict):
                continue
            class_type = node.get("type", "")
            nodes.append(class_type)

        # Extract links
        links = workflow.get("links", [])
        for link in links:
            if isinstance(link, list) and len(link) >= 4:
                edges.append(f"{link[1]}:{link[2]}->{link[3]}")

    return {
        "nodes": sorted(set(nodes)),
        "edges": sorted(set(edges)),
    }


def _is_model_reference(key: str) -> bool:
    """Check if an input key is likely a model/checkpoint reference."""
    model_keys = {
        "ckpt_name", "checkpoint", "model_name", "lora_name",
        "vae_name", "unet_name", "clip_name",
    }
    return key.lower() in model_keys


def save_fingerprint(fingerprint: str, output_dir: str, workflow_name: str,
                     node_summary: list[str] | None = None):
    """Save fingerprint to .workflow_fingerprint file."""
    fp_path = os.path.join(output_dir, workflow_name, ".workflow_fingerprint")
    os.makedirs(os.path.dirname(fp_path), exist_ok=True)

    data = {
        "fingerprint": fingerprint,
        "created": datetime.now().isoformat(),
        "workflow_name": workflow_name,
    }
    if node_summary:
        data["nodes"] = node_summary

    with open(fp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_fingerprint(output_dir: str, workflow_name: str) -> dict | None:
    """Load existing fingerprint data. Returns None if not found."""
    fp_path = os.path.join(output_dir, workflow_name, ".workflow_fingerprint")
    if not os.path.exists(fp_path):
        return None

    with open(fp_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_collision(current_fp: str, output_dir: str, workflow_name: str,
                    current_nodes: list[str] | None = None) -> str | None:
    """Check if current fingerprint matches saved one.

    Returns None if OK (match or first run).
    Returns error message string if collision detected.
    """
    saved = load_fingerprint(output_dir, workflow_name)

    if saved is None:
        # First run — save and allow
        save_fingerprint(current_fp, output_dir, workflow_name, current_nodes)
        return None

    if saved["fingerprint"] == current_fp:
        return None

    # Collision detected
    saved_nodes = saved.get("nodes", ["(unknown)"])
    saved_date = saved.get("created", "(unknown)")
    current_display = current_nodes or ["(unknown)"]

    return (
        f'BLOCKED: workflow_name "{workflow_name}" is already in use by a different workflow.\n'
        f'\n'
        f'Existing fingerprint (created {saved_date}):\n'
        f'  - Nodes: {", ".join(saved_nodes)}\n'
        f'\n'
        f'Current fingerprint:\n'
        f'  - Nodes: {", ".join(current_display)}\n'
        f'\n'
        f'Options:\n'
        f'  1. Choose a different workflow_name\n'
        f'  2. Delete output/{workflow_name}/ to release the name\n'
        f'  3. Set reset_workflow=True to overwrite'
    )
