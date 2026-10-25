"""Deterministic synthetic test images: no external assets, reproducible bytes."""
import math

from .pngio import write_png_file


def gradient_scene(width, height, channels=3):
    """A deterministic scene: horizontal gradient plus two filled circles."""
    cx1, cy1, r1 = int(width * 0.3), int(height * 0.4), int(min(width, height) * 0.18)
    cx2, cy2, r2 = int(width * 0.7), int(height * 0.65), int(min(width, height) * 0.12)
    px = bytearray(width * height * channels)
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * channels
            px[i] = (x * 255) // max(1, width - 1)
            px[i + 1] = (y * 255) // max(1, height - 1)
            px[i + 2] = 128
            d1 = math.hypot(x - cx1, y - cy1)
            d2 = math.hypot(x - cx2, y - cy2)
            if d1 <= r1:
                px[i] = 240; px[i + 1] = 90; px[i + 2] = 40
            if d2 <= r2:
                px[i] = 30; px[i + 1] = 200; px[i + 2] = 120
    return bytes(px)


def write_scene(path, width, height, channels=3):
    write_png_file(path, width, height, channels, gradient_scene(width, height, channels))


def edit_region(pixels, width, height, channels, x0, y0, w, h):
    """Return a copy with one rectangle overwritten with a distinct pattern."""
    px = bytearray(pixels)
    for y in range(y0, min(y0 + h, height)):
        for x in range(x0, min(x0 + w, width)):
            i = (y * width + x) * channels
            px[i] = (px[i] + 64) % 256
            px[i + 1] = 255 - px[i + 1]
            px[i + 2] = (px[i + 2] * 3) % 256
    return bytes(px)
