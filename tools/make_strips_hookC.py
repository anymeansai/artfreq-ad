#!/usr/bin/env python3
"""Ad C's drawings: one picture per pass of the drawing (2 bars = 4 s at 120 BPM), the words
laid out as they will read on a phone, then turned a quarter left, because the ad shows ArtFreq
FX's live view turned a quarter right (time running up the screen). Each picture is dropped into
ArtFreq FX as an ordinary picture layer, 300 Hz - 12 kHz, the whole pass long.

    python3 tools/make_strips_hookC.py <out-dir>      # writes c-p1.png ... c-p3.png
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT = "/home/user/ArtFreq-plug-in/assets/fonts/Inter-Bold.ttf"
PX_PER_S = 829.0          # on screen: 2.316 s of the live view over 1920 px
BEAT = 0.5 * PX_PER_S     # 120 BPM
W = 1018                  # 300 Hz - 12 kHz on screen (1.602 decades at 635.7 px a decade)
H = round(4.0 * PX_PER_S) # one pass, 4 s

# (word, first beat, beats) per pass. A word's ink starts at the top of its first beat, so it
# sounds on that beat; the last beat of every pass stays empty (the next drawing goes in there).
PASSES = [
    [("HEY", 0, 2), ("THIS", 2, 1), ("BEAT", 3, 1), ("IS", 4, 1), ("TALKING", 5, 2)],
    [("TYPE", 0, 2), ("ANYTHING", 2, 2), ("DRAW", 4, 1), ("IT", 5, 1)],
    [("<bolt>", 0, 4), ("IN", 4, 1), ("ANY", 5, 1), ("TRACK", 6, 1)],
]


def word(draw, text, top, beats):
    slot = beats * BEAT
    probe = ImageFont.truetype(FONT, 400)
    x0, y0, x1, y1 = probe.getbbox(text)                    # ink box at 400 px
    aspect = (x1 - x0) / (y1 - y0)
    ink_h = min(0.78 * slot, 940 / aspect)                  # as tall as the beat allows, at most 940 wide
    font = ImageFont.truetype(FONT, round(400 * ink_h / (y1 - y0)))
    x0, y0, x1, y1 = font.getbbox(text)
    x = (W - (x1 - x0)) / 2 - x0
    y = top - y0
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))


def bolt(draw, top, beats):
    slot = beats * BEAT
    h = 0.86 * slot
    w = min(0.56 * h, 900)
    ox, oy = (W - w) / 2, top
    pts = [(0.62, 0.0), (0.10, 0.57), (0.45, 0.57), (0.30, 1.0), (0.92, 0.40), (0.55, 0.40), (0.78, 0.0)]
    draw.polygon([(ox + px * w, oy + py * h) for px, py in pts], fill=(255, 255, 255, 255))


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for i, words in enumerate(PASSES, 1):
        screen = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # as on the phone: time down the page
        draw = ImageDraw.Draw(screen)
        for text, beat, beats in words:
            top = beat * BEAT
            bolt(draw, top, beats) if text == "<bolt>" else word(draw, text, top, beats)
        plot = screen.rotate(90, expand=True)              # a quarter left: time across, frequency up
        plot = plot.resize((1024, round(1024 * plot.height / plot.width)), Image.LANCZOS)
        plot.save(out / f"c-p{i}.png")
        screen.convert("LA").resize((W // 4, H // 4)).save(out / f"c-p{i}-preview.png")
        print(f"c-p{i}.png {plot.size}")


if __name__ == "__main__":
    main()
