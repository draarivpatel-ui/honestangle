"""Block grid hashing and Merkle tree construction for pixel provenance."""
import hashlib

from .pngio import read_png


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def block_grid(width, height, block_size):
    """Yield (row, col, x, y, w, h) for every block in scan order."""
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    rows = (height + block_size - 1) // block_size
    cols = (width + block_size - 1) // block_size
    for r in range(rows):
        for c in range(cols):
            x = c * block_size
            y = r * block_size
            w = min(block_size, width - x)
            h = min(block_size, height - y)
            yield r, c, x, y, w, h


def block_bytes(pixels, width, channels, x, y, w, h):
    """Concatenate the raw bytes of one rectangular block, row by row."""
    stride = width * channels
    out = bytearray()
    mv = memoryview(pixels)
    for dy in range(h):
        start = (y + dy) * stride + x * channels
        out.extend(mv[start:start + w * channels])
    return bytes(out)


def image_blocks(path, block_size):
    """Read a PNG and return (meta, leaves) where leaves are per-block digests."""
    width, height, channels, pixels = read_png(path)
    meta = {
        "width": width,
        "height": height,
        "channels": channels,
        "block_size": block_size,
    }
    leaves = []
    for r, c, x, y, w, h in block_grid(width, height, block_size):
        digest = sha256_hex(block_bytes(pixels, width, channels, x, y, w, h))
        leaves.append({"row": r, "col": c, "x": x, "y": y, "w": w, "h": h, "digest": digest})
    return meta, leaves


def merkle_root(leaves):
    """SHA-256 Merkle root over leaf digests; odd node duplicated pairwise."""
    if not leaves:
        raise ValueError("no leaves")
    level = [bytes.fromhex(item["digest"] if isinstance(item, dict) else item) for item in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def merkle_proof(leaves, index):
    """Return the audit proof (list of hex neighbor digests) for leaf index."""
    if not 0 <= index < len(leaves):
        raise IndexError("leaf index out of range")
    level = [bytes.fromhex(item["digest"] if isinstance(item, dict) else item) for item in leaves]
    proof = []
    idx = index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sib = idx ^ 1
        proof.append(level[sib].hex())
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
        idx //= 2
    return proof


def verify_proof_at(leaf_hex, proof, root_hex, leaf_index):
    """Position-aware proof verification (leaf side derived from the index)."""
    cur = bytes.fromhex(leaf_hex)
    idx = leaf_index
    for sib_hex in proof:
        sib = bytes.fromhex(sib_hex)
        if idx % 2 == 0:
            cur = hashlib.sha256(cur + sib).digest()
        else:
            cur = hashlib.sha256(sib + cur).digest()
        idx //= 2
    return cur.hex() == root_hex
