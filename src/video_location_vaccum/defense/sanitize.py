"""Sanitize, mask, or decoy Doppler signatures.

These transforms are for your own recordings, or recordings you are authorized
to modify. They alter the evidence: keep the transformation manifest, and do
not present a sanitized file as an unmodified original.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy import signal

from ..audio.io import load_audio
from ..model.doppler import StraightLinePass
from .leakage import LeakageReport, analyze_leakage


@dataclass
class TransformResult:
    output: Path
    mode: str
    manifest: dict


def _notch(
    y: NDArray[np.float64],
    sr: int,
    events: list[tuple[float, float, float]],
    *,
    width_hz: float = 10.0,
    depth: float = 0.999,
) -> NDArray[np.float64]:
    """Attenuate a time-frequency corridor around each (t_rel, f, amplitude) point."""
    nperseg = 2048
    noverlap = 1536
    # shortcut: whole-file STFT in memory; chunk for multi-hour files.
    f, t, spec_z = signal.stft(y, fs=sr, nperseg=nperseg, noverlap=noverlap)
    for t_rel, f_hz, _amp in events:
        ti = int(np.searchsorted(t, t_rel))
        if ti < 0 or ti >= t.size:
            continue
        df = float(np.median(np.diff(f)))
        half = max(2, round(width_hz / max(df, 1e-9)))
        fi = int(np.searchsorted(f, f_hz))
        lo, hi = max(0, fi - half), min(f.size, fi + half + 1)
        if hi <= lo:
            continue
        # Rectangular corridor across neighbouring STFT frames. A Gaussian
        # taper leaves too much energy in the skirt for a strong ridge.
        for frame in (ti - 1, ti, ti + 1):
            if 0 <= frame < t.size:
                spec_z[lo:hi, frame] *= 1.0 - depth
    _, out = signal.istft(spec_z, fs=sr, nperseg=nperseg, noverlap=noverlap)
    if out.size < y.size:
        out = np.pad(out, (0, y.size - out.size))
    return np.asarray(out[: y.size], dtype=np.float64)


def _cut(
    y: NDArray[np.float64], sr: int, start_s: float, end_s: float, fade_s: float = 0.03
) -> NDArray[np.float64]:
    out = y.copy()
    a = max(0, int(start_s * sr))
    b = min(out.size, int(end_s * sr))
    if b <= a:
        return out
    fade = max(1, int(fade_s * sr))
    # Fade into and out of a low-level ambient bed rather than a hard digital zero.
    ambient = float(np.percentile(np.abs(out), 20)) or 1e-4
    out[a:b] = np.random.default_rng(0).normal(0.0, ambient, b - a)
    ramp = min(fade, (b - a) // 2)
    if ramp > 0:
        out[a : a + ramp] *= np.linspace(0.0, 1.0, ramp)
        out[b - ramp : b] *= np.linspace(1.0, 0.0, ramp)
    return out


def _add_noise(y: NDArray[np.float64], sr: int, snr_db: float) -> NDArray[np.float64]:
    rms = float(np.sqrt(np.mean(y**2) + 1e-20))
    noise_rms = rms / (10.0 ** (snr_db / 20.0))
    rng = np.random.default_rng(1)
    noise = rng.normal(0.0, noise_rms, y.size)
    # Shape the noise toward the low band where the curve lives.
    sos = signal.butter(4, [40.0 / (sr / 2), 600.0 / (sr / 2)], btype="band", output="sos")
    noise = signal.sosfilt(sos, noise)
    return y + noise


def _decoy(
    y: NDArray[np.float64],
    sr: int,
    *,
    seed: int = 0,
    count: int = 2,
    amplitude: float = 0.04,
) -> NDArray[np.float64]:
    rng = np.random.default_rng(seed)
    t = np.arange(y.size, dtype=float) / sr
    out = y.copy()
    duration = y.size / sr
    for _ in range(count):
        f0 = float(rng.uniform(90.0, 180.0))
        speed = float(rng.uniform(55.0, 130.0))
        distance = float(rng.uniform(600.0, 3500.0))
        t0 = float(rng.uniform(0.15 * duration, 0.85 * duration))
        height = float(rng.uniform(400.0, 1500.0))
        p = StraightLinePass(
            f0_hz=f0,
            speed_mps=speed,
            cpa_horizontal_m=distance,
            cpa_time_s=t0,
            height_m=height,
        )
        f = p.frequency(t, 343.0)
        phase = 2.0 * np.pi * np.cumsum(f) / sr
        out += amplitude * np.sin(phase)
    return out


def _write_wav(path: Path, y: NDArray[np.float64], sr: int) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(y, -1.0, 1.0), sr)


def sanitize_file(
    source: Path,
    output: Path,
    *,
    mode: str = "notch",
    event_index: int | None = None,
    width_hz: float = 10.0,
    snr_db: float = 12.0,
    decoys: int = 2,
    add_noise: bool = False,
) -> TransformResult:
    """Apply one defense mode and write a transformation manifest."""
    allowed = {"notch", "cut", "mask", "decoy"}
    if mode not in allowed:
        raise ValueError(f"mode must be one of {sorted(allowed)}")
    y, sr = load_audio(source, sr=16000)
    if y.ndim > 1:
        y = y.mean(axis=1)
    before = analyze_leakage(source)
    events = before.events
    if event_index is not None:
        events = [events[event_index]] if 0 <= event_index < len(events) else []

    out = y.copy()
    if mode in {"notch", "mask", "decoy"}:
        points: list[tuple[float, float, float]] = []
        for e in events:
            if e.times_s and e.freqs_hz and len(e.times_s) == len(e.freqs_hz):
                n = len(e.times_s)
                stride = max(1, n // max(20, int((e.end_s - e.start_s) * 20)))
                pts = list(zip(e.times_s[::stride], e.freqs_hz[::stride], strict=True))
            else:
                pts = [(float(t), float(e.f0_hz or 140.0)) for t in np.linspace(e.start_s, e.end_s, 100)]
            points.extend((float(t), float(f), 1.0) for t, f, *_ in pts)
        out = _notch(out, sr, points, width_hz=width_hz)
    if mode == "cut":
        for e in events:
            out = _cut(out, sr, e.start_s, e.end_s)
    if mode == "mask" or add_noise:
        out = _add_noise(out, sr, snr_db)
    if mode == "decoy":
        out = _decoy(out, sr, count=decoys)

    _write_wav(output, out, sr)
    after = analyze_leakage(output)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "source_sha256": _sha256(source),
        "output": str(output),
        "output_sha256": _sha256(output),
        "mode": mode,
        "event_index": event_index,
        "width_hz": width_hz,
        "snr_db": snr_db if (mode == "mask" or add_noise) else None,
        "decoys": decoys if mode == "decoy" else 0,
        "before": _summary(before),
        "after": _summary(after),
        "warning": (
            "This file has been altered. Do not present it as an unmodified original. "
            "Decoys are counter-forensic and may invalidate authenticity claims."
        ),
    }
    manifest_path = output.with_suffix(".transform.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return TransformResult(output=output, mode=mode, manifest=manifest)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _summary(report: LeakageReport) -> dict:
    return {
        "event_count": report.event_count,
        "risk": report.risk,
        "max_snr_db": None if not report.events else round(report.max_snr_db, 2),
        "events": [
            {
                "start_s": round(e.start_s, 2),
                "end_s": round(e.end_s, 2),
                "snr_db": round(e.snr_db, 2),
                "drop_hz": round(e.drop_hz, 2),
            }
            for e in report.events
        ],
    }
