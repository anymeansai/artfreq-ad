# artfreq-ad

One paid ad for ArtFreq (AnyMeans Audio): `ad-artfreq-hookA.mp4`, vertical 1080 x 1920, 28 s, for
Reels and TikTok. Composed with [HyperFrames](https://www.npmjs.com/package/hyperframes).

Every picture of the plug-in in it, and every sound except one drum loop, is the plug-in's own
output: nothing of the GUI or of a spectrogram is drawn, mocked up or generated.

## What is in the ad

| Time | Section | On screen | Sound |
| --- | --- | --- | --- |
| 0 - 3 s | Hook | "This sound is a picture." over ArtFreq's live view: HEAR / THIS, whole on the first picture and written again as it sounds; then the window | those words, played by ArtFreq |
| 3 - 10 s | Proof | "Type it. Draw it. Hear it.": ART / FREQ typed, a star brushed, a picture dropped and dragged out, each cut to its live view | each drawing, played by ArtFreq, over a drum loop |
| 10 - 20 s | Depth | "Or carve it into audio you already have.": ArtFreq FX on a loop. Each 4 s pass: the loop as it is, then YOUR / NAME: Carve + Draw, then Carve, then Carve + Draw | the loop through ArtFreq FX |
| 20 - 25 s | Product | "ArtFreq", "VST3 · Mac + Windows" (and a small "ArtFreq FX comes with ArtFreq Pro"); no prices | the loop carries on |
| 25 - 28 s | End card | AnyMeans Audio, "ArtFreq", "Draw in sound.", anymeansaudio.com | the loop ends its phrase, then the hook's words once more |

Two small labels are not in the brief's copy: the row "Dry / Carve + Draw / Carve" in the depth
section (the one that is true of the sound at that moment is lit) and "ArtFreq FX comes with
ArtFreq Pro" at 20 - 25 s. The ad shows no prices; the one amber accent is the website on the end card.

## How it is made

```
ArtFreq plug-in checkout (read only)
        |  tools/adreel            films the real editor on the real processor
        v
takes: <take>.mkv (every picture of the window, lossless), .wav (the plug-in's output), .json
        |  tools/cut_shots.py      crops the takes into the shots      -> assets/video, assets/img
        |  tools/mix_audio.py      cuts the takes' sound, adds the drums -> assets/audio/ad-mix.wav
        v
index.html + compositions/*.html   the HyperFrames film: shots, words, sound
        |  hyperframes render
        v
ad-artfreq-hookA.mp4
```

`tools/edit.py` holds the edit's numbers (which pictures of which take go where) for both scripts.

### 1. Filming the plug-in (`tools/adreel`)

`ArtFreqAdReel` compiles the plug-in's own sources from a checkout of the plug-in and opens its
real editor on its real processor, as the plug-in's `tools/DemoReel.cpp` does for the clips on
anymeansaudio.com. It plays the "DAW" itself (48 kHz, 30 pictures a second, 1600 samples of sound
per picture) and after each picture's sound takes a snapshot of the window. So a take's picture
`i` always belongs to its samples `[1600 i, 1600 (i + 1))`, and what the live view shows is what
was just heard.

- Drawings are made through the plug-in's own interface: text typed into the text box, the brush
  dragged over the canvas, a PNG dropped on the canvas and dragged out by its corner handles.
  The input is scripted (keys and mouse events sent to the window), so it is faster and
  steadier than a hand; it is not a screen recording of someone using it.
- Every take runs with Repeat on. A live shot in the ad starts where a later pass starts: the
  pass before is whole in the live view, and the sound of the same drawing starts on the cut.
  So the first picture of such a shot was drawn by the pass just before the one being heard
  (the same drawing, the same sound).
- ArtFreq FX's "dry" stretches are the rest at the start of each pass of the drawing: the loop
  passes through the plug-in untouched there, its output equal to its input sample for sample
  (delayed by the plug-in's latency). Mode is changed on the first picture of a pass, as a
  host's automation would change it.
- The loop ArtFreq FX works on is the plug-in repository's own test song (`makeSong` in
  `tools/DemoReel.cpp`, a synthetic 120 BPM loop), not a record.
- The plug-in's sources stay in its own checkout. `AdReel.cpp` includes `DemoReel.cpp` where
  it lies there, for the test song, the sunset picture and its helpers; the way a take is
  filmed follows that file, and a few helper lines are adapted from it and from
  `tools/Snapshot.cpp`.
- The still of ArtFreq's window in the offer shows the drawing a new instance opens with (the
  word "ArtFreq"), drawn with the view settings below.

Settings that differ from a fresh instance, all of them the plug-in's own controls:

| Setting | Here | Default | What it changes |
| --- | --- | --- | --- |
| Settings > FFT | 4096 | 8192 | how the live view and canvas draw: sharper in time for short passes |
| Settings > Levels, brightest | -30 dBFS (ArtFreq), -20 dBFS (ArtFreq FX) | 0 dBFS | the colours of the picture only: brighter, as in the demo clips on the site |
| Density | 512 lines | 256 | solid letters |
| Length, Repeat, Tempo | 1 bar (ArtFreq), 2 bars (ArtFreq FX), Repeat on, host at 120 or 160 BPM | 4 bars, off | how long a pass is |

Build and run (Linux; needs the plug-in's build dependencies, ffmpeg and a virtual display):

```sh
git clone --depth 1 --branch 8.0.15 https://github.com/juce-framework/JUCE.git <juce>
cmake -S tools/adreel -B <build> -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DADREEL_ARTFREQ_DIR=<ArtFreq-plug-in checkout> -DADREEL_JUCE_DIR=<juce>
cmake --build <build> --target ArtFreqAdReel
xvfb-run -a -s "-screen 0 2400x1600x24" <build>/ArtFreqAdReel_artefacts/Release/ArtFreqAdReel <takes>
```

The takes are large (about 300 MB) and are not kept in this repository; the shots cut from them are.

### 2. Shots and sound

```sh
python3 tools/cut_shots.py <takes>   # assets/video/*.mp4, assets/img/artfreq-window.png
python3 tools/mix_audio.py <takes>   # assets/audio/ad-mix.wav  (needs numpy)
```

- A shot is a crop of a take, scaled down with Lanczos to the size it is shown at. Nothing is
  retimed, recoloured or drawn on.
- The sound of the plug-in is only cut (on the same pictures as the shots), levelled and given
  a few milliseconds of fade at each cut. No EQ, reverb, pitch or time change.
- The drum loop under the proof is made in `mix_audio.py` from sines and noise (no samples).
- The mix is levelled to -14 LUFS with peaks under -1 dBTP.

### 3. The film

```sh
npm install
npx hyperframes lint
npx hyperframes check --no-cache
npm run render                       # ad-artfreq-hookA.mp4
```

The render carries HyperFrames' container tags; the file in this repository has them removed
without re-encoding: `ffmpeg -i in.mp4 -map 0 -map_metadata -1 -c copy -movflags +faststart out.mp4`.

`index.html` holds the shots and the sound; `compositions/` holds the words of each section.
Fonts (Inter, DM Mono) and the AnyMeans lockup are the website's own files, in `assets/`.

## Licences

ArtFreq is AGPL-3.0; `tools/adreel` builds on its sources. Inter and DM Mono are under the SIL
Open Font License (`assets/fonts/OFL-*.txt`).
