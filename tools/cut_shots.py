#!/usr/bin/env python3
"""Cuts the ad's shots out of the takes filmed by tools/adreel.

    python3 tools/cut_shots.py <takes-dir> [edit-module]

The edit module (default `edit`, the first ad; `edit_hookB` for the second) lists the shots and
names the project folder they go into (its PROJECT, default the repository's root).

Writes assets/video/<shot>.mp4 (H.264, 30 fps, no sound: the sound is mixed by mix_audio.py)
and assets/img/<still>.png. A shot is a crop of the take's pictures, scaled down with Lanczos;
nothing is retimed, recoloured, sharpened or drawn on.
"""
import importlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
edit = importlib.import_module(sys.argv[2] if len(sys.argv) > 2 else "edit")

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / getattr(edit, "PROJECT", ".")
VIDEO = PROJECT / "assets" / "video"
IMG = PROJECT / "assets" / "img"


def even(v):
    return int(round(v / 2.0)) * 2


def framing(shot, meta):
    """(crop x, y, w, h in the take's pixels), (output w, h)."""
    rects = meta["rects"]
    scale = meta["scale"]
    kind = shot["frame"]
    prefix = shot.get("rects", "")

    def rect(name):
        for key in (prefix + name, "live/" + name, name):
            if key in rects:
                return rects[key]
        raise KeyError(f"{meta['name']}: no rect {name}")

    if kind == "tall":
        x, y, w, h = rect("live-plot")
        cw = w * shot["seconds"] / meta["liveSeconds"]          # the newest `seconds` of the view
        ow = shot.get("width", edit.OUT_W)
        return (x + w - cw, y, cw, h), (ow, even(h * ow / cw))
    if kind == "card":
        cw = edit.CARD_W / 1.25 * scale                          # 832 points of the window
        return (0, 0, cw, meta["height"]), (edit.CARD_W, edit.CARD_H)
    if kind == "fx-card":
        return (0, 0, meta["width"], meta["height"]), (edit.FX_CARD_W, edit.FX_CARD_H)
    if kind == "fx-zoom":
        x, y, w, h = rect("live-plot")
        cw = w * shot["seconds"] / meta["liveSeconds"]
        return (x + w - cw, y, cw, h), (edit.ZOOM_W, even(h * edit.ZOOM_W / cw))
    if kind == "plotcrop":
        # the newest part of the live view between two frequencies (the plot runs 20 Hz - 20 kHz
        # on a log scale), as many seconds as keep its pixels square at the output size
        import math
        x, y, w, h = rect("live-plot")
        ow, oh = shot["out"]
        y_of = lambda f: y + h * math.log10(20000.0 / f) / 3.0
        y0, y1 = y_of(shot["f_hi"]), y_of(shot["f_lo"])
        # `seconds` given: that much time, scaled to fit (time and frequency then scale apart)
        cw = w * shot["seconds"] / meta["liveSeconds"] if "seconds" in shot else (y1 - y0) * ow / oh
        return (x + w - cw, y0, cw, y1 - y0), (ow, oh)
    if kind == "crop":
        # a part of the window, given in points of the window: (x, y, w, h)
        x, y, w, h = (v * scale for v in shot["rect"])
        return (x, y, w, h), (shot["width"], even(h * shot["width"] / w))
    if kind == "window":
        return (0, 0, meta["width"], meta["height"]), (shot["width"], even(meta["height"] * shot["width"] / meta["width"]))
    raise ValueError(kind)


def run(cmd):
    subprocess.run(cmd, check=True)


def main():
    takes = Path(sys.argv[1])
    VIDEO.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)

    for shot in edit.SHOTS:
        meta = json.loads((takes / f"{shot['take']}.json").read_text())
        first = meta["marks"][shot["mark"]] + shot["offset"]
        last = first + shot["frames"] - 1
        assert 0 <= first and last < meta["frames"], (shot["name"], first, last, meta["frames"])
        (cx, cy, cw, ch), (ow, oh) = framing(shot, meta)
        crop = f"crop={round(cw)}:{round(ch)}:{round(cx)}:{round(cy)}"
        if "smooth" in shot:
            # The live view scrolls by whole columns (256 samples) while a picture is 1600 samples,
            # so it steps 6, 6, 6, 7 columns a picture. Moving the crop by the column fraction the
            # view has not yet shown makes the scroll steady; `jump` is a take picture with a step of 7.
            k, colw = shot["smooth"]["jump"], shot["smooth"]["colw"]
            x = f"{cx - colw:.3f}+{colw:.4f}*mod((n+{first - k})/4+0.125\,1)"
            crop = f"crop={round(cw)}:{round(ch)}:'{x}':{round(cy)}"
        vf = (f"select='between(n\\,{first}\\,{last})',setpts=N/{edit.FPS}/TB,{crop},"
              f"scale={ow}:{oh}:flags=lanczos+accurate_rnd+full_chroma_int:out_color_matrix=bt709:out_range=tv,format=yuv420p")
        out = VIDEO / f"{shot['name']}.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(takes / f"{shot['take']}.mkv"),
             "-vf", vf, "-an", "-r", str(edit.FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "10",
             "-profile:v", "high", "-g", "15", "-bf", "0",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
             "-movflags", "+faststart", str(out)])
        print(f"{out.name}: take {shot['take']} pictures {first}-{last}, {crop} -> {ow}x{oh}, "
              f"{out.stat().st_size / 1e6:.1f} MB")

    for still in edit.STILLS:
        meta = json.loads((takes / f"{still['take']}.json").read_text())
        (cx, cy, cw, ch), (ow, oh) = framing(still, meta)
        out = IMG / f"{still['name']}.png"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(takes / f"{still['take']}.mkv"),
             "-vf", f"select='eq(n\\,{still['index']})',crop={round(cw)}:{round(ch)}:{round(cx)}:{round(cy)},"
                    f"scale={ow}:{oh}:flags=lanczos+accurate_rnd+full_chroma_int",
             "-frames:v", "1", str(out)])
        print(f"{out.name}: {ow}x{oh}")


if __name__ == "__main__":
    main()
