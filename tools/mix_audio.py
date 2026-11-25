#!/usr/bin/env python3
"""Mixes the ad's sound: assets/audio/ad-mix.wav (48 kHz, 24-bit stereo, 28 s).

    python3 tools/mix_audio.py <takes-dir>

What is in it:

  - The plug-in's own output, cut from the takes on the same pictures as the shots that show it
    (edit.SOUND). It is only cut, levelled (one gain per cut) and given a few milliseconds of
    fade at each end so a cut does not click. No EQ, no reverb, no pitch or time change.
  - One drum loop under the proof (edit.DRUMS), made here from sines and noise: a kick on every
    beat, a clap on 2 and 4, hats on the off-beats. 120 BPM, bars on even seconds, so it hands
    over to the loop ArtFreq FX plays from 10 s (the plug-in repo's own test song, same tempo).
    It is voiced to be heard on a phone: the kick has a knock and a click above its thump.
  - On the sum: a peak limiter (5 ms look-ahead) and a gain to the loudness target.

Needs numpy and ffmpeg (to read the takes' float WAVs, measure loudness and write the file).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import edit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "audio" / "ad-mix.wav"
SR = edit.SAMPLE_RATE
TARGET_LUFS = -14.0      # where Reels and TikTok level to
CEILING_DB = -1.5        # sample peak; the true peak is checked after


def db(x):
    return 10.0 ** (x / 20.0)


def read(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def write(path, audio):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f64le", "-ac", "2", "-ar", str(SR), "-i", "-",
                    "-c:a", "pcm_s24le", str(path)], input=audio.astype(np.float64).tobytes(), check=True)


def loudness(audio, start=0.0, end=None):
    """Integrated loudness (LUFS) and true peak (dBTP) of a stretch, by ffmpeg's ebur128."""
    a = audio[int(start * SR): None if end is None else int(end * SR)]
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f64le", "-ac", "2", "-ar", str(SR), "-i", "-",
                          "-af", "ebur128=peak=true", "-f", "null", "-"],
                         input=a.astype(np.float64).tobytes(), capture_output=True).stderr.decode()
    summary = out[out.rindex("Summary:"):]
    return (float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1)),
            float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1)))


def fade(clip, in_ms=3.0, out_ms=8.0):
    n_in, n_out = int(in_ms * SR / 1000), int(out_ms * SR / 1000)
    clip = clip.copy()
    clip[:n_in] *= np.linspace(0.0, 1.0, n_in)[:, None]
    clip[-n_out:] *= np.linspace(1.0, 0.0, n_out)[:, None]
    return clip


# ---------------------------------------------------------------------------------------------
# The drum loop: sines and noise, nothing sampled.

def shaped_noise(rng, n, low, high):
    """White noise kept between low and high Hz (a soft-edged band, done in the spectrum)."""
    spectrum = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    edge = lambda x, at, width: 1.0 / (1.0 + np.exp(-(x - at) / width))
    spectrum *= edge(f, low, low * 0.08) * (1.0 - edge(f, high, high * 0.08))
    out = np.fft.irfft(spectrum, n)
    return out / np.max(np.abs(out))


def kick():
    t = np.arange(int(0.32 * SR)) / SR
    hz = 55.0 + 160.0 * np.exp(-t / 0.030)                      # the pitch drops into the thump
    body = np.sin(2.0 * np.pi * np.cumsum(hz) / SR) * np.exp(-t / 0.13)
    knock_hz = 220.0 + 500.0 * np.exp(-t / 0.012)               # the part a phone speaker plays
    knock = np.sin(2.0 * np.pi * np.cumsum(knock_hz) / SR) * np.exp(-t / 0.040) * 0.9
    click = np.sin(2.0 * np.pi * 1800.0 * t) * np.exp(-t / 0.008)
    out = np.tanh(1.6 * (body + knock + click)) * np.minimum(1.0, t / 0.001)
    out[-480:] *= np.linspace(1.0, 0.0, 480)
    return out


def clap(rng):
    n = int(0.40 * SR)
    t = np.arange(n) / SR
    envelope = np.zeros(n)
    for start, level in ((0.0, 0.7), (0.011, 0.8), (0.023, 1.0)):   # three hands, then the tail
        later = t >= start
        envelope[later] = np.maximum(envelope[later], level * np.exp(-(t[later] - start) / 0.007))
    tail = t >= 0.023
    envelope[tail] = np.maximum(envelope[tail], 0.8 * np.exp(-(t[tail] - 0.023) / 0.110))
    return shaped_noise(rng, n, 700.0, 6000.0) * envelope


