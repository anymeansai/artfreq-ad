"""The edit of ad-artfreq-hookA: which pictures of which take go where, and how each is framed.

One place for the numbers, read by cut_shots.py (the picture) and mix_audio.py (the sound), and
mirrored by hand in index.html (data-start / data-duration of each <video>).

A take is what tools/adreel films from the real plug-in: <take>.mkv (every picture of the whole
window, lossless), <take>.wav (the plug-in's own output: picture i <-> samples [1600 i, 1600 (i+1)))
and <take>.json (marks: the picture at which something happens; rects: where the parts of the
window are, in pixels of the picture). A shot never retimes a take: one picture of the take per
picture of the ad, so the sound cut from the same pictures stays in step with what is seen.
"""

FPS = 30
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS   # 1600
AD_SECONDS = 28.0
BPM = 120.0                               # the ad's grid: a beat every 15 pictures, bars on even seconds

# How a shot is framed from the window.
#   tall:  the right end of the live view's plot ("now" and the last `seconds`), nothing else:
#          the live view scrolls, so this is where the drawing appears as it sounds. Every tall
#          shot shows 2 s, so they all move at the same speed and share one scale.
#   card:  the window from its left edge, `points` wide (the canvas side of ArtFreq), or whole.
OUT_W = 1080
TALL_H = 1306            # the instrument's plot (aspect 1.654) with 2 s across 1080 px
CARD_W, CARD_H = 1040, 900   # ArtFreq's window at 1.25 px per point, 832 points of its 1120 wide
FX_CARD_W, FX_CARD_H = 1008, 616   # ArtFreq FX's whole window (720 x 440 points) at 1.4 px per point

# name, take, framing, first picture (a mark of the take + offset), pictures, ad picture it starts at
SHOTS = [
    # Every take plays its drawing round and round (Repeat). A live shot starts where the second
    # pass starts: the first pass's picture is whole in the live view, and the sound of the same
    # drawing starts on the cut. As it plays, that picture moves out and the new one is written.
    #
    # 0-3 s  HOOK: the words, whole, on the first picture; then the window.
    dict(name="hook-tall",    take="hook",    frame="tall", seconds=2.0, mark="play", offset=60,  frames=30,  at=0),
    dict(name="hook-card",    take="hook",    frame="card",              mark="play", offset=90,  frames=60,  at=30),
    # 3-10 s PROOF: type / draw / drop, each cut to its sound on a bar line.
    dict(name="type-card",    take="type",    frame="card",              mark="typing", offset=0,  frames=30, at=90),
    dict(name="type-tall",    take="type",    frame="tall", seconds=2.0, mark="play", offset=45,  frames=45,  at=120),
    dict(name="draw-card",    take="draw",    frame="card",              mark="stroke", offset=0, frames=15,  at=165),
    dict(name="draw-tall",    take="draw",    frame="tall", seconds=2.0, mark="play", offset=45,  frames=45,  at=180),
    dict(name="picture-card", take="picture", frame="card",              mark="drop", offset=-5,  frames=15,  at=225),
    dict(name="picture-tall", take="picture", frame="tall", seconds=2.0, mark="play", offset=60,  frames=60,  at=240),
    # 10-25 s DEPTH and OFFER: one unbroken take of ArtFreq FX on the loop (the window), with two
    #        closer looks at the words while they are carved (the same pictures, cropped).
    dict(name="fx-card",      take="fx",      frame="fx-card",           mark="carve", offset=0,   frames=450, at=300),
    dict(name="fx-zoom-1",    take="fx",      frame="fx-zoom", rects="carve/",      seconds=2.76, mark="carve", offset=60,  frames=60, at=360),
    dict(name="fx-zoom-2",    take="fx",      frame="fx-zoom", rects="carve-draw/", seconds=2.76, mark="carve", offset=180, frames=60, at=480),
]

# Stills: name, take, picture, framing
STILLS = [
    dict(name="artfreq-window", take="still", index=2, frame="window", width=1000),
]

# The sound: which take's output is heard when (ad seconds), from which of its pictures.
# Everything here is the plug-in's own output, cut on picture boundaries; gains in dB.
SOUND = [
    dict(take="hook",    mark="play",  offset=60, at=0.0,  seconds=3.0,  gain=5.5),             # pass 2, half of pass 3
    dict(take="type",    mark="play",  offset=45, at=4.0,  seconds=1.5,  gain=6.5),             # pass 2 (1.5 s at 160 BPM)
    dict(take="draw",    mark="play",  offset=45, at=6.0,  seconds=1.5,  gain=6.0),
    dict(take="picture", mark="play",  offset=60, at=8.0,  seconds=2.0,  gain=4.5),
    dict(take="fx",      mark="carve", offset=0,  at=10.0, seconds=15.0, gain=3.2),  # the loop through ArtFreq FX
    dict(take="hook",    mark="play",  offset=60, at=25.0, seconds=2.0,  gain=4.5),              # the hook's words once more, whole
]

# The drum loop under the proof (3-10 s): made in mix_audio.py, not a recording of anything.
DRUMS = dict(start=3.0, end=10.0, gain=-3.0)
