# artfreq-ad

One paid ad for ArtFreq (AnyMeans Audio): `ad-artfreq-hookA.mp4`, vertical 1080 x 1920, 28 s, for
Reels and TikTok. Composed with [HyperFrames](https://www.npmjs.com/package/hyperframes).

Every picture of the plug-in in it, and every sound except one drum loop, is the plug-in's own
output: nothing of the GUI or of a spectrogram is drawn, mocked up or generated.

## What is in the ad

| Time | Section | On screen | Sound |
| --- | --- | --- | --- |
| 0 - 3 s | Hook | "This sound is a picture." over ArtFreq's live view writing HEAR / THIS, then the window | those words, played by ArtFreq |
| 3 - 10 s | Proof | "Type it. Draw it. Hear it.": a word typed, a star brushed, a picture dropped, each cut to its live view | each drawing, played by ArtFreq, over a drum loop |
| 10 - 20 s | Depth | "Or carve it into audio you already have.": ArtFreq FX on a loop: as it is, then Carve, then Carve + Draw | the loop through ArtFreq FX |
| 20 - 25 s | Offer | "ArtFreq $29 · Pro $39", "VST3 · Mac + Windows" | the loop carries on |
| 25 - 28 s | End card | AnyMeans Audio, "Draw in sound.", anymeansaudio.com | the hook's words once more |

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

- Drawings are made the way a user makes them: typing into the text box, dragging the brush over
  the canvas, dropping a PNG on the canvas.
- Every take runs with Repeat on. A live shot in the ad starts where the second pass starts: the
  first pass's picture is whole in the live view, and the sound of the same drawing starts on
  the cut.
- ArtFreq FX's "dry" stretches are the loop passing through the plug-in untouched: its output
  there equals its input, sample for sample (delayed by the plug-in's latency).
- The loop ArtFreq FX works on is the plug-in repository's own test song (`makeSong` in
  `tools/DemoReel.cpp`, a synthetic 120 BPM loop), not a record.
- Nothing of the plug-in is copied into this repository. `AdReel.cpp` includes `DemoReel.cpp`
  where it lies in the checkout, for the test song, the sunset picture and its helpers.

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
- The drum loop under the proof is made in `mix_audio.py` from sines and noise.
- The mix is levelled to -14 LUFS with peaks under -1 dBTP.

### 3. The film

```sh
npm install
npx hyperframes lint
npx hyperframes check --no-cache
npm run render                       # ad-artfreq-hookA.mp4
```

`index.html` holds the shots and the sound; `compositions/` holds the words of each section.
Fonts (Inter, DM Mono) and the AnyMeans lockup are the website's own files, in `assets/`.

## Licences

ArtFreq is AGPL-3.0; `tools/adreel` builds on its sources. Inter and DM Mono are under the SIL
Open Font License (`assets/fonts/OFL-*.txt`).
