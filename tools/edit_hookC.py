"""The edit of ad-artfreq-hookC ("This beat is talking"), an Instagram Reel. One take (c-wf) of
ArtFreq FX in Carve + Draw on the loop: its live view, turned a quarter right so time runs up the
screen, then the whole window. Read by cut_shots.py / mix_audio.py (`... edit_hookC`).
"""

PROJECT = "hookC"
FPS = 30
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
AD_SECONDS = 20.0      # 10 bars: ends where it began in the loop, so the Reel loops in time
BPM = 120.0

OUT_W = 1080
FX_CARD_W, FX_CARD_H = 1080, 660


def at(t):
    return round(t * FPS)


# The live view between 268 Hz and 13.4 kHz (the words' 300 Hz - 12 kHz, centred) and its newest
# 2.316 s, as 1920 x 1080, shown turned a quarter right: time rising up the screen.
F_LO, F_HI = 268.4, 13416.0

SHOTS = [
    # 2.316 s across 1920 px: 829 px a second, as the words were laid out (make_strips_hookC.py)
    dict(name="wf",  take="c-wf", frame="plotcrop", f_lo=F_LO, f_hi=F_HI, seconds=2.316, out=(1920, 1080), mark="ad0", offset=at(0), frames=at(15.9), at=at(0)),
    dict(name="win", take="c-wf", frame="fx-card",                                          mark="ad0", offset=at(15), frames=at(5),    at=at(15)),
]

STILLS = []

SOUND = [
    dict(take="c-wf", mark="ad0", offset=at(0), at=0.0, seconds=20.0, gain=0.0, fade_in_ms=0.0, tail_ms=0.0, out_ms=3.0),
]

DRUMS = None

SECTIONS = (("words", 0, 15), ("reveal", 15, 20))
