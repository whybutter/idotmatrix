#!/usr/bin/env python3
"""Live audio-spectrum analyzer for the iDotMatrix panel.

Captures your computer's audio *output* (loopback — whatever is playing), runs
an FFT into 8 log-spaced bands, and POSTs the band levels to the integration's
webhook ~20x/second. The panel draws them as bars in real time.

    pip install soundcard numpy requests
    python spectrum_analyzer.py --webhook https://ha.example/api/webhook/idotmatrix_spectrum_c8a2bc

Loopback capture support (via the `soundcard` library):
  - Windows: WASAPI loopback — works out of the box on the default speaker.
  - Linux (PipeWire/PulseAudio): the default speaker's ".monitor" source.
  - macOS: has no OS loopback; install a virtual device (BlackHole) and either
    pick it with --device or route your output through it.

--device substring-matches a capture device name if the default isn't the one
playing the music. --list prints available devices and exits.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import requests
import soundcard as sc

SAMPLE_RATE = 44100
BLOCK = 2048          # samples per FFT (~46 ms) — the analysis window
BANDS = 8
FPS = 20              # POSTs per second
# Log-spaced band edges across the audible-ish range the panel can show.
EDGES = np.geomspace(60, 16000, BANDS + 1)


def pick_loopback(device_hint: str | None):
    """Return a soundcard recorder for the system output (loopback)."""
    if device_hint:
        for mic in sc.all_microphones(include_loopback=True):
            if device_hint.lower() in mic.name.lower():
                return mic
        sys.exit(f"No capture device matching {device_hint!r}. Try --list.")
    # Default: the loopback of the default speaker.
    try:
        return sc.get_microphone(
            sc.default_speaker().name, include_loopback=True
        )
    except Exception:  # noqa: BLE001
        loops = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
        if loops:
            return loops[0]
        sys.exit("No loopback device found. On macOS install BlackHole and use --device.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--webhook", help="Full webhook URL from the integration")
    ap.add_argument("--device", help="Substring of the capture device to use")
    ap.add_argument("--list", action="store_true", help="List devices and exit")
    ap.add_argument("--gain", type=float, default=1.0, help="Level multiplier")
    ap.add_argument("--floor", type=float, default=-60.0, help="Noise floor (dB)")
    args = ap.parse_args()

    if args.list:
        for m in sc.all_microphones(include_loopback=True):
            print(("loopback" if m.isloopback else "input "), m.name)
        return
    if not args.webhook:
        ap.error("--webhook is required (or use --list)")

    mic = pick_loopback(args.device)
    print(f"Capturing: {mic.name}\nPosting to: {args.webhook}\nCtrl-C to stop.")

    window = np.hanning(BLOCK)
    freqs = np.fft.rfftfreq(BLOCK, 1 / SAMPLE_RATE)
    band_idx = [
        np.where((freqs >= EDGES[b]) & (freqs < EDGES[b + 1]))[0] for b in range(BANDS)
    ]
    smooth = np.zeros(BANDS)
    session = requests.Session()
    period = 1.0 / FPS

    with mic.recorder(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK) as rec:
        while True:
            t0 = time.monotonic()
            data = rec.record(numframes=BLOCK)[:, 0]
            spec = np.abs(np.fft.rfft(data * window))
            levels = np.zeros(BANDS)
            for b, idx in enumerate(band_idx):
                if len(idx):
                    mag = float(np.mean(spec[idx]))
                    db = 20 * np.log10(mag + 1e-9)
                    levels[b] = np.clip((db - args.floor) / (-args.floor), 0, 1)
            levels = np.clip(levels * args.gain, 0, 1)
            # Asymmetric smoothing: snap up, ease down — reads as musical.
            smooth = np.where(levels > smooth, levels, smooth * 0.6 + levels * 0.4)
            try:
                session.post(args.webhook, json={"levels": smooth.round(3).tolist()},
                             timeout=0.5)
            except requests.RequestException:
                pass
            dt = time.monotonic() - t0
            if dt < period:
                time.sleep(period - dt)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
