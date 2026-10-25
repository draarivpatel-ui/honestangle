# HonestAngle

Cryptographic pixel provenance for ComfyUI outputs. HonestAngle commits an image
block by block under SHA-256 into a Merkle root receipt. Any later image verifies
against that receipt, and changed blocks are localized exactly, so authentic
regions can be told apart from diffusion-infilled ones.

## Why it exists

Higgsfield AI promised to open source its generative editing tools and did not
deliver. This project is an open-source rebuild in the spirit of the ComfyUI
Open Source Higgsfield challenge. It takes on the half of the problem that
generative tools leave open. Once an image has been receipted, HonestAngle can
state, cryptographically and at block resolution, which parts of a later image
still match the committed original and which parts were regenerated.

## How it works

The core is pure Python standard library, with zero pip dependencies, so
provenance hashing is reproducible on a bare Python install.

1. **PNG IO.** `honestangle/pngio.py` reads and writes PNG in RGB8 and RGBA8,
   non-interlaced, using only `struct` and `zlib`. The reader decodes all five
   scanline filter types and rejects loudly anything it cannot read exactly,
   such as interlaced files or 16-bit depth.
2. **Block hashing.** `honestangle/hashing.py` splits the image into a grid of
   blocks, 16 pixels by default and configurable, and digests each block's raw
   bytes with SHA-256. The leaf digests build a Merkle root with odd nodes
   duplicated pairwise, and position-aware audit proofs are available for any
   leaf.
3. **Receipts.** `honestangle/receipt.py` writes a JSON receipt holding the
   image SHA-256, dimensions, channels, block size, block count, Merkle root,
   the full leaf digest list, a note, a UTC timestamp, and `receipt_sha256`, a
   self-integrity digest computed over every other field.
4. **Verification.** `honestangle/verify.py` re-derives block digests from the
   image being checked and compares them with the committed leaves. The leaf
   list is also checked independently against the committed Merkle root, so a
   forged leaf list is refused. Verdicts are `VERIFIED`, `TAMPERED`,
   `REGENERATED`, `DIMENSIONS_MISMATCH` and `RECEIPT_INVALID`. A `TAMPERED`
   result localizes every changed block with its row, column and pixel
   rectangle.

## Install and run

Python 3.9 or newer. Clone this repository and run from its root. Nothing to
install.

Create a receipt for an image.

```
python -m honestangle.cli init image.png -o receipt.json --block 32
```

Verify any later image against it.

```
python -m honestangle.cli verify check.png --receipt receipt.json --json-out results.json
```

`verify` prints the verdict, the matched and changed block counts, the tamper
ratio, and the pixel rectangle of every changed block up to `--max-rects` (20
by default). The exit code is 0 for `VERIFIED`, 1 for any other verdict, and 2
when the receipt itself fails its self-integrity check. `--json-out` writes the
full per-block result as JSON.

Run the test suite.

```
python -m unittest discover -s tests
```

33 unit tests cover PNG round trips, block grid math with partial edge blocks,
Merkle proofs and their rejection cases, receipt determinism and tamper
detection, and every verdict, including forged leaf lists.

## Receipts

A receipt is one JSON file, deterministic for the same image and block size
except for the timestamp and note. A receipt for a 512 by 512 image at block
size 32 has 256 leaf digests, one per block.

```json
{
  "tool": "honestangle",
  "tool_version": "2.0.0",
  "algorithm": "sha256-block-merkle",
  "image_sha256": "...",
  "width": 512,
  "height": 512,
  "channels": 3,
  "block_size": 32,
  "block_count": 256,
  "merkle_root": "...",
  "leaf_digests": ["... one digest per block ..."],
  "note": "...",
  "created_utc": "...",
  "receipt_sha256": "..."
}
```

The Merkle root is the compact commitment. The full `leaf_digests` list is what
enables exact localization, because each block is compared individually.
`receipt_sha256` covers every other field, so any edit to a receipt, the leaf
list included, breaks the self-integrity check, and `verify` refuses such a
receipt with `RECEIPT_INVALID`.

## The GPU run

`comfyui/run_gpu.py` performs a full provenance run against a real ComfyUI
install, end to end.

1. Clones ComfyUI (the resolved commit is recorded in the receipt) and installs
   its requirements.
2. Downloads the SD 1.5 inpainting checkpoint `sd-v1-5-inpainting.ckpt`, the
   open-weights release from runwayml, about 4.4 GB.
3. Generates a deterministic 512 by 512 original with the built-in scene
   generator, plus a rectangular inpaint mask, both written locally with no
   external assets.
4. Starts ComfyUI and submits an API-format inpaint workflow over HTTP with a
   fixed seed, then saves the generated output.
5. Runs `honestangle init` on the original and `honestangle verify` on the
   ComfyUI output.
6. Writes `receipts/gpu_run_receipt.json`, `receipts/gpu_run_results.json` and
   `receipts/job_receipt.json`, the last holding SHA-256 hashes of every
   artifact together with job metadata such as the ComfyUI commit, the model
   name and its license, and the workflow prompt id.

The committed receipts are from a real run on the local Apple Silicon GPU (MPS
backend), ComfyUI commit `19ae172bff6c9e4c738e7f2e00fe087f5b5b46ab`, prompt id
`b6819013-e30e-44a1-be08-cc2babf5eeb0`. The verdict was `REGENERATED`: all 256
blocks changed. That result is exactly what byte-level provenance should report
for a diffusion round trip, because the inpaint pipeline re-encodes the whole
image through the VAE, so even pixels outside the mask come back with slightly
different bytes. Localization of a surgical edit, where only the touched blocks
change, is demonstrated by the CLI example above and by the 33-test suite; the
GPU run demonstrates the other honest pole, detecting that nothing in a
diffusion-processed image is byte-identical to the original.

## The demo

`demo/index.html` is a local proof viewer. Open it in any browser; there is no
server and nothing is uploaded. Drop in the original image, the image to check,
and the results JSON written by `--json-out`, or press **Show synthetic
sample** for a built-in proof of an edited region. Changed blocks light up over
the original, and a selector coarsens the map to 2x or 4x superblocks. The page
only visualizes results; the Python CLI is the verifier of record.

## What is proven, and what is not

### What is proven

Byte-exact block provenance between two images, relative to a receipt created
by this tool. A later image that matches the receipt everywhere returns
`VERIFIED`. Where bytes differ, the changed blocks are named at pixel
resolution. Receipt integrity is proven as well; any modification of a receipt,
the leaf digest list included, breaks its self-integrity digest or the
leaf-to-root check and is refused.

### What is not claimed

- HonestAngle does not detect provenance for images that never had a receipt.
  A receipt must exist from the moment of generation onward.
- It is not a watermark detector. It compares an image against a receipt; it
  does not fingerprint arbitrary images or infer how an image was made.

## License

The code is released under the Apache License 2.0, copyright 2026 Aariv Patel.
See `LICENSE`.

The SD 1.5 inpainting checkpoint is not part of this repository. The weights
are published by runwayml on Hugging Face under the CreativeML Open RAIL-M
license, and their use in the GPU run follows that license.

## Repository layout

```
honestangle/   core package, pngio, hashing, receipt, verify, cli, scene
tests/         33 unit tests, standard library unittest
demo/          local proof viewer
comfyui/       GPU run script
receipts/      written by the GPU run
```
