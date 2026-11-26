#!/usr/bin/env python3
"""The pictures ad D plays through ArtFreq: a ringed planet, a crescent moon over waves, a spiral
galaxy, a comet and a starfield. Drawn here with code (numpy + PIL), white on opaque black, so
ArtFreq's Auto mode plays them as Original (bright is loud). No faces, people or photos.

    python3 tools/make_pictures_hookD.py <takes-dir>

Each picture is drawn at the shape its object has on screen in ArtFreq's live view (10 s across
764 points, 3 decades across 462 points: 76.4 points a second, 154 points a decade), so circles
come out round. tools/adreel places them (filmHookD); the boxes are listed in PICTURES.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PASS_SECONDS = 8.0                 # Length 4 bars at 120 BPM
PT_PER_S, PT_PER_DECADE = 76.4, 154.0

# name: (start, end as fractions of the pass, low Hz, high Hz, mode)
PICTURES = {
    "planet": (0.000, 0.190, 1100.0, 6300.0, "original"),
    "moon":   (0.250, 0.406, 2000.0, 6300.0, "original"),
    "waves":  (0.250, 0.406, 1100.0, 1800.0, "original"),
    "galaxy": (0.500, 0.656, 1200.0, 6300.0, "outline"),
    "comet":  (0.750, 0.940, 1100.0, 6300.0, "original"),
    "stars":  (0.000, 0.940, 7500.0, 11500.0, "original"),
}


def aspect(name):
    s, e, lo, hi, _ = PICTURES[name]
    return ((e - s) * PASS_SECONDS * PT_PER_S) / (math.log10(hi / lo) * PT_PER_DECADE)


def size_for(name, long_side=1024):
    a = aspect(name)
    return (long_side, max(8, round(long_side / a))) if a >= 1 else (max(8, round(long_side * a)), long_side)


def grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    return (x + 0.5) / w, (y + 0.5) / h       # 0..1, y down


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def save(v, path):
    v = np.clip(v, 0.0, 1.0)
    Image.fromarray((v * 255.0 + 0.5).astype(np.uint8), "L").convert("RGB").save(path)


def planet(w, h):
    """A sphere lit from the upper left, a tilted ring with a gap, the ring's shadow on it."""
    u, v = grid(w, h)
    cx, cy, r = 0.50, 0.52, 0.27
    # in the box's own units: the box is square on screen, so x and y scale alike
    dx, dy = (u - cx) / r, (v - cy) / r
    d2 = dx * dx + dy * dy
    inside = d2 < 1.0
    nz = np.sqrt(np.clip(1.0 - d2, 0.0, 1.0))
    light = np.array([-0.55, -0.55, 0.63])
    light /= np.linalg.norm(light)
    lambert = np.clip(dx * light[0] + dy * light[1] + nz * light[2], 0.0, 1.0)
    # soft cloud bands across the sphere, following its latitude
    bands = 0.88 + 0.12 * np.sin(dy * 9.0 + 0.6 * np.sin(dx * 3.0))
    sphere = (0.22 + 0.78 * lambert ** 0.9) * bands * smoothstep(1.0, 0.97, np.sqrt(d2))
    sphere = np.where(inside, sphere, 0.0)

    # the ring: an ellipse tilted -18 degrees, outer 0.48 x 0.13, inner 0.34 x 0.092, a gap at 0.42
    t = math.radians(-18.0)
    rx = (u - cx) * math.cos(t) + (v - cy) * math.sin(t)
    ry = -(u - cx) * math.sin(t) + (v - cy) * math.cos(t)
    q = np.sqrt((rx / 0.48) ** 2 + (ry / 0.13) ** 2)            # 1 at the outer edge
    q_in = 0.34 / 0.48
    ring = smoothstep(q_in - 0.01, q_in + 0.02, q) * smoothstep(1.0, 0.975, q)
    ring *= 1.0 - 0.9 * np.exp(-((q - 0.875) / 0.018) ** 2)     # the gap
    ring *= 0.70 + 0.30 * smoothstep(q_in, 1.0, q)              # brighter outward
    behind = (ry < 0) & inside                                  # the far half is hidden by the sphere
    ring = np.where(behind, 0.0, ring)

    # the ring's shadow: a band across the sphere just above the ring's near edge
    shadow = np.exp(-((ry - (-0.055)) / 0.022) ** 2) * inside
    sphere *= 1.0 - 0.75 * shadow

    img = np.maximum(sphere, ring * 0.95)
    return img


def moon(w, h):
    """A crescent lit from the left, craters on the lit part, faint earthshine on the rest."""
    u, v = grid(w, h)
    ax = w / h                                                  # keep it round: x in units of height
    x, y = u * ax, v
    cx, cy, r = 0.50 * ax, 0.50, 0.42
    d = np.hypot(x - cx, y - cy)
    disc = smoothstep(r, r - 0.008, d)
    d2 = np.hypot(x - (cx + 0.20), y - (cy - 0.04))
    lit = disc * smoothstep(r * 0.98, r * 0.98 + 0.03, d2)
    shade = 0.75 + 0.25 * smoothstep(r, 0.0, d)                 # limb darkening
    rng = np.random.default_rng(7)
    craters = np.ones_like(u)
    for _ in range(14):
        a = rng.uniform(math.radians(110), math.radians(250))
        rr = rng.uniform(0.05, 0.36)
        px, py = cx + rr * math.cos(a), cy + rr * math.sin(a)
        cr = rng.uniform(0.018, 0.05)
        dc = np.hypot(x - px, y - py)
        craters *= 1.0 - 0.38 * smoothstep(cr, cr * 0.6, dc)
        craters += 0.12 * np.exp(-((dc - cr) / 0.006) ** 2)    # a bright rim
    body = lit * shade * craters
    earthshine = disc * 0.13
    return np.maximum(body, earthshine)


