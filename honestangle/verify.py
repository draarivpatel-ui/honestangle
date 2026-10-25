"""Verify an image against a receipt and locate exactly what changed.

Receipts carry both a Merkle root (compact integrity proof) and the full leaf
digest list (change localization). The receipt's own SHA-256 covers the leaf
list, so a forged list cannot pass receipt_intact().
"""
from .hashing import image_blocks, merkle_root


def verify_image(image_path, receipt, receipt_was_intact=True):
    """Compare an image with a receipt's commitments, block by block."""
    if not receipt_was_intact:
        return {
            "verdict": "RECEIPT_INVALID",
            "reason": "receipt self-integrity check failed; refusing to verify",
            "blocks_total": 0, "blocks_matched": 0, "blocks_changed": 0,
            "tamper_ratio": None, "blocks": [], "localized": False,
        }
    from .pngio import read_png
    width, height, channels, pixels = read_png(image_path)
    r_w, r_h, r_ch = receipt["width"], receipt["height"], receipt["channels"]
    if (width, height, channels) != (r_w, r_h, r_ch):
        return {
            "verdict": "DIMENSIONS_MISMATCH",
            "reason": "image is %dx%d ch%d, receipt committed %dx%d ch%d"
                      % (width, height, channels, r_w, r_h, r_ch),
            "blocks_total": 0, "blocks_matched": 0, "blocks_changed": 0,
            "tamper_ratio": None, "blocks": [], "localized": False,
        }
    _, leaves = image_blocks(image_path, receipt["block_size"])
    committed = receipt["leaf_digests"]
    if len(leaves) != len(committed):
        return {
            "verdict": "RECEIPT_INVALID",
            "reason": "leaf count differs from receipt commitment",
            "blocks_total": len(committed), "blocks_matched": 0, "blocks_changed": 0,
            "tamper_ratio": None, "blocks": [], "localized": False,
        }
    # Independent check: the committed leaf list must hash to the committed root.
    root_now = merkle_root([{"digest": d} for d in committed])
    if root_now != receipt["merkle_root"]:
        return {
            "verdict": "RECEIPT_INVALID",
            "reason": "leaf digest list does not match the committed Merkle root",
            "blocks_total": 0, "blocks_matched": 0, "blocks_changed": 0,
            "tamper_ratio": None, "blocks": [], "localized": False,
        }
    blocks = []
    changed = 0
    for leaf, digest in zip(leaves, committed):
        ok = leaf["digest"] == digest
        blocks.append({
            "row": leaf["row"], "col": leaf["col"],
            "x": leaf["x"], "y": leaf["y"], "w": leaf["w"], "h": leaf["h"],
            "matched": ok,
        })
        if not ok:
            changed += 1
    total = len(blocks)
    if changed == 0:
        verdict = "VERIFIED"
    elif changed == total:
        verdict = "REGENERATED"
    else:
        verdict = "TAMPERED"
    return {
        "verdict": verdict,
        "blocks_total": total,
        "blocks_matched": total - changed,
        "blocks_changed": changed,
        "tamper_ratio": round(changed / total, 6) if total else 0.0,
        "blocks": blocks,
        "localized": True,
    }


def changed_rects(result):
    """Changed block rectangles as (x, y, w, h) for drawing."""
    if not result.get("localized"):
        return []
    return [(b["x"], b["y"], b["w"], b["h"]) for b in result["blocks"] if not b["matched"]]


def result_json(result, path):
    import json
    slim = {k: v for k, v in result.items() if k != "blocks"}
    slim["blocks"] = result.get("blocks", [])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=1)
