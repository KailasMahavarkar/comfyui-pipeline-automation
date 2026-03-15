"""Generate pipeline-flow.excalidraw from node definitions."""

import json
import os

SEED = 100

def next_seed():
    global SEED
    SEED += 1
    return SEED

COMMON = {
    "angle": 0,
    "fillStyle": "solid",
    "strokeWidth": 2,
    "strokeStyle": "solid",
    "roughness": 1,
    "opacity": 100,
    "groupIds": [],
    "frameId": None,
    "version": 1,
    "versionNonce": 1,
    "isDeleted": False,
    "updated": 1,
    "link": None,
    "locked": False,
}


def rect(id, x, y, w, h, bg, stroke, label, arrow_ids=None):
    """Create a labeled rectangle (shape + text)."""
    bound = [{"type": "text", "id": f"{id}-text"}]
    if arrow_ids:
        for aid in arrow_ids:
            bound.append({"type": "arrow", "id": aid})

    shape = {
        **COMMON,
        "id": id, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": bg,
        "roundness": {"type": 3},
        "boundElements": bound,
        "seed": next_seed(),
    }

    lines = label.split("\n")
    font_size = 16
    text_h = font_size * 1.25 * len(lines)

    text = {
        **COMMON,
        "id": f"{id}-text", "type": "text",
        "x": x + 5, "y": y + (h - text_h) / 2,
        "width": w - 10, "height": text_h,
        "strokeColor": stroke, "backgroundColor": "transparent",
        "strokeWidth": 1,
        "roundness": None,
        "boundElements": None,
        "text": label, "fontSize": font_size, "fontFamily": 1,
        "textAlign": "center", "verticalAlign": "middle",
        "containerId": id, "originalText": label, "lineHeight": 1.25,
        "seed": next_seed(),
    }

    return [shape, text]


def arrow(id, src, src_edge, dst, dst_edge, stroke="#495057", label=None):
    """Create an elbow arrow between two shapes."""
    edges = {
        "top": lambda s: (s["x"] + s["w"] / 2, s["y"]),
        "bottom": lambda s: (s["x"] + s["w"] / 2, s["y"] + s["h"]),
        "left": lambda s: (s["x"], s["y"] + s["h"] / 2),
        "right": lambda s: (s["x"] + s["w"], s["y"] + s["h"] / 2),
    }
    fixed = {
        "top": [0.5, 0], "bottom": [0.5, 1],
        "left": [0, 0.5], "right": [1, 0.5],
    }

    sx, sy = edges[src_edge](src)
    tx, ty = edges[dst_edge](dst)
    dx = tx - sx
    dy = ty - sy

    # Route based on edge combo
    if src_edge == "bottom" and dst_edge == "top":
        if abs(dx) < 5:
            points = [[0, 0], [0, dy]]
        else:
            mid_y = dy / 2
            points = [[0, 0], [0, mid_y], [dx, mid_y], [dx, dy]]
    elif src_edge == "right" and dst_edge == "left":
        if abs(dy) < 5:
            points = [[0, 0], [dx, 0]]
        else:
            mid_x = dx / 2
            points = [[0, 0], [mid_x, 0], [mid_x, dy], [dx, dy]]
    elif src_edge == "right" and dst_edge == "top":
        points = [[0, 0], [dx, 0], [dx, dy]]
    elif src_edge == "bottom" and dst_edge == "left":
        points = [[0, 0], [0, dy], [dx, dy]]
    else:
        points = [[0, 0], [dx, 0], [dx, dy]]

    w = max(abs(p[0]) for p in points) or 1
    h = max(abs(p[1]) for p in points) or 1

    elements = [{
        **COMMON,
        "id": id, "type": "arrow",
        "x": sx, "y": sy, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": "transparent",
        "roughness": 0,
        "roundness": None,
        "boundElements": None,
        "points": points,
        "elbowed": True,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "startBinding": {
            "elementId": src["id"], "focus": 0, "gap": 1,
            "fixedPoint": fixed[src_edge],
        },
        "endBinding": {
            "elementId": dst["id"], "focus": 0, "gap": 1,
            "fixedPoint": fixed[dst_edge],
        },
        "seed": next_seed(),
    }]

    if label:
        # Place label at midpoint of arrow
        mid_x = sx + dx / 2
        mid_y = sy + dy / 2
        elements.append({
            **COMMON,
            "id": f"{id}-label", "type": "text",
            "x": mid_x - 40, "y": mid_y - 16,
            "width": 80, "height": 20,
            "strokeColor": "#495057", "backgroundColor": "transparent",
            "strokeWidth": 1,
            "roundness": None,
            "boundElements": None,
            "text": label, "fontSize": 12, "fontFamily": 1,
            "textAlign": "center", "verticalAlign": "middle",
            "containerId": None, "originalText": label, "lineHeight": 1.25,
            "seed": next_seed(),
        })

    return elements


