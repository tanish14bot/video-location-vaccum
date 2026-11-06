"""Consumer-media viability audit.

Answers one question before any search: is there enough here for the acoustic
method, or should this be handled visually? It does not claim a location.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import signal

from ..audio.detect import detect_ridges
from ..audio.io import load_audio
from ..audio.spectrogram import compute_spectrogram


@dataclass
class ViabilityReport:
    duration_s: float
    sample_rate: int
    codec: str | None
    bitrate_kbps: float | None
    clipping_fraction: float
    noise_floor_db: float
    dynamic_range_db: float
    bandwidth_hz: float
    low_band_ratio_db: float
    highpass_suspect: bool
    agc_suspect: bool
    curve_count: int
    strongest_snr_db: float | None
    event_offset_s: float | None
    verdict: str
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _probe(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
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
    except Exception:
        return {}


def _bandwidth(y: np.ndarray, sr: int) -> tuple[float, float]:
    freqs, psd = signal.welch(y, fs=sr, nperseg=min(8192, max(2048, y.size // 4)))
    cumulative = np.cumsum(psd)
    if cumulative[-1] <= 0:
        return 0.0, 0.0
    idx = int(np.searchsorted(cumulative, 0.99 * cumulative[-1]))
    bandwidth = float(freqs[min(idx, freqs.size - 1)])
    low = psd[(freqs >= 50) & (freqs <= 100)]
    mid = psd[(freqs >= 120) & (freqs <= 300)]
    if low.size == 0 or mid.size == 0:
        return bandwidth, 0.0
    ratio = float(10 * np.log10((np.mean(low) + 1e-20) / (np.mean(mid) + 1e-20)))
    return bandwidth, ratio


def assess_viability(path: Path, *, sr: int = 8000) -> ViabilityReport:
    probe = _probe(path)
    fmt = probe.get("format", {})
    stream: dict = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {})
    y, actual_sr = load_audio(path, sr=sr)
    if y.ndim > 1:
        y = y.mean(axis=1)
    duration = float(y.size / actual_sr)
    clipping = float(np.mean(np.abs(y) >= 0.999))
    noise = float(np.percentile(np.abs(y), 20) + 1e-12)
    peak = float(np.max(np.abs(y)) + 1e-12)
    noise_db = float(20 * np.log10(noise))
    dynamic = float(20 * np.log10(peak / max(noise, 1e-9)))
    bandwidth, low_ratio = _bandwidth(y, actual_sr)
    highpass = low_ratio < -18.0 and bandwidth < 500.0

    # AGC hint: very steady frame loudness despite a wide dynamic range.
    frame = max(1, int(0.05 * actual_sr))
    frames = y[: (y.size // frame) * frame].reshape(-1, frame)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-20)
    loud = 20 * np.log10(rms + 1e-20)
    agc = bool(np.std(loud) < 3.0 and dynamic > 35.0)

    spec = compute_spectrogram(y, actual_sr, nperseg=2048, hop=128, fmin=40, fmax=800)
    ridges = detect_ridges(spec, fmin=60, fmax=320, threshold_db=-30.0, max_slope_hz_s=10.0, max_tracks=5)
    curves = [r for r in ridges if r.drop_hz >= 8.0 and r.snr_db > 6.0]
    offset = None
    if len(curves) >= 2:
        offset = float(abs(curves[1].times[0] - curves[0].times[0]))

    reasons: list[str] = []
    if not curves:
        verdict = "visual-only"
        reasons.append("no measurable Doppler ridge in the recorded band")
    elif len(curves) >= 2 and offset is not None and offset >= 30.0:
        verdict = "multiple-events"
        reasons.append(
            f"{len(curves)} ridges; strongest two separated by {offset:.1f} s (pair not validated)"
        )
    elif len(curves) == 1:
        verdict = "single-event"
        reasons.append("one ridge; needs a known recording time or a second event")
    else:
        verdict = "marginal"
        reasons.append("ridges are too close together to provide a time offset")
    if highpass:
        reasons.append("low-band energy is attenuated; a phone high-pass may have removed prop tones")
    if clipping > 0.001:
        reasons.append("clipping present; codec artifacts may distort the curve")
    if agc:
        reasons.append("possible AGC; amplitude is not a reliable range cue")
    if duration < 20.0:
        reasons.append("clip is short; a full pass may be truncated")

    return ViabilityReport(
        duration_s=duration,
        sample_rate=int(stream.get("sample_rate") or actual_sr),
        codec=stream.get("codec_name"),
        bitrate_kbps=float(fmt.get("bit_rate", 0)) / 1000.0 if fmt.get("bit_rate") else None,
        clipping_fraction=clipping,
        noise_floor_db=noise_db,
        dynamic_range_db=dynamic,
        bandwidth_hz=bandwidth,
        low_band_ratio_db=float(low_ratio),
        highpass_suspect=bool(highpass),
        agc_suspect=bool(agc),
        curve_count=len(curves),
        strongest_snr_db=max((r.snr_db for r in curves), default=None),
        event_offset_s=offset,
        verdict=verdict,
        reasons=reasons,
        notes=[
            "This is a feasibility audit, not a location estimate.",
            "A phone high-pass, music bed, or AGC can make a real curve unusable.",
        ],
    )
