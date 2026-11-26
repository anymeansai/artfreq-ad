"""The edit of ad-artfreq-hookD ("Resolve"), an Instagram Reel / TikTok. One take (d-orbit) of
the ArtFreq instrument playing a drawing of a night sky over 4 bars, Repeat on; Density turned up
on its knob from 64 lines to 1024. Read by cut_hookD.py (pictures) and mix_audio.py (sound:
`python3 tools/mix_audio.py <takes> edit_hookD`).

Ad time t is take picture ad0 + 30 t (ad0: 1 s into the drawing's second pass). 120 BPM: the
drawing's bars start at ad -1, 1, 3, 5 (pass 2) and 7, 9, 11, 13 (pass 3), 15 (pass 4).
Where the pictures are drawn in the pass (8 s): planet 0 - 1.52 s, moon and waves 2.0 - 3.25,
galaxy 4.0 - 5.25 (Outline), comet 6.0 - 7.52, stars all along to 7.52; the last beat is empty.
"""

PROJECT = "hookD"
FPS = 30
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
AD_SECONDS = 16.0      # 8 bars: the Reel loops in time
BPM = 120.0

# The plot shots: the live view from 140 Hz to 12 kHz, 9:16 (the newest 2.19 s). The drawing
# (1.1 - 6.3 kHz) then lies between y 278 and 1031, the stars above it, and the band under it
# (1 kHz down) is empty for the words, inside the apps' safe area.
W = dict(cam="plot", f_lo=140.0, f_hi=12000.0)
# The moon up close: 1.38 - 9.13 kHz, from 2.07 to 3.0 s into the pass.
M = dict(cam="plot", f_lo=1380.0, f_hi=9130.0)

SHOTS = [
    # 0 - 1: the hook. 64 lines: the planet printing at the right edge, pulled back to full frame.
    dict(name="s1-hook", start=0.0, dur=1.0, **W, zoom=[(0.0, 1.25, "linear"), (0.6, 1.0, "expo.out")], origin=(1080, 1150)),
    # 1 - 2: moon and waves at 128 lines.
    dict(name="s2-moon", start=1.0, dur=1.0, **W),
    # 2 - 3: the moon up close, held still as it scrolls (128 lines).
    dict(name="s3-macro", start=2.0, dur=1.0, **M, track=2.0, zoom=[(2.0, 1.0, "linear"), (3.0, 1.045, "inout")], origin=(540, 960)),
    # 3 - 5: the galaxy at 256 lines; held still once drawn.
    dict(name="s4-galaxy", start=3.0, dur=2.0, **W, track=4.25, zoom=[(3.0, 1.0, "linear"), (5.0, 1.06, "inout")], origin=(700, 650)),
    # 5 - 6.5: the comet at 512 lines, pushing in on its head.
    dict(name="s5-comet", start=5.0, dur=1.5, **W, zoom=[(5.0, 1.0, "linear"), (6.5, 1.12, "inout")], origin=(986, 384)),
    # 6.5 - 7: the Density knob turned to 1024 (camera pixels: 90 x 90 points at 12 px a point).
    dict(name="s6-knob", cam="knob", start=6.5, dur=0.5, rect=(24, 72, 1104, 1152), out=(1080, 1080)),
    # 7 - 9: the drop. The same planet at 1024 lines; held still once drawn.
    dict(name="s7-drop", start=7.0, dur=2.0, **W, track=8.52,
         zoom=[(7.0, 1.0, "linear"), (7.2, 1.10, "back.out"), (7.5, 1.05, "inout")], origin=(1080, 671)),
    # 9 - 10.5: moon and waves at 1024.
    dict(name="s8-moon", start=9.0, dur=1.5, **W),
    # 10.5 - 11: the moon up close again, framed as in s3.
    dict(name="s9-macro", start=10.5, dur=0.5, **M, track=10.5, back=0.5, zoom=[(10.5, 1.0, "linear"), (11.0, 1.02, "inout")], origin=(540, 960)),
    # 11 - 12: the window: the live view's newest seconds and the layer list with the pictures.
    dict(name="s10-ui", cam="ui", start=11.0, dur=1.0, rect=(0, 0, 2240, 1784), out=(1080, 860),
         zoom=[(11.0, 1.0, "linear"), (12.0, 1.04, "inout")], origin=(540, 430)),
    # 12 - 13: the galaxy at 1024, held still once drawn.
    dict(name="s11-galaxy", start=12.0, dur=1.0, **W, track=12.25),
    # 13 - 16: under the end card (459 Hz - 6.9 kHz, the lower 1170 px of the page): the comet
    # rises, a beat of sky, the planet comes round again.
    dict(name="s12-end", cam="plot", f_lo=459.0, f_hi=6900.0, start=13.0, dur=3.0, out=(1080, 1170)),
]

# The sound: ArtFreq's output in the take, uncut, from ad0 for 16 s. Only its level is ridden:
# the galaxy is drawn in Outline, which plays much quieter (README), so it is brought up.
SOUND = [
    dict(take="d-orbit", mark="ad0", offset=0, at=0.0, seconds=16.0, gain=0.0, fade_in_ms=3.0, tail_ms=0.0, out_ms=3.0,
         ride=[(2.95, 4.35, 12.0), (10.95, 12.35, 12.0)]),
]

DRUMS = None


def _bed():
    """The drums under it (made in mix_audio.py from sines and noise), section by section."""
    ev = [(0.0, "kick", -3.0), (0.0, "sub", -4.0)]                       # the hook: one hit
    ev += [(1.0, "kick", -3.0), (2.0, "kick", -3.0)]                     # half time
    for b in range(4):                                                   # 3 - 5: four on the floor
        t = 3.0 + 0.5 * b
        ev += [(t, "kick", -3.0), (t + 0.25, "open", -14.0)]
        if b % 2:
            ev.append((t, "clap", -4.0))
    for b in range(3):                                                   # 5 - 6.5: the build
        ev.append((5.0 + 0.5 * b, "kick", -3.0))
    roll = [5.0 + 0.25 * i for i in range(3)] + [5.75 + 0.125 * i for i in range(6)]
    for i, t in enumerate(roll):
        ev.append((t, "clap", -12.0 + 9.0 * i / (len(roll) - 1)))
    # 6.5 - 7: nothing at all
    ev += [(7.0, "crash", -8.0)]
    for b in range(16):                                                  # 7 - 15: the drop
        t = 7.0 + 0.5 * b
        ev.append((t, "kick", -3.0))
        if b % 2:
            ev.append((t, "clap", -3.0))
        if t < 14.5:
            ev.append((t + 0.25, "open", -11.0))
        if b % 4 == 0:
            ev.append((t, "sub", -5.0))
    ev += [(15.0, "kick", -3.0), (15.0, "sub", -4.0)]                    # one last hit, then ArtFreq alone
    return ev


DRUM_EVENTS = _bed()
DRUM_EVENTS_GAIN = -10.0      # the drums as loud as ArtFreq (both about -21 LUFS alone)

SECTIONS = (("hook", 0, 1), ("build", 1, 5), ("riser", 5, 7), ("drop", 7, 11), ("ui", 11, 13), ("end", 13, 16))
STILLS = []
