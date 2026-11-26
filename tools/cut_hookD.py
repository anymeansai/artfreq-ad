#!/usr/bin/env python3
"""Cuts ad D's shots out of the take d-orbit (tools/adreel, filmHookD): crops of its cameras,
scaled with Lanczos (PIL, with sub-pixel crop boxes), moved as the edit says (edit_hookD.SHOTS).

    python3 tools/cut_hookD.py <takes-dir>

A plot shot is a 9:16 crop of the live view between two frequencies whose right edge follows the
view's "now" (or, from `track` on, holds still on what has just been drawn, as the view scrolls
it away). The view scrolls in whole columns (256 samples, 6.25 a picture: steps of 6, 6, 6, 7); a
now-following crop moves by the fraction of a column the view has not shown yet, so the scroll is
steady. `zoom` keys scale the crop about an `origin` (a point of the output). Nothing is retimed,
recoloured, sharpened or drawn on: every output picture is one take picture, cropped and scaled.

Writes hookD/assets/video/<shot>.mp4 (H.264, 30 fps, no sound) and hookD/assets/data/hud.json
(the Density of every ad picture, as the knob read it).
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import edit_hookD as edit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / edit.PROJECT
VIDEO = PROJECT / "assets" / "video"
DATA = PROJECT / "assets" / "data"

HOP = 256                      # samples a column of the live view
SPF = edit.SAMPLES_PER_FRAME   # 1600: 6.25 columns a picture


def ease(name, x):
    x = min(1.0, max(0.0, x))
    if name == "linear":
        return x
    if name == "expo.out":
        return 1.0 if x >= 1.0 else 1.0 - 2.0 ** (-10.0 * x)
    if name == "inout":            # cubic-bezier(0.65, 0, 0.35, 1), close enough: an in-out quint
        return 16 * x ** 5 if x < 0.5 else 1 - (-2 * x + 2) ** 5 / 2
    if name == "out":              # cubic-bezier(0.16, 1, 0.3, 1)
        return 1 - (1 - x) ** 4
    if name == "back.out":         # a little overshoot (about 2 %)
        c1 = 0.6
        c3 = c1 + 1
        return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
    raise ValueError(name)


def zoom_at(keys, t):
    """keys: [(t, z, ease into this key)], first key's ease ignored."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, z0, _), (t1, z1, e) in zip(keys, keys[1:]):
        if t <= t1:
            return z0 + (z1 - z0) * ease(e, (t - t0) / (t1 - t0))
    return keys[-1][1]


class Plot:
    """Where things are in the plot camera's pictures."""

    def __init__(self, meta, cam):
        self.px, self.py, self.pw, self.ph = meta["rects"]["plot-pt"]
        self.ax, self.ay, self.aw, self.ah = cam["area"]
        self.s = cam["scale"]
        self.pt_per_s = self.pw / meta["liveSeconds"]
        self.colw = HOP / edit.SAMPLE_RATE * self.pt_per_s * self.s
        self.now_x = (self.px + self.pw - self.ax) * self.s
        self.width, self.height = cam["width"], cam["height"]

    def y(self, hz):
        return (self.py + self.ph * math.log10(20000.0 / hz) / 3.0 - self.ay) * self.s


def column_phase(video, cam_first, plot, frames):
    """A take picture whose view moved 7 columns (the others move 6), measured on the pictures:
    the shift of the starfield between pictures, to the nearest column."""
    w, h = plot.width, plot.height
    y0, y1 = int(plot.y(11500)), int(plot.y(7500))
    first = frames[0] - cam_first
    n = len(frames)
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf",
           f"select='between(n\\,{first}\\,{first + n - 1})',crop={w}:{y1 - y0}:0:{y0}", "-vsync", "0",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    rows = np.frombuffer(raw, np.uint8).reshape(n, y1 - y0, w).astype(np.float64).sum(axis=1)
    sevens = []
    x = np.arange(w)
    for i in range(1, n):
        best = None
        for k in (5, 6, 7, 8):
            # what was at x one picture ago is at x - k columns now
            shifted = np.interp(x - k * plot.colw, x, rows[i])
            lo, hi = int(9 * plot.colw), int(w * 0.85)
            err = np.mean((shifted[lo:hi] - rows[i - 1][lo:hi]) ** 2)
            if best is None or err < best[0]:
                best = (err, k)
        if best[1] == 7:
            sevens.append(frames[i])
    assert sevens, "no 7-column step found"
    steps = sorted({(f - sevens[0]) % 4 for f in sevens})
    assert steps == [0], f"7-column steps are not every 4 pictures: {sevens[:12]}"
    return sevens[0]