def annotation(id, x, y, text_str, color="#868e96"):
    """Standalone text annotation."""
    return {
        **COMMON,
        "id": id, "type": "text",
        "x": x, "y": y,
        "width": len(text_str) * 7, "height": 18,
        "strokeColor": color, "backgroundColor": "transparent",
        "strokeWidth": 1,
        "roundness": None,
        "boundElements": None,
        "text": text_str, "fontSize": 14, "fontFamily": 1,
        "textAlign": "left", "verticalAlign": "top",
        "containerId": None, "originalText": text_str, "lineHeight": 1.25,
        "seed": next_seed(),
    }


def group_box(id, x, y, w, h, stroke, label_text):
    """Dashed grouping rectangle with label."""
    box = {
        **COMMON,
        "id": id, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": "transparent",
        "strokeStyle": "dashed",
        "roughness": 0,
        "roundness": None,
        "boundElements": None,
        "seed": next_seed(),
    }
    label = {
        **COMMON,
        "id": f"{id}-label", "type": "text",
        "x": x + 10, "y": y + 8,
        "width": len(label_text) * 8, "height": 18,
        "strokeColor": stroke, "backgroundColor": "transparent",
        "strokeWidth": 1,
        "roundness": None,
        "boundElements": None,
        "text": label_text, "fontSize": 14, "fontFamily": 1,
        "textAlign": "left", "verticalAlign": "top",
        "containerId": None, "originalText": label_text, "lineHeight": 1.25,
        "seed": next_seed(),
    }
    return [box, label]


# ── Colors ──
BLUE_BG, BLUE_STROKE = "#a5d8ff", "#1971c2"      # Our nodes
GREY_BG, GREY_STROKE = "#e9ecef", "#868e96"        # Built-in ComfyUI
PURPLE_BG, PURPLE_STROKE = "#d0bfff", "#7048e8"    # Standalone utility

# ── Node positions ──
# dict with id, x, y, w, h for easy arrow calculation
nodes = {}

def define(id, x, y, w, h):
    nodes[id] = {"id": id, "x": x, "y": y, "w": w, "h": h}
    return nodes[id]

# Row 1: Config sources
gs = define("gap-scanner", 60, 80, 200, 80)
lc = define("llm-config", 500, 80, 180, 80)

# Row 2: Prompt + Latent
pg = define("prompt-gen", 100, 260, 220, 80)
el = define("empty-latent", 460, 280, 190, 70)

# Row 3: Encoding
cp = define("clip-pos", 60, 440, 180, 65)
cn = define("clip-neg", 270, 440, 180, 65)

# Row 4: Sampling
ks = define("ksampler", 180, 580, 180, 70)

# Row 5: Decode
vd = define("vae-decode", 180, 720, 180, 70)

# Row 6: Schedule
cs = define("cron-sched", 160, 860, 200, 80)

# Row 7: Save
sa = define("save-as", 160, 1020, 200, 80)

# Standalone
ac = define("api-call", 760, 80, 170, 70)
bp = define("bulk-prompter", 760, 210, 170, 70)


# ── Build elements ──
elements = []

# Group boxes
elements.extend(group_box("group-pipeline", 30, 30, 680, 1100, "#1971c2", "Pipeline Automation Nodes"))
elements.extend(group_box("group-standalone", 730, 30, 230, 280, "#7048e8", "Standalone Utility"))
elements.extend(group_box("group-comfyui", 30, 410, 380, 420, "#868e96", "Built-in ComfyUI"))

