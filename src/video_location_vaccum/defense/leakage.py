"""Leakage detection: does this recording contain a usable Doppler signature?"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import numpy as np

from ..audio.detect import detect_ridges
from ..audio.fit import fit_pass
from ..audio.io import load_audio
from ..audio.spectrogram import compute_spectrogram


@dataclass
class LeakageEvent:
    start_s: float
    end_s: float
    f0_hz: float | None
    speed_mps: float | None
    slant_m: float | None
    snr_db: float
    drop_hz: float
    fit_ok: bool
    times_s: list[float] = field(default_factory=list)
    freqs_hz: list[float] = field(default_factory=list)


@dataclass
class LeakageReport:
    events: list[LeakageEvent] = field(default_factory=list)
    risk: str = "unknown"
    notes: list[str] = field(default_factory=list)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def max_snr_db(self) -> float:
        return max((e.snr_db for e in self.events), default=-np.inf)

    def to_dict(self) -> dict:
        return {
            "risk": self.risk,
            "event_count": self.event_count,
            "max_snr_db": None if not self.events else round(self.max_snr_db, 2),
            "events": [
                {
                    "start_s": round(e.start_s, 2),
                    "end_s": round(e.end_s, 2),
                    "f0_hz": None if e.f0_hz is None else round(e.f0_hz, 2),
                    "speed_mps": None if e.speed_mps is None else round(e.speed_mps, 2),
                    "slant_m": None if e.slant_m is None else round(e.slant_m, 1),
                    "snr_db": round(e.snr_db, 2),
                    "drop_hz": round(e.drop_hz, 2),
                    "fit_ok": e.fit_ok,
                }
                for e in self.events
            ],
            "notes": self.notes,
        }


def analyze_leakage(path: Path, *, sr: int = 8000) -> LeakageReport:
    y, actual_sr = load_audio(path, sr=sr)
    if y.ndim > 1:
        y = y.mean(axis=1)
    spec = compute_spectrogram(y, actual_sr, nperseg=2048, hop=128, fmin=40, fmax=800)
    ridges = detect_ridges(
        spec,
        fmin=60,
        fmax=320,
        threshold_db=-30.0,
        max_slope_hz_s=10.0,
        max_tracks=8,
        min_duration_s=8.0,
        min_drop_hz=6.0,
    )
    events: list[LeakageEvent] = []
    for ridge in ridges:
        f0 = speed = slant = None
        fit_ok = False
        try:
            fit = fit_pass(ridge.times, ridge.freqs, c_mps=343.0, height_m=0.0)
            f0 = fit.pass_.f0_hz
            speed = fit.pass_.speed_mps
            slant = fit.pass_.cpa_horizontal_m
            fit_ok = fit.success
        except Exception:
            pass
        events.append(
            LeakageEvent(
                start_s=float(ridge.times[0]),
                end_s=float(ridge.times[-1]),
                f0_hz=f0,
                speed_mps=speed,
                slant_m=slant,
                snr_db=float(ridge.snr_db),
                drop_hz=float(ridge.drop_hz),
                fit_ok=fit_ok,
                times_s=ridge.times.tolist(),
                freqs_hz=ridge.freqs.tolist(),
            )
        )

    strong = [e for e in events if e.snr_db > 10.0 and e.drop_hz > 12.0]
    if len(strong) >= 2:
        risk = "high"
    elif len(strong) == 1:
        risk = "medium"
    elif events:
        risk = "low"
    else:
        risk = "none"

    notes = [
        "A second event (or a known time) is required to turn these curves into a location.",
        "Removing the curve is not the same as removing every location vector.",
    ]
    if len(strong) >= 2:
        offsets = [round(b.start_s - a.start_s, 1) for a, b in pairwise(strong)]
        notes.append(f"strongest ridge separations (s): {offsets}; no pair has been validated")
    return LeakageReport(events=events, risk=risk, notes=notes)
