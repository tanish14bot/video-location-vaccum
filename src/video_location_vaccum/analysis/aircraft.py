"""Aircraft acoustic signature: blade-pass frequency and harmonic structure."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal


@dataclass
class AircraftSignature:
    blade_pass_hz: float | None
    harmonic_count: int
    tonal_db: float
    class_hint: str
    confidence: str


def harmonic_analysis(
    y: np.ndarray,
    sr: int,
    *,
    fmin: float = 60.0,
    fmax: float = 250.0,
) -> AircraftSignature:
    """Estimate a blade-pass fundamental with a harmonic product spectrum."""
    freqs, psd = signal.welch(y, fs=sr, nperseg=min(16384, max(2048, y.size // 4)))
    logp = 10.0 * np.log10(psd + 1e-20)
    median = float(np.median(logp[(freqs >= 40) & (freqs <= 800)]))
    peak = float(np.max(logp[(freqs >= 40) & (freqs <= 800)]))
    tonal = peak - median

    candidates = np.arange(fmin, fmax + 0.25, 0.25)
    best_f0 = None
    best_score = -np.inf
    for f0 in candidates:
        score = 0.0
        valid = 0
        for k in range(1, 6):
            target = f0 * k
            if target > 1500:
                break
            idx = int(np.searchsorted(freqs, target))
            if idx >= freqs.size:
                break
            score += float(logp[idx])
            valid += 1
        if valid >= 3:
            score /= valid
            if score > best_score:
                best_score = score
                best_f0 = float(f0)

    harmonic_count = 0
    if best_f0 is not None:
        for k in range(1, 7):
            target = best_f0 * k
            if target > 1500:
                break
            lo = np.searchsorted(freqs, target - 4.0)
            hi = np.searchsorted(freqs, target + 4.0)
            if hi > lo and float(np.max(logp[lo:hi])) > median + 6.0:
                harmonic_count += 1

    if best_f0 is not None and harmonic_count >= 3 and tonal > 8.0:
        hint = "prop/turboprop harmonic series"
        confidence = "medium"
    elif tonal > 10.0 and harmonic_count <= 1:
        hint = "narrowband tone; type uncertain"
        confidence = "low"
    else:
        hint = "broadband or no stable blade-pass tone; likely jet or too weak"
        confidence = "low"
    return AircraftSignature(
        blade_pass_hz=best_f0,
        harmonic_count=harmonic_count,
        tonal_db=tonal,
        class_hint=hint,
        confidence=confidence,
    )
