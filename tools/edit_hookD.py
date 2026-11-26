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
# Moon and waves closer (1.3x): 229 Hz - 7 kHz, so the drawing (1.1 - 6.3 kHz) fills y 60 - 1040
# and the words still fit under it.
C = dict(cam="plot", f_lo=229.0, f_hi=7000.0)

SHOTS = [
    # 0 - 1: the hook. 64 lines: the planet printing at the right edge, pulled back through the second.
    dict(name="s1-hook", start=0.0, dur=1.0, **W, zoom=[(0.0, 1.25, "linear"), (1.0, 1.0, "linear")], origin=(1080, 1150)),
    # 1 - 2: moon and waves at 128 lines, a punch on the 1.0 kick as the moon starts printing.
    dict(name="s2-moon", start=1.0, dur=1.0, **W, zoom=[(1.0, 1.15, "linear"), (1.6, 1.0, "out")], origin=(1080, 560)),
    # 2 - 3: moon and waves closer (1.3x), held still once drawn (128 lines; the knob goes to 256).
    dict(name="s3-close", start=2.0, dur=1.0, **C, track=2.25, settle=0.25, zoom=[(2.0, 1.0, "linear"), (3.0, 1.05, "inout")], origin=(540, 560)),
    # 3 - 5: the galaxy at 256 lines, easing out to the wide frame so the cut at 5 continues it.
    dict(name="s4-galaxy", start=3.0, dur=2.0, **W, zoom=[(3.0, 1.06, "linear"), (5.0, 1.0, "inout")], origin=(700, 650)),
    # 5 - 6.5: the comet at 512 lines, a slow push.
    dict(name="s5-comet", start=5.0, dur=1.5, **W, zoom=[(5.0, 1.0, "linear"), (6.5, 1.05, "inout")], origin=(1080, 420)),
    # 6.5 - 7: the Density knob turned towards 1024 (camera pixels: 90 x 90 points at 12 px a point).
    dict(name="s6-knob", cam="knob", start=6.5, dur=0.5, rect=(80, 72, 1160, 1152), out=(1080, 1080)),
    # 7 - 9: the drop. The same planet at 1024 lines, its ring printing in at 3.2x (nothing older in
    # frame), pulling back to the wide frame as it completes, so the cut at 9 continues it.
    dict(name="s7-drop", start=7.0, dur=2.0, **W,
         zoom=[(7.0, 3.2, "linear"), (7.4, 2.4, "out"), (8.5, 1.0, "inout")], origin=(1080, 820)),
    # 9 - 10.5: moon and waves at 1024.
    dict(name="s8-moon", start=9.0, dur=1.5, **W),
    # 10.5 - 11: moon and waves closer again, framed as in s3.
    dict(name="s9-close", start=10.5, dur=0.5, **C, track=10.5, back=0.25, zoom=[(10.5, 1.0, "linear"), (11.0, 1.02, "inout")], origin=(540, 560)),
    # 11 - 12.25: the galaxy at 1024, while it plays.
    dict(name="s11-galaxy", start=11.0, dur=1.25, **W),
    # 12.25 - 13: the window: the live view's newest seconds and the layer list with the pictures.
    dict(name="s10-ui", cam="ui", start=12.25, dur=0.75, rect=(24, 0, 2240, 1765), out=(1080, 860),
         zoom=[(12.25, 1.0, "linear"), (13.0, 1.03, "inout")], origin=(540, 430)),
    # 13 - 16: under the end card (459 Hz - 6.9 kHz, the lower 1170 px of the page): the comet
    # rises, a beat of sky, the planet comes round again.
    dict(name="s12-end", cam="plot", f_lo=459.0, f_hi=6900.0, start=13.0, dur=3.0, out=(1080, 1170)),
]

# The sound: ArtFreq's output in the take, uncut, from ad0 for 16 s. Only its level is ridden:
# the galaxy is drawn in Outline, which plays much quieter (README), so it is brought up.
SOUND = [
    dict(take="d-orbit", mark="ad0", offset=0, at=0.0, seconds=16.0, gain=0.0, fade_in_ms=3.0, tail_ms=0.0, out_ms=3.0,
         # the stars' sparkle up in the gaps of the first bars, the moon a little down so the drop
         # is the loudest part, the galaxy (Outline) up, ending on the grid before the next star
         ride=[(0.55, 0.97, 8.0), (0.97, 2.25, -4.0), (2.28, 2.92, 8.0), (2.95, 4.33, 12.0), (7.0, 8.55, 3.5),
               (10.95, 12.33, 12.0)]),
]

DRUMS = None


def _bed():
    """The drums under it (made in mix_audio.py from sines and noise), section by section."""
    ev = [(0.0, "kick", -3.0), (0.0, "sub", -8.0)]                       # the hook: one hit ...
    ev += [(0.5, "clap", -8.0), (0.75, "open", -14.0), (0.75, "kick", -6.0), (0.75, "clap", -8.0),
           (0.875, "clap", -6.0)]                                          # ... and a pickup
    ev += [(1.0, "kick", -3.0), (2.0, "kick", -3.0), (2.0, "clap", -6.0)]       # half time
    ev += [(t, "hat", -16.0) for t in (1.25, 1.75, 2.25, 2.75)]
    ev += [(2.5, "clap", -10.0), (2.625, "clap", -8.0), (2.75, "clap", -6.0), (2.875, "clap", -4.0), (2.75, "kick", -6.0)]
    for b in range(4):                                                   # 3 - 5: four on the floor
        t = 3.0 + 0.5 * b
        ev += [(t, "kick", -3.0), (t + 0.25, "open", -17.0)]
        if b % 2:
            ev.append((t, "clap", -4.0))
    ev += [(4.75, "kick", -9.0), (5.25, "kick", -9.0)]                   # pushes into the build
    for b in range(3):                                                   # 5 - 6.5: the build
        ev.append((5.0 + 0.5 * b, "kick", -3.0))
    roll = [5.0 + 0.25 * i for i in range(3)] + [5.75 + 0.125 * i for i in range(6)]
    for i, t in enumerate(roll):
        ev.append((t, "clap", -12.0 + 9.0 * i / (len(roll) - 1)))
    # 6.5 - 7: nothing at all
    ev += [(7.0, "kick", 0.0), (7.0, "sub", -3.0), (7.0, "clap", -6.0), (7.0, "crash", -4.0)]   # the drop
    for b in range(16):                                                  # 7 - 15
        t = 7.0 + 0.5 * b
        if b:
            ev.append((t, "kick", -3.0))
            if b % 4 == 0:
                ev.append((t, "sub", -8.0))
        if b % 2:
            ev.append((t, "clap", -3.0))
        if t < 14.5:
            ev += [(t + 0.25, "open", -11.0), (t + 0.125, "hat", -20.0), (t + 0.375, "hat", -20.0)]
    ev += [(15.0, "kick", -3.0), (15.0, "sub", -8.0)]                    # one last hit, then ArtFreq alone
    return ev


DRUM_EVENTS = _bed()
# Voiced for phone speakers: more knock and click on the kick, the clap lower (under the drawing)
KICK_KNOCK, KICK_CLICK = 1.3, 1.5
CLAP_BAND = (350.0, 2500.0)
DRUM_EVENTS_GAIN = -10.0      # the drums as loud as ArtFreq (both about -21 LUFS alone)

SECTIONS = (("hook", 0, 1), ("build", 1, 5), ("riser", 5, 7), ("drop", 7, 11), ("ui", 11, 13), ("end", 13, 16))
STILLS = []
