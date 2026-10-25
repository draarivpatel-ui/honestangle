# HonestAngle demo video, 60 seconds

Note. The GPU-run screens, the ComfyUI generation and `receipts/job_receipt.json`,
will be added once the run finishes. Everything below is already producible from
the repository as it stands. Narration totals about 180 words, a brisk 60 second
read; trim pauses or slow the scroll to fit the voice.

## Shot 1 (0 to 10 seconds)

**Screen.** The repository README, scrolled slowly through the intro and How it
works.

**Action.** A slow scroll, no cursor tricks needed.

**Narration.** "This is HonestAngle. It adds cryptographic provenance to
ComfyUI outputs. An original image is committed block by block under SHA 256
into a Merkle root receipt. Any later image verifies against that receipt, and
every changed block is localized exactly. That separates authentic regions from
regions infilled by diffusion."

## Shot 2 (10 to 24 seconds)

**Screen.** A terminal in the repository root.

**Action.** Run `python -m honestangle.cli init original.png -o receipt.json
--block 32` on a deterministic scene image. The printed summary shows the image
hash, the Merkle root and the block count.

**Narration.** "First, init. The command splits the image into blocks and
writes a receipt holding the image hash, the Merkle root, and every per block
digest. A self integrity digest covers the rest of the receipt, so an edited
receipt is refused later instead of trusted."

## Shot 3 (24 to 38 seconds)

**Screen.** Same terminal.

**Action.** A copy of the original with one small region edited sits as
check.png. Run `python -m honestangle.cli verify check.png --receipt
receipt.json --json-out results.json`. The output shows TAMPERED, one block
changed, and the changed rectangle coordinates.

**Narration.** "Now verify a copy with one small region edited. The verdict is
TAMPERED. One block changed, and the tool prints the exact rectangle and the
tamper ratio. The full result, every block listed, goes to JSON for the
viewer."

## Shot 4 (38 to 51 seconds)

**Screen.** `demo/index.html` in a browser.

**Action.** Press Show synthetic sample, then coarsen the map to 2x so the lit
blocks merge into superblocks. Optionally drag in the three files from shots 2
and 3 afterwards.

**Narration.** "The proof viewer runs locally in a browser. Nothing is
uploaded. The built in synthetic sample shows changed blocks lit over the
original, and a selector coarsens the map. Drop in a real original, a checked
image, and the results JSON to see the same proof on your own files."

## Shot 5 (51 to 60 seconds)

**Screen.** `receipt.json` and `results.json` opened in an editor, then an end
card with the repository URL.

**Action.** Highlight `merkle_root` and `leaf_digests` in the receipt, then the
per-block entries in the results. Hold the end card with the repository link.

**Narration.** "Receipt and results are plain JSON. A GPU run pairs ComfyUI at
a pinned commit with the SD 1.5 inpainting open weights, and its job receipt
will land in the receipts folder. Link on screen now."
