"""Guided Doppler ridge tracing.

Adapted from `doppler-locate` (MIT): Viterbi path through a whitened
spectrogram, with optional start/end frequency pins. Use it after looking at the
spectrogram; it measures a curve you have already identified.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .spectrogram import Spectrogram


@dataclass
class Trace:
    times: NDArray[np.float64]
    freqs: NDArray[np.float64]
    score: NDArray[np.float64]


def trace_ridge(
    spec: Spectrogram,
    *,
    f_start: float | None = None,
    f_end: float | None = None,
    max_slope_hz_s: float = 8.0,
    penalty: float = 0.05,
    min_z: float = 1.5,
) -> Trace:
    """Follow the brightest smooth ridge through a whitened spectrogram."""
    z = spec.db.astype(np.float64, copy=False)
    if z.size == 0:
        return Trace(np.array([]), np.array([]), np.array([]))
    df = float(np.median(np.diff(spec.freqs)))
    dt = float(np.median(np.diff(spec.times)))
    max_step = max(1, int(np.ceil(max_slope_hz_s * dt / max(df, 1e-9))))
    sb = -1 if f_start is None else round((f_start - spec.freqs[0]) / df)
    eb = -1 if f_end is None else round((f_end - spec.freqs[0]) / df)
    path = _viterbi(z, max_step=max_step, penalty=penalty, start_bin=sb, end_bin=eb)
    if path.size == 0:
        return Trace(np.array([]), np.array([]), np.array([]))

    j = np.arange(path.size)
    b = np.clip(path, 1, spec.freqs.size - 2)
    y0, y1, y2 = z[b - 1, j], z[b, j], z[b + 1, j]
    den = y0 - 2 * y1 + y2
    off = np.where(den < 0, 0.5 * (y0 - y2) / np.where(den < 0, den, -1.0), 0.0)
    freqs = spec.freqs[0] + (b + np.clip(off, -0.5, 0.5)) * df
    score = z[path, j]

    # Keep the longest bright run; the ends usually wander into noise.
    smooth = np.convolve(score, np.ones(9) / 9, mode="same")
    good = smooth >= min_z
    best, cur, start, best_range = 0, 0, 0, (0, 0)
    for i, flag in enumerate(np.append(good, False)):
        if flag:
            if cur == 0:
                start = i
            cur += 1
        else:
            if cur > best:
                best, best_range = cur, (start, i)
            cur = 0
    keep = np.zeros(score.size, bool)
    keep[best_range[0] : best_range[1]] = True
    keep &= score >= 0.5 * min_z
    return Trace(spec.times[keep], freqs[keep], score[keep])


def _viterbi(
    z: NDArray[np.float64],
    *,
    max_step: int,
    penalty: float,
    start_bin: int,
    end_bin: int,
) -> NDArray[np.int32]:
    """Max-brightness path with a slope penalty and optional edge pins."""
    f_count, t_count = z.shape
    if f_count == 0 or t_count == 0:
        return np.array([], dtype=np.int32)
    dp = np.full((t_count, f_count), -np.inf, dtype=np.float64)
    back = np.full((t_count, f_count), -1, dtype=np.int16)
    dp[0] = z[:, 0]
    if 0 <= start_bin < f_count:
        dp[0, :start_bin] = -np.inf
        dp[0, start_bin + 1 :] = -np.inf

    lags = np.arange(-max_step, max_step + 1)
    penalties = penalty * lags * lags
    for ti in range(1, t_count):
        prev = dp[ti - 1]
        best = np.full(f_count, -np.inf)
        best_idx = np.full(f_count, -1, dtype=np.int16)
        for lag, pen in zip(lags, penalties, strict=True):
            src = np.arange(f_count) - lag
            valid = (src >= 0) & (src < f_count)
            cand = np.full(f_count, -np.inf)
            cand[valid] = prev[src[valid]] - pen
            better = cand > best
            best[better] = cand[better]
            best_idx[better] = src[better].astype(np.int16)
        dp[ti] = best + z[:, ti]
        back[ti] = best_idx

    end = end_bin if 0 <= end_bin < f_count else int(np.argmax(dp[-1]))
    if not np.isfinite(dp[-1, end]):
        return np.array([], dtype=np.int32)
    path = np.full(t_count, -1, dtype=np.int32)
    path[-1] = end
    for ti in range(t_count - 1, 0, -1):
        prev = back[ti, path[ti]]
        if prev < 0:
            break
        path[ti - 1] = prev
    return path
