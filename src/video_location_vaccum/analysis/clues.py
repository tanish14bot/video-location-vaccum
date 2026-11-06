"""Non-Doppler acoustic clues.

These are *leads*, not location proofs: mains hum suggests a grid region,
reverb suggests an environment, tonal peaks suggest machinery or aircraft.
Every result carries a confidence label.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import signal


@dataclass
class HumResult:
    hz_50_db: float
    hz_60_db: float
    harmonics_50_db: float
    harmonics_60_db: float
    hint: str


@dataclass
class ClueReport:
    duration_s: float
    sample_rate: int
    channels: int
    noise_floor_db: float
    dynamic_range_db: float
    clipping_fraction: float
    hum: HumResult
    tonal_peaks_hz: list[float] = field(default_factory=list)
    reverb_rt60_s: float | None = None
    reverb_confidence: str = "low"
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _band_db(freqs: NDArray[np.float64], psd: NDArray[np.float64], f0: float, half: float = 1.5) -> float:
    band = psd[(freqs >= f0 - half) & (freqs <= f0 + half)]
    if band.size == 0:
        return -np.inf
    return float(10.0 * np.log10(np.max(band) + 1e-20))


def hum_analysis(y: NDArray[np.float64], sr: int) -> HumResult:
    freqs, psd = signal.welch(y, fs=sr, nperseg=min(16384, max(2048, y.size // 4)))

    # Local baseline around each mains frequency, excluding the peak itself.
    def local_floor(f0: float) -> float:
        lo, hi = f0 * 0.9, f0 * 1.1
        band = psd[(freqs >= lo) & (freqs <= hi)]
        return float(np.median(band) + 1e-20) if band.size else 1e-20

    def ratio(f0: float) -> float:
        peak = 10.0 ** (_band_db(freqs, psd, f0) / 10.0)
        return float(10.0 * np.log10(peak / local_floor(f0) + 1e-20))

    def harmonics(f0: float) -> float:
        vals = [ratio(f0 * k) for k in (2.0, 3.0)]
        return float(np.mean(vals))

    h50, h60 = ratio(50.0), ratio(60.0)
    k50, k60 = harmonics(50.0), harmonics(60.0)
    if max(h50, k50) > max(h60, k60) + 6.0:
        hint = "50 Hz grid (Europe/Asia/Africa/parts of South America)"
    elif max(h60, k60) > max(h50, k50) + 6.0:
        hint = "60 Hz grid (Americas/parts of Asia)"
    else:
        hint = "no clear mains-hum region hint"
    return HumResult(h50, h60, k50, k60, hint)


def reverb_estimate(y: NDArray[np.float64], sr: int) -> tuple[float | None, str]:
    """Very rough Schroeder-style decay estimate from the loudest transients.

    This is a lead, not a measurement: music, speech, and compression all bias
    it. Use an impulse response for real RT60 work.
    """
    if y.size < sr:
        return None, "low"
    envelope = np.abs(signal.hilbert(y))
    # Smooth to a ~10 ms envelope.
    win = max(1, int(0.01 * sr))
    env = np.convolve(envelope, np.ones(win) / win, mode="same")
    peaks, _ = signal.find_peaks(env, distance=int(0.2 * sr), height=np.percentile(env, 95))
    estimates: list[float] = []
    for p in peaks[:20]:
        segment = env[p : min(env.size, p + int(1.2 * sr))]
        if segment.size < int(0.2 * sr):
            continue
        db = 20.0 * np.log10(segment / (segment[0] + 1e-12) + 1e-12)
        below = np.where(db < -20.0)[0]
        if below.size == 0:
            continue
        t20 = below[0] / sr
        if 0.02 < t20 < 1.0:
            estimates.append(3.0 * t20)
    if not estimates:
        return None, "low"
    return float(np.median(estimates)), "low"


def tonal_peaks(
    y: NDArray[np.float64], sr: int, *, fmin: float = 40.0, fmax: float = 2000.0, n: int = 10
) -> list[float]:
    freqs, psd = signal.welch(y, fs=sr, nperseg=min(8192, max(2048, y.size // 4)))
    mask = (freqs >= fmin) & (freqs <= fmax)
    f = freqs[mask]
    p = 10.0 * np.log10(psd[mask] + 1e-20)
    peaks, _ = signal.find_peaks(p, distance=5, prominence=6.0)
    if peaks.size == 0:
        return []
    order = np.argsort(p[peaks])[::-1][:n]
    return [float(f[i]) for i in peaks[order]]


def audio_container_metadata(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"error": "ffprobe not installed"}
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return json.loads(out.stdout)
    except Exception as exc:
        return {"error": str(exc)}


def analyze_audio(path: Path, *, sr: int = 8000) -> ClueReport:
    from ..audio.io import load_audio

    y, actual_sr = load_audio(path, sr=sr)
    if y.ndim > 1:
        y = y.mean(axis=1)
    duration = float(y.size / actual_sr)
    noise = float(np.percentile(np.abs(y), 20) + 1e-12)
    peak = float(np.max(np.abs(y)) + 1e-12)
    clipping = float(np.mean(np.abs(y) >= 0.999))
    rt60, rt_conf = reverb_estimate(y, actual_sr)
    report = ClueReport(
        duration_s=duration,
        sample_rate=actual_sr,
        channels=1,
        noise_floor_db=float(20 * np.log10(noise)),
        dynamic_range_db=float(20 * np.log10(peak / max(noise, 1e-9))),
        clipping_fraction=clipping,
        hum=hum_analysis(y, actual_sr),
        tonal_peaks_hz=tonal_peaks(y, actual_sr),
        reverb_rt60_s=rt60,
        reverb_confidence=rt_conf,
        metadata=audio_container_metadata(path),
    )
    report.notes.append("Mains hum and reverb are leads, not location proofs.")
    report.notes.append("Speech language, wildlife, bells, and vehicles require separate models.")
    return report