class Shot:
    def __init__(self, spec, meta, cams, takes):
        self.spec = spec
        self.name = spec["name"]
        self.cam_name = spec["cam"]
        self.cam = cams[self.cam_name]
        self.first = meta["marks"]["ad0"] + round(spec["start"] * edit.FPS)
        self.frames = round(spec["dur"] * edit.FPS)
        self.out_w, self.out_h = spec.get("out", (1080, 1920))
        VIDEO.mkdir(parents=True, exist_ok=True)
        self.path = VIDEO / f"{self.name}.mp4"
        self.enc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{self.out_w}x{self.out_h}", "-framerate", str(edit.FPS), "-i", "-",
             "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
             "-c:v", "libx264", "-preset", "slow", "-crf", "10", "-profile:v", "high", "-g", "15", "-bf", "0",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
             "-movflags", "+faststart", str(self.path)], stdin=subprocess.PIPE)
        self.done = 0

    def wants(self, take_frame):
        return self.first <= take_frame < self.first + self.frames

    def box(self, take_frame, plot, seven):
        spec = self.spec
        t = spec["start"] + (take_frame - self.first) / edit.FPS          # ad time
        if self.cam_name != "plot":
            x0, y0, x1, y1 = spec["rect"]                                 # camera pixels
            w, h = x1 - x0, y1 - y0
            ox, oy = spec.get("origin", (self.out_w / 2, self.out_h / 2))
        else:
            top, bottom = plot.y(spec["f_hi"]), plot.y(spec["f_lo"])
            h = bottom - top
            w = h * self.out_w / self.out_h
            # columns the view has shown (D) and the true position (T), relative to a 7-step picture
            T = lambda n: 6.25 * (n - seven) + 0.125
            n_anchor = take_frame
            if spec.get("track") is not None:
                n_anchor = min(take_frame, self.first + round((spec["track"] - spec["start"]) * edit.FPS))
            lag = math.floor(T(take_frame)) - T(n_anchor)                # columns the content has moved on since
            right = plot.now_x - plot.colw - lag * plot.colw - spec.get("back", 0.0) * plot.pt_per_s * plot.s
            x0, y0 = right - w, top
            ox, oy = spec.get("origin", (self.out_w, self.out_h / 2))
        z = zoom_at(spec.get("zoom", [(0.0, 1.0, "linear")]), t)
        # the output point (ox, oy) stays where it is while the crop scales about it
        px, py = x0 + ox / self.out_w * w, y0 + oy / self.out_h * h
        w2, h2 = w / z, h / z
        bx0, by0 = px - ox / self.out_w * w2, py - oy / self.out_h * h2
        return (bx0, by0, bx0 + w2, by0 + h2)

    def add(self, image, take_frame, plot, seven):
        b = self.box(take_frame, plot, seven)
        W, H = image.size
        if b[0] < -0.5 or b[1] < -0.5 or b[2] > W + 0.5 or b[3] > H + 0.5:
            print(f"  WARNING {self.name}: picture {take_frame} crop {tuple(round(v, 1) for v in b)} leaves the camera {W}x{H}")
        b = (max(0.0, b[0]), max(0.0, b[1]), min(float(W), b[2]), min(float(H), b[3]))
        out = image.resize((self.out_w, self.out_h), Image.LANCZOS, box=b)
        self.enc.stdin.write(out.tobytes())
        self.done += 1

    def close(self):
        self.enc.stdin.close()
        assert self.enc.wait() == 0
        assert self.done == self.frames, (self.name, self.done, self.frames)
        print(f"{self.path.name}: {self.frames} pictures from take picture {self.first}")


def main():
    takes = Path(sys.argv[1])
    meta = json.loads((takes / "d-orbit.json").read_text())
    cams = {k.split("-")[-1]: v for k, v in meta["cameras"].items()}
    plot = Plot(meta, cams["plot"])

    ad0 = meta["marks"]["ad0"]
    seven = column_phase(takes / "d-orbit-plot.mkv", cams["plot"]["first"], plot, list(range(ad0, ad0 + 40)))
    print(f"plot: {plot.width}x{plot.height}, column {plot.colw:.4f} px, 7-column step at picture {seven}")

    shots = [Shot(s, meta, cams, takes) for s in edit.SHOTS]
    for cam_name in sorted({s.cam_name for s in shots}):
        cam = cams[cam_name]
        mine = [s for s in shots if s.cam_name == cam_name]
        lo = min(s.first for s in mine)
        hi = max(s.first + s.frames for s in mine)
        w, h = cam["width"], cam["height"]
        first_index = lo - cam["first"]
        assert first_index >= 0 and hi - cam["first"] <= cam["written"], (cam_name, lo, hi, cam)
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(takes / f"d-orbit-{cam_name}.mkv"), "-vf",
                                f"select='between(n\\,{first_index}\\,{hi - cam['first'] - 1})'", "-vsync", "0",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        size = w * h * 3
        for take_frame in range(lo, hi):
            buf = dec.stdout.read(size)
            assert len(buf) == size, (cam_name, take_frame)
            users = [s for s in mine if s.wants(take_frame)]
            if users:
                image = Image.frombuffer("RGB", (w, h), buf, "raw", "RGB", 0, 1)
                for s in users:
                    s.add(image, take_frame, plot, seven)
        dec.stdout.close()
        dec.wait()
    for s in shots:
        s.close()

    # The HUD's numbers: the knob's value for every ad picture.
    dens = json.loads((takes / "d-orbit-density.json").read_text())
    values = [dens["density"][ad0 + k - dens["firstFrame"]] for k in range(round(edit.AD_SECONDS * edit.FPS))]
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "hud.json").write_text(json.dumps({"fps": edit.FPS, "density": [round(v) for v in values]}))
    print(f"hud.json: density {values[0]:.0f} .. {values[-1]:.0f}")


if __name__ == "__main__":
    main()
