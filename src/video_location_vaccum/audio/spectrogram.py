"""Spectrogram computation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import signal


@dataclass
class Spectrogram:
    """Power spectrogram in dB relative to the per-run maximum."""

    db: NDArray[np.float64]  # (freq, time)
    freqs: NDArray[np.float64]
    times: NDArray[np.float64]
    sr: int
    nperseg: int
    hop: int

    def band(
        self, fmin: float, fmax: float
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        mask = (self.freqs >= fmin) & (self.freqs <= fmax)
        return self.freqs[mask], self.times, self.db[mask]

    def whiten(
        self,
        *,
        clip: tuple[float, float] = (0.0, 6.0),
        freq_hz: float = 15.0,
        line_s: float = 0.0,
    ) -> Spectrogram:
        """Robust z-score brightness for tracing.

        Adapted from `doppler-locate` (MIT): subtract the per-bin median over
        time, then a per-frame median over +/- ``freq_hz``, optionally a per-bin
        running median over ``line_s`` seconds, then divide by a robust spread.
        """
        from scipy.ndimage import median_filter

        s = self.db.astype(np.float64, copy=True)
        s -= np.median(s, axis=1, keepdims=True)
        if freq_hz > 0:
            df = float(np.median(np.diff(self.freqs)))
            k = max(3, round(2 * freq_hz / max(df, 1e-9)) | 1)
            s -= median_filter(s, size=(k, 1), mode="nearest")
        if line_s > 0:
            dt = float(np.median(np.diff(self.times)))
            k = max(3, round(line_s / max(dt, 1e-9)) | 1)
            s -= np.maximum(median_filter(s, size=(1, k), mode="nearest"), 0.0)
        mad = float(np.median(np.abs(s))) * 1.4826 + 1e-6
        z = np.clip(s / mad, clip[0], clip[1])
        return Spectrogram(z, self.freqs, self.times, self.sr, self.nperseg, self.hop)

    def power_at(self, f_hz: ArrayLike, t_s: ArrayLike, *, half_bins: int = 1) -> NDArray[np.float64]:
        """Sample dB along a curve, taking the max within +/- half_bins."""
        f = np.atleast_1d(np.asarray(f_hz, dtype=float))
        t = np.atleast_1d(np.asarray(t_s, dtype=float))
        fi = np.searchsorted(self.freqs, f)
        ti = np.searchsorted(self.times, t)
        fi = np.clip(fi, half_bins, self.freqs.size - 1 - half_bins)
        ti = np.clip(ti, 0, self.times.size - 1)
        vals = self.db[fi, ti].astype(float, copy=True)
        for d in range(1, half_bins + 1):
            vals = np.maximum(vals, self.db[fi - d, ti])
            vals = np.maximum(vals, self.db[fi + d, ti])
        return vals


def compute_spectrogram(
    y: NDArray[np.float64],
    sr: int,
    *,
    nperseg: int = 4096,
    hop: int = 256,
    fmin: float = 20.0,
    fmax: float = 800.0,
    window: str = "hann",
) -> Spectrogram:
    """Compute a dB spectrogram restricted to ``[fmin, fmax]``."""
    if y.size < nperseg:
        raise ValueError(f"signal too short: {y.size} samples < nperseg {nperseg}")
    freqs, times, sxx = signal.spectrogram(
        y,
        fs=sr,
        window=window,
        nperseg=nperseg,
        noverlap=nperseg - hop,
        detrend=False,
        scaling="density",
        mode="psd",
    )
    db = 10.0 * np.log10(np.maximum(sxx, 1e-20))
    db -= float(np.nanmax(db))
    mask = (freqs >= fmin) & (freqs <= fmax)
    return Spectrogram(db[mask], freqs[mask], times, sr, nperseg, hop)