def waves(w, h):
    """Three wave lines, 2.5 periods across, fading back."""
    S = 4                                                      # drawn large, then scaled down smooth
    img = Image.new("L", (w * S, h * S), 0)
    dr = ImageDraw.Draw(img)
    r = max(3, h // 22) * S / 2
    for k, (level, phase) in enumerate(((0.85, 0.0), (0.68, 0.9), (0.52, 1.8))):
        y0 = h * S * (0.25 + 0.25 * k)
        for x in range(0, w * S + 1, 2):
            y = y0 + h * S * 0.13 * math.sin(2 * math.pi * 2.5 * x / (w * S) + phase)
            dr.ellipse([x - r, y - r, x + r, y + r], fill=int(level * 255))
    img = img.resize((w, h), Image.LANCZOS)
    return np.asarray(img, dtype=np.float64) / 255.0


def galaxy(w, h):
    """Two logarithmic spiral arms of solid strokes tapering out, and a core: played in Outline."""
    S = 4                                                      # drawn large, then scaled down smooth
    img = Image.new("L", (w * S, h * S), 0)
    dr = ImageDraw.Draw(img)
    cx, cy = w * S / 2, h * S / 2
    rmax = min(w, h) * S * 0.47
    for arm in range(2):
        pts = []
        for i in range(400):
            t = i / 399.0
            ang = arm * math.pi + t * 3.3 * math.pi
            rad = rmax * (0.10 + 0.90 * t)
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang) * (h / w) ** 0 * 1.0))
        for i in range(len(pts) - 1):
            t = i / (len(pts) - 1)
            width = (40 - 32 * t) * S * w / 880
            level = int(255 * (1.0 - 0.45 * t))
            dr.line([pts[i], pts[i + 1]], fill=level, width=max(1, int(width)))
            dr.ellipse([pts[i][0] - width / 2, pts[i][1] - width / 2, pts[i][0] + width / 2, pts[i][1] + width / 2], fill=level)
    cr = min(w, h) * S * 0.085
    dr.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=255)
    img = img.resize((w, h), Image.LANCZOS)
    return np.asarray(img, dtype=np.float64) / 255.0


def comet(w, h):
    """A bright head at the upper right with a glow, its tail falling to the lower left."""
    u, v = grid(w, h)
    hx, hy = 0.86, 0.14
    tx, ty = 0.04, 0.93
    ax_, ay_ = tx - hx, ty - hy
    L = math.hypot(ax_, ay_)
    ax_, ay_ = ax_ / L, ay_ / L
    px, py = u - hx, v - hy
    along = px * ax_ + py * ay_                                 # 0 at the head, L at the tail's end
    across = -px * ay_ + py * ax_
    s = np.clip(along / L, 0.0, 1.0)
    width = 0.018 + 0.20 * s ** 1.1
    tail = np.where(along > 0, np.exp(-(across / width) ** 2) * (0.95 - 0.80 * s) * smoothstep(1.0, 0.9, s), 0.0)
    rng = np.random.default_rng(3)
    streaks = np.zeros_like(u)
    for _ in range(7):
        off = rng.uniform(-0.6, 0.6)
        streaks += 0.5 * np.exp(-((across - off * width) / 0.006) ** 2) * (along > 0) * (1.0 - s) * smoothstep(1.0, 0.6, s)
    d = np.hypot(u - hx, v - hy)
    head = smoothstep(0.055, 0.035, d) + 0.6 * np.exp(-(d / 0.07) ** 2)
    return np.maximum(np.maximum(tail, streaks), np.minimum(head, 1.0))


def stars(w, h):
    """Stars on the exact 16th grid of the pass (none in its last beat): bright on beats, softer
    on 8ths, faint on 16ths, so ArtFreq plays an accented 16th sparkle."""
    img = np.zeros((h, w))
    rng = np.random.default_rng(11)
    span = PICTURES["stars"][1] - PICTURES["stars"][0]
    for k in range(60):                                         # 64 sixteenths a pass, the last 4 left out
        x = (k / 64.0) / span * w
        level = (1.0 if k % 4 == 0 else 0.62 if k % 2 == 0 else 0.36) + rng.uniform(-0.08, 0.08)
        for _ in range(1 if k % 4 else 2):
            y = rng.uniform(0.12, 0.88) * h
            x0, x1 = int(round(x)), int(round(x)) + 3
            y0, y1 = int(round(y - 2)), int(round(y + 3))
            img[max(0, y0):min(h, y1), max(0, x0):min(w, x1)] = np.clip(level, 0.0, 1.0)
    return img


DRAW = {"planet": planet, "moon": moon, "waves": waves, "galaxy": galaxy, "comet": comet, "stars": stars}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, draw in DRAW.items():
        w, h = size_for(name)
        save(draw(w, h), out / f"d-{name}.png")
        print(f"d-{name}.png {w}x{h}")


if __name__ == "__main__":
    main()
