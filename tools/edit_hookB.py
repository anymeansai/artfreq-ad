"""The edit of ad-artfreq-hookB ("Hidden in this beat"), an Instagram Reel: which pictures of
which take go where, and how each is framed. Read by cut_shots.py and mix_audio.py
(`python3 tools/cut_shots.py <takes> edit_hookB`), mirrored by hand in hookB/index.html.

All four takes (tools/adreel: b-type, b-hook, b-drop, b-logo) are ArtFreq FX on the same loop on
one clock: ad time t is take picture "ad0" + 30 t in every take, with the loop at the same place.
So every shot and every cut of sound here is `offset` = 30 t pictures after mark "ad0", and a cut
from one take to another keeps the music in step. Cuts fall on bar lines (every 2 s at 120 BPM).
"""

PROJECT = "hookB"
FPS = 30
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
AD_SECONDS = 16.0      # 8 bars: the loop ends where it began, so the Reel loops in time
BPM = 120.0

OUT_W = 1080
CARD_W, CARD_H = 1040, 900
FX_CARD_W, FX_CARD_H = 1080, 660   # ArtFreq FX's whole window, edge to edge (1.5 px a point)


def at(t):
    """The take picture (after mark "ad0") and the ad picture for ad time t."""
    return round(t * FPS)


SHOTS = [
    # 0-2 s   the hook: the loop's live view, the name being carved into it
    dict(name="hook-live",   take="b-hook", frame="tall", seconds=2.0, mark="ad0", offset=at(0),  frames=at(2),   at=at(0)),
    # 2-4 s   the plug-in it happens in
    dict(name="hook-window", take="b-hook", frame="fx-card",           mark="ad0", offset=at(2),  frames=at(2),   at=at(2)),
    # 4-6 s   typing the name
    dict(name="type-ui",     take="b-type", frame="fx-card",           mark="ad0", offset=at(4),  frames=at(2),   at=at(4)),
    # 6-8 s   the name, carved as the loop plays (the same drawing as typed)
    dict(name="play-live",   take="b-hook", frame="tall", seconds=2.0, mark="ad0", offset=at(6),  frames=at(2),   at=at(6)),
    # 8-10 s  a logo dropped in and dragged out
    dict(name="drop-ui",     take="b-drop", frame="fx-card",           mark="ad0", offset=at(8),  frames=at(2),   at=at(8)),
    # 10-12 s the logo, carved
    dict(name="logo-live",   take="b-logo", frame="tall", seconds=2.0, mark="ad0", offset=at(10), frames=at(2),   at=at(10)),
    # 12-16 s "Hide yours." and the end card, over the name carved again
    dict(name="end-live",    take="b-hook", frame="tall", seconds=2.0, mark="ad0", offset=at(12), frames=at(4),   at=at(12)),
]

STILLS = []

# The sound: the loop as it came out of ArtFreq FX in the take that is on screen. Each cut runs
# 6 ms into the next and fades across it (the same music on both sides, so its level holds).
_X = dict(gain=0.0, tail_ms=6.0)
SOUND = [
    dict(take="b-hook", mark="ad0", offset=at(0),  at=0.0,  seconds=4.0, fade_in_ms=0.0, **_X),
    dict(take="b-type", mark="ad0", offset=at(4),  at=4.0,  seconds=2.0, fade_in_ms=6.0, **_X),
    dict(take="b-hook", mark="ad0", offset=at(6),  at=6.0,  seconds=2.0, fade_in_ms=6.0, **_X),
    dict(take="b-drop", mark="ad0", offset=at(8),  at=8.0,  seconds=2.0, fade_in_ms=6.0, **_X),
    dict(take="b-logo", mark="ad0", offset=at(10), at=10.0, seconds=2.0, fade_in_ms=6.0, **_X),
    # the last: no run-on, and 3 ms out at the very end (the Reel loops back to the first beat)
    dict(take="b-hook", mark="ad0", offset=at(12), at=12.0, seconds=4.0, fade_in_ms=6.0, gain=0.0, tail_ms=0.0, out_ms=3.0),
]

DRUMS = None   # the beat is the loop itself

SECTIONS = (("hook", 0, 4), ("how", 4, 8), ("logo", 8, 12), ("close", 12, 16))
