# Social drafts (X post is LIVE: https://x.com/MonkeyRunStore/status/2114429022197137427; r/comfyui writeup below is authorized by Billy, not yet posted)

Drafts for the HonestAngle launch. Neither is posted yet; the repository link
resolves once the public repo is up.

## X post

```
Higgsfield promised open source and never delivered it. HonestAngle is the rebuild. It commits ComfyUI images block by block under SHA-256 and localizes exactly which pixels diffusion changed. https://github.com/draarivpatel-ui/honestangle #OpenSourceHiggsfield @ComfyUI
```

Character count 270, within the 277 limit, including the link, the hashtag and
the mention.

## r/comfyui post

Suggested title.

HonestAngle, cryptographic pixel provenance for ComfyUI outputs

Body, about 250 words.

HonestAngle is a small open source tool for proving what a ComfyUI edit
changed. An original image is split into blocks and each block is hashed into a
Merkle tree receipt. Any later image verifies against that receipt. If the
bytes match everywhere, the verdict is VERIFIED. Where they differ, the exact
blocks that changed are named at pixel resolution, which separates authentic
regions from diffusion-infilled ones.

A receipt carries the image hash, the dimensions, the block size, the Merkle
root, and the full leaf digest list. It also carries a self-integrity digest
over its own fields, so editing the leaf list to hide a change breaks the
receipt and the verifier refuses it. The receipt also records the tool version,
the block size, and a UTC timestamp. Verdicts cover the full range, VERIFIED,
TAMPERED, REGENERATED, DIMENSIONS_MISMATCH, and RECEIPT_INVALID.

The core is pure Python standard library with zero pip dependencies, and 33
unit tests pass on Python 3.9. A local browser demo takes an original, a
checked image, and a results JSON, then lights the changed blocks over the
original. Nothing is uploaded anywhere. The page is a visualization only, and
the Python CLI is the verifier of record.

A scripted GPU run pairs ComfyUI at a pinned commit with the SD 1.5 inpainting
open weights. It generates a deterministic image, inpaints a masked region
through the HTTP API, then runs init and verify across the pair and writes
receipts with per-block results.

The code is Apache-2.0. Repository,
https://github.com/draarivpatel-ui/honestangle (the public repo goes up before
submission).
