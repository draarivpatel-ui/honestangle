# HonestAngle submission answers

Short answers for the ComfyUI Open Source Higgsfield challenge Typeform. Wording
adapted to the actual fields at submission time.

## Project name

HonestAngle

## Repository URL

https://github.com/draarivpatel-ui/honestangle

Live demo viewer: https://aariv.me/honestangle/demo/

## Summary (100 words)

HonestAngle adds cryptographic pixel provenance to ComfyUI outputs. A source
image is committed block by block under SHA-256 into a Merkle root receipt. Any
later image verifies against that receipt, and changed blocks are localized
exactly, separating authentic regions from diffusion-infilled ones. The core is
pure Python standard library with zero dependencies and 33 passing unit tests.
A local browser demo lights up edited blocks. A scripted GPU run generates an
image with ComfyUI and pinned open weights, then proves which blocks the
diffusion step changed. Higgsfield promised open source and did not deliver, so
this is the honest rebuild.

## What Higgsfield app concept does it rebuild

Higgsfield-style generative editing apps repaint parts of a picture with
diffusion and hand back a result with no proof of what changed. HonestAngle is
the provenance counterpart to that concept, rebuilt open source on ComfyUI. It
commits a source image into a Merkle receipt and then shows exactly which
blocks any later edit touched, so an honest answer about an image becomes a
checkable artifact instead of a promise.

## Demo video URL

https://youtu.be/5p0ibDusbWY

## Social post (live)

https://x.com/MonkeyRunStore/status/2114429022197137427

## License

Apache-2.0 for the code, copyright 2026 Aariv Patel. The SD 1.5 inpainting
weights used in the GPU run are external to the repository and carry the
CreativeML Open RAIL-M license from their publisher.

## Category suggestion

Most Innovative. It turns a generated edit into a verifiable claim, localizing
diffusion changes at block resolution with a pure standard library core and a
self-checking receipt.

Open Weights Only. The whole pipeline runs on open weights, the SD 1.5
inpainting checkpoint under CreativeML Open RAIL-M, driven through
open-source ComfyUI by a dependency-free Python tool.