def hat(rng, decay):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    return shaped_noise(rng, n, 5000.0, 14000.0) * np.exp(-t / decay) * np.minimum(1.0, t / 0.0005)


def drum_loop(start, end):
    """Mono, on the ad's clock: beats every half second, bars on even seconds."""
    rng = np.random.default_rng(20261124)
    total = int(edit.AD_SECONDS * SR)
    out = np.zeros(total)
    beat = 60.0 / edit.BPM
    k, c = kick(), clap(rng)
    closed, open_hat = hat(rng, 0.030), hat(rng, 0.070)

    def add(sound, at, level):
        i = int(round(at * SR))
        j = min(total, i + len(sound), int(round(end * SR)))
        if at >= start and j > i:
            piece = sound[: j - i] * level
            if j - i < len(sound):
                piece = piece.copy()
                piece[-min(240, j - i):] *= np.linspace(1.0, 0.0, min(240, j - i))
            out[i:j] += piece

    n_beats = int(round(edit.AD_SECONDS / beat))
    for b in range(n_beats):
        at = b * beat
        add(k, at, db(-5.0))
        if b % 4 in (1, 3):                      # 2 and 4
            add(c, at, db(0.0))
        add(open_hat, at + beat / 2, db(-6.0))  # the off-beat
        for sixteenth in (0.25, 0.75):
            add(closed, at + beat * sixteenth, db(-9.0))
    return out


# ---------------------------------------------------------------------------------------------

def limit(audio, ceiling):
    """A peak limiter with 5 ms look-ahead: the gain falls before a peak and recovers in 80 ms."""
    look = int(0.005 * SR)
    peak = np.max(np.abs(audio), axis=1)
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-12))
    # the smallest gain needed over the next `look` samples
    padded = np.concatenate([need, np.ones(look)])
    windows = np.lib.stride_tricks.sliding_window_view(padded, look + 1)
    ahead = windows.min(axis=1)
    gain = np.empty_like(ahead)
    g, release = 1.0, np.exp(-1.0 / (0.080 * SR))
    for i, target in enumerate(ahead):
        g = target if target < g else 1.0 - (1.0 - g) * release if g < 1.0 else 1.0
        g = min(g, target)
        gain[i] = g
    # smooth the attack over the look-ahead so the gain never jumps
    kernel = np.hanning(look * 2 + 1)
    kernel /= kernel.sum()
    smooth = np.minimum(gain, np.convolve(np.pad(gain, look, mode="edge"), kernel, mode="valid"))
    return audio * smooth[:, None], float(20 * np.log10(smooth.min()))


def main():
    takes = Path(sys.argv[1])
    total = int(edit.AD_SECONDS * SR)
    mix = np.zeros((total, 2))

    for cut in edit.SOUND:
        meta = json.loads((takes / f"{cut['take']}.json").read_text())
        audio = read(takes / f"{cut['take']}.wav")
        first = (meta["marks"][cut["mark"]] + cut["offset"]) * edit.SAMPLES_PER_FRAME
        n = int(round(cut["seconds"] * SR))
        clip = fade(audio[first:first + n], in_ms=cut.get("fade_in_ms", 3.0)) * db(cut["gain"])
        at = int(round(cut["at"] * SR))
        n = min(len(clip), total - at)
        mix[at:at + n] += clip[:n]
        print(f"{cut['take']:8s} take samples {first}..{first + n} -> {cut['at']:5.2f} s, {cut['gain']:+.1f} dB, "
              f"peak {20 * np.log10(np.max(np.abs(clip)) + 1e-12):+.1f} dBFS")

    drums = drum_loop(edit.DRUMS["start"], edit.DRUMS["end"]) * db(edit.DRUMS["gain"])
    mix += drums[:, None]

    # Level to the target, then catch the peaks; twice, as limiting lowers the loudness a little.
    for _ in range(3):
        lufs, _ = loudness(mix)
        mix *= db(TARGET_LUFS - lufs)
        mix, reduction = limit(mix, db(CEILING_DB))

    lufs, true_peak = loudness(mix)
    print(f"whole: {lufs:.1f} LUFS, true peak {true_peak:.1f} dBTP, limiter at most {reduction:.1f} dB")
    for name, a, b in (("hook", 0, 3), ("proof", 3, 10), ("depth", 10, 20), ("offer", 20, 25), ("end", 25, 28)):
        l, p = loudness(mix, a, b)
        print(f"  {name:6s} {a:2d}-{b:2d} s: {l:6.1f} LUFS, peak {p:5.1f} dBTP")

    write(OUT, mix)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(mix) / SR:.2f} s)")


if __name__ == "__main__":
    main()
