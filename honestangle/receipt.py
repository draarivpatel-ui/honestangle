"""Receipts: the attestation that an image existed, byte exact, at a time."""
import datetime
import json

from .hashing import image_blocks, merkle_root, sha256_hex

TOOL_VERSION = "2.0.0"


def canonical_json(obj):
    """Stable serialization: sorted keys, no spaces, UTF-8, newline safe."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def create_receipt(image_path, block_size=16, note=None, extra=None):
    """Build a receipt dict for an image. Deterministic except for timestamps."""
    meta, leaves = image_blocks(image_path, block_size)
    with open(image_path, "rb") as f:
        image_sha = sha256_hex(f.read())
    body = {
        "tool": "honestangle",
        "tool_version": TOOL_VERSION,
        "algorithm": "sha256-block-merkle",
        "image_sha256": image_sha,
        "width": meta["width"],
        "height": meta["height"],
        "channels": meta["channels"],
        "block_size": meta["block_size"],
        "block_count": len(leaves),
        "merkle_root": merkle_root(leaves),
        "leaf_digests": [leaf["digest"] for leaf in leaves],
        "note": note or "",
    }
    if extra:
        body["extra"] = extra
    body["created_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body["receipt_sha256"] = sha256_hex(canonical_json({k: v for k, v in body.items() if k != "receipt_sha256"}).encode("utf-8"))
    return body


def receipt_intact(receipt):
    """Self-integrity check: recompute receipt_sha256 over the other fields."""
    if not isinstance(receipt, dict) or "receipt_sha256" not in receipt:
        return False
    expect = receipt["receipt_sha256"]
    rest = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    return sha256_hex(canonical_json(rest).encode("utf-8")) == expect


def write_receipt(receipt, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")


def load_receipt(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