# Our nodes (blue)
elements.extend(rect("gap-scanner", gs["x"], gs["y"], gs["w"], gs["h"], BLUE_BG, BLUE_STROKE, "Gap Scanner"))
elements.extend(rect("llm-config", lc["x"], lc["y"], lc["w"], lc["h"], BLUE_BG, BLUE_STROKE, "LLM Config"))
elements.extend(rect("prompt-gen", pg["x"], pg["y"], pg["w"], pg["h"], BLUE_BG, BLUE_STROKE, "Prompt Generator"))
elements.extend(rect("cron-sched", cs["x"], cs["y"], cs["w"], cs["h"], BLUE_BG, BLUE_STROKE, "CRON Scheduler"))
elements.extend(rect("save-as", sa["x"], sa["y"], sa["w"], sa["h"], BLUE_BG, BLUE_STROKE, "Save As"))

# Built-in nodes (grey)
elements.extend(rect("empty-latent", el["x"], el["y"], el["w"], el["h"], GREY_BG, GREY_STROKE, "Empty Latent"))
elements.extend(rect("clip-pos", cp["x"], cp["y"], cp["w"], cp["h"], GREY_BG, GREY_STROKE, "CLIP Encode (+)"))
elements.extend(rect("clip-neg", cn["x"], cn["y"], cn["w"], cn["h"], GREY_BG, GREY_STROKE, "CLIP Encode (-)"))
elements.extend(rect("ksampler", ks["x"], ks["y"], ks["w"], ks["h"], GREY_BG, GREY_STROKE, "KSampler"))
elements.extend(rect("vae-decode", vd["x"], vd["y"], vd["w"], vd["h"], GREY_BG, GREY_STROKE, "VAE Decode"))

# Standalone (purple)
elements.extend(rect("api-call", ac["x"], ac["y"], ac["w"], ac["h"], PURPLE_BG, PURPLE_STROKE, "API Call"))
elements.extend(rect("bulk-prompter", bp["x"], bp["y"], bp["w"], bp["h"], PURPLE_BG, PURPLE_STROKE, "Bulk Prompter"))

# ── Arrows ──

# Main flow: GS → PG
elements.extend(arrow("a-gs-pg", gs, "bottom", pg, "top", BLUE_STROKE, "topic / res / idx\nPIPELINE_CONFIG"))

# LLM Config → PG
elements.extend(arrow("a-lc-pg", lc, "bottom", pg, "right", BLUE_STROKE, "LLM_CONFIG"))

# LLM Config → API Call (dashed — optional)
elements.extend(arrow("a-lc-ac", lc, "right", ac, "left", PURPLE_STROKE))

# GS → Empty Latent (width/height)
elements.extend(arrow("a-gs-el", gs, "right", el, "top", GREY_STROKE, "width / height"))

# PG → CLIP+ (prompt)
elements.extend(arrow("a-pg-cp", pg, "bottom", cp, "top", GREY_STROKE, "prompt"))

# PG → CLIP- (negative)
elements.extend(arrow("a-pg-cn", pg, "bottom", cn, "top", GREY_STROKE, "negative"))

# CLIP+ → KSampler
elements.extend(arrow("a-cp-ks", cp, "bottom", ks, "top", GREY_STROKE))

# CLIP- → KSampler
elements.extend(arrow("a-cn-ks", cn, "bottom", ks, "top", GREY_STROKE))

# Empty Latent → KSampler
elements.extend(arrow("a-el-ks", el, "bottom", ks, "right", GREY_STROKE, "latent"))

# KSampler → VAE Decode
elements.extend(arrow("a-ks-vd", ks, "bottom", vd, "top", GREY_STROKE))

# VAE Decode → CRON Scheduler
elements.extend(arrow("a-vd-cs", vd, "bottom", cs, "top", BLUE_STROKE, "image"))

# CRON Scheduler → Save As (passthrough)
elements.extend(arrow("a-cs-sa", cs, "bottom", sa, "top", BLUE_STROKE, "passthrough (*)"))

# GS → CRON Scheduler (is_complete) — route along left side
elements.append(annotation("note-iscomplete", 420, 885, "is_complete from Gap Scanner", "#c92a2a"))

# GS/PG → Save As (PIPELINE_CONFIG + metadata)
elements.append(annotation("note-pipeline-cfg", 420, 1045, "PIPELINE_CONFIG + metadata", "#1971c2"))


# ── Assemble file ──
excalidraw = {
    "type": "excalidraw",
    "version": 2,
    "source": "claude-code-excalidraw-skill",
    "elements": elements,
    "appState": {
        "gridSize": 20,
        "viewBackgroundColor": "#ffffff",
    },
    "files": {},
}

out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "pipeline-flow.excalidraw")

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(excalidraw, f, indent=2)

print(f"Written to {os.path.abspath(out_path)}")
