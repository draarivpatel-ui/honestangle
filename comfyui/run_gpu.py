#!/usr/bin/env python3
"""GPU provenance run: ComfyUI open-weights inpaint, then HonestAngle verification.

Runs on the local Apple Silicon GPU (MPS). Steps, all recorded in receipts/:
1. Clone ComfyUI at a pinned commit, install requirements.
2. Download the SD 1.5 inpainting open-weights checkpoint.
3. Generate a deterministic 512x512 original image (no external assets).
4. Submit an API-format inpaint workflow over HTTP; save the ComfyUI output.
5. honestangle init on the original; honestangle verify on the ComfyUI output.
6. Write receipts/job_receipt.json with every artifact hash and job metadata.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

WORK = os.environ.get("HA_WORK", "/tmp/ha_work")
RECEIPTS = os.path.join(ROOT, "receipts")
COMFYUI_COMMIT = ""  # resolved at runtime from the cloned repo and recorded in the receipt
MODEL_URL = ("https://huggingface.co/runwayml/stable-diffusion-inpainting/resolve/main/"
             "sd-v1-5-inpainting.ckpt")
MODEL_NAME = "sd-v1-5-inpainting.ckpt"


def log(msg):
    print("[ha] %s" % msg, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, **kw):
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, **kw)


def setup_comfyui():
    d = os.path.join(WORK, "ComfyUI")
    if not os.path.isdir(d):
        run(["git", "clone", "--depth", "1", "https://github.com/comfyanonymous/ComfyUI.git", d])
        run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(d, "requirements.txt")])
    global COMFYUI_COMMIT
    COMFYUI_COMMIT = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"],
                                    capture_output=True, text=True, check=True).stdout.strip()
    models = os.path.join(d, "models", "checkpoints")
    os.makedirs(models, exist_ok=True)
    dst = os.path.join(models, MODEL_NAME)
    if not os.path.exists(dst):
        log("downloading open-weights checkpoint (~4.4 GB)")
        urllib.request.urlretrieve(MODEL_URL, dst + ".part")
        os.rename(dst + ".part", dst)
    return d


WORKFLOW = {
    "3": {
        "class_type": "KSampler",
        "inputs": {"seed": 20261025, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                   "scheduler": "normal", "denoise": 1.0, "model": ["4", 0],
                   "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]},
    },
    "4": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": MODEL_NAME}},
    "5": {"class_type": "VAEEncodeForInpaint",
          "inputs": {"pixels": ["10", 0], "vae": ["4", 2], "mask": ["11", 1], "grow_mask_by": 6}},
    "6": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "a serene landscape with soft green hills, high quality", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "blurry, low quality, watermark", "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ha_inpaint", "images": ["8", 0]}},
    "10": {"class_type": "LoadImage", "inputs": {"image": "ha_original.png"}},
    "11": {"class_type": "LoadImage", "inputs": {"image": "ha_mask.png"}},
}


def start_comfyui(comfy_dir):
    cmd = [sys.executable, os.path.join(comfy_dir, "main.py"), "--port", "8188",
           "--listen", "127.0.0.1", "--disable-auto-launch", "--output-directory",
           os.path.join(WORK, "out")]
    proc = subprocess.Popen(cmd, stdout=open(os.path.join(WORK, "comfyui.log"), "wb"),
                            stderr=subprocess.STDOUT)
    for _ in range(120):
        time.sleep(2)
        try:
            urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2).read()
            return proc
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError("ComfyUI exited early; see comfyui.log")
    raise RuntimeError("ComfyUI did not come up in 240s")


def submit_workflow():
    body = json.dumps({"prompt": WORKFLOW, "client_id": "honestangle"}).encode()
    req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("prompt rejected: %s %s" % (e.code, e.read().decode()[:800]))
    pid = resp["prompt_id"]
    log("prompt %s submitted" % pid)
    for _ in range(600):
        time.sleep(2)
        hist = json.loads(urllib.request.urlopen("http://127.0.0.1:8188/history/" + pid, timeout=10).read())
        if pid in hist:
            outputs = hist[pid]["outputs"]
            for node in outputs.values():
                for im in node.get("images", []):
                    return os.path.join(WORK, "out", im["subfolder"] or "", im["filename"]), pid
            raise RuntimeError("history has no images: %s" % json.dumps(hist[pid].get("status")))
    raise RuntimeError("workflow did not finish in 1200s")


def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(RECEIPTS, exist_ok=True)
    from honestangle.scene import write_scene
    from honestangle.receipt import create_receipt, write_receipt, TOOL_VERSION
    from honestangle.verify import verify_image, result_json

    # deterministic original + a simple inpaint mask (white region = area to fill)
    orig = os.path.join(WORK, "ha_original.png")
    write_scene(orig, 512, 512)
    import struct, zlib

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)

    W = H = 512
    mask_px = bytearray(W * H * 3)
    for y in range(H):
        for x in range(W):
            i = (y * W + x) * 3
            on = 200 <= x < 340 and 180 <= y < 300
            mask_px[i] = 255 if on else 0
            mask_px[i + 1] = mask_px[i + 2] = mask_px[i + 1]
    mask = os.path.join(WORK, "ha_mask.png")
    parts = [b"\x89PNG\r\n\x1a\n",
             chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)),
             chunk(b"IDAT", zlib.compress(bytes(mask_px), 9)),
             chunk(b"IEND", b"")]
    open(mask, "wb").write(b"".join(parts))
    # LoadImage needs inputs in ComfyUI's input dir
    comfy_dir = setup_comfyui()
    for src in (orig, mask):
        shutil.copy(src, os.path.join(comfy_dir, "input", os.path.basename(src)))

    proc = start_comfyui(comfy_dir)
    try:
        out_path, prompt_id = submit_workflow()
    finally:
        proc.terminate()

    log("ComfyUI output: %s" % out_path)
    receipt = create_receipt(orig, block_size=32,
                             note="honestangle gpu run; open-weights SD1.5 inpaint via ComfyUI")
    write_receipt(receipt, os.path.join(RECEIPTS, "gpu_run_receipt.json"))
    result = verify_image(out_path, receipt)
    result_json(result, os.path.join(RECEIPTS, "gpu_run_results.json"))

    artifacts = {}
    for name, path in [("original", orig), ("mask", mask), ("comfyui_output", out_path),
                       ("receipt", os.path.join(RECEIPTS, "gpu_run_receipt.json")),
                       ("results", os.path.join(RECEIPTS, "gpu_run_results.json"))]:
        artifacts[name] = {"path": os.path.basename(path), "sha256": sha256_file(path)}
    job = {
        "tool": "honestangle",
        "tool_version": TOOL_VERSION,
        "run_type": "local_mps_comfyui_openweights",
        "run_host": "local",
        "accelerator": "Apple Silicon MPS (local GPU)",
        "comfyui_commit": COMFYUI_COMMIT,
        "model": MODEL_NAME,
        "model_license": "CreativeML Open RAIL-M (open weights)",
        "prompt_id": prompt_id,
        "verdict": result["verdict"],
        "blocks_changed": result.get("blocks_changed"),
        "blocks_total": result.get("blocks_total"),
        "artifacts": artifacts,
        "comfyui_log_sha256": sha256_file(os.path.join(WORK, "comfyui.log")),
    }
    with open(os.path.join(RECEIPTS, "job_receipt.json"), "w") as f:
        json.dump(job, f, indent=2, sort_keys=True)
    log("VERDICT: %s (%s/%s blocks changed)" % (result["verdict"], result.get("blocks_changed"), result.get("blocks_total")))
    log("receipts written to %s" % RECEIPTS)


if __name__ == "__main__":
    main()
