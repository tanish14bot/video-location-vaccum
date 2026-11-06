"""Doppler ridge detection.

The detector is deliberately conservative: it finds continuous, mostly
falling narrowband ridges in a user-supplied band and reports their strength.
It never claims an event is a Doppler curve; the fit stage and the operator
decide that.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .spectrogram import Spectrogram


@dataclass
class Ridge:
    times: NDArray[np.float64]
    freqs: NDArray[np.float64]
    db: NDArray[np.float64]
    score: float
    snr_db: float

    @property
    def duration_s(self) -> float:
        return float(self.times[-1] - self.times[0])

    @property
    def drop_hz(self) -> float:
        return float(self.freqs[0] - self.freqs[-1])


def detect_ridges(
    spec: Spectrogram,
    *,
    fmin: float = 60.0,
    fmax: float = 400.0,
    threshold_db: float = -45.0,
    max_slope_hz_s: float = 25.0,
    max_tracks: int = 5,
    min_duration_s: float = 8.0,
    min_drop_hz: float = 5.0,
    freq_stride: int = 2,
    max_peaks_per_frame: int = 3,
    max_coast_frames: int = 6,
    whiten: bool = False,
    threshold_z: float = 2.0,
    line_s: float = 5.0,
) -> list[Ridge]:
    """Track falling ridges by linking per-frame spectral peaks.

    A global dynamic-programming pass tends to follow a flat noise band across a
    long recording. Linking local peaks into tracks keeps separate events
    separate, and the drop/duration checks reject horizontal bands.
    """
    freqs, times, db = spec.band(fmin, fmax)
    if freqs.size < 5 or times.size < 5:
        return []
    db = db[::freq_stride, :]
    freqs = freqs[::freq_stride]
    if whiten:
        # Remove steady tones and broadband events before tracking. This is the
        # whitening used by doppler-locate (MIT); see NOTICE.
        from .spectrogram import Spectrogram

        z = Spectrogram(db, freqs, times, spec.sr, spec.nperseg, spec.hop).whiten(line_s=line_s)
        db = z.db
        threshold = threshold_z
    else:
        threshold = threshold_db
    df = float(np.median(np.diff(freqs)))
    dt = float(np.median(np.diff(times)))
    floor = float(np.median(db))

    tracks = _track_peaks(
        db,
        threshold_db=threshold,
        max_peaks=max_peaks_per_frame,
        max_step_bins=max(2, round(max_slope_hz_s * dt / max(df, 1e-9)) + 2),
        max_coast=max_coast_frames,
    )

    candidates: list[Ridge] = []
    for tr in tracks:
        if len(tr) < 3:
            continue
        idx = np.array([p[0] for p in tr])
        fi = np.array([p[1] for p in tr])
        p = np.array([p[2] for p in tr])
        t = times[idx]
        f = freqs[fi]
        if (t[-1] - t[0]) < min_duration_s or (f[0] - f[-1]) < min_drop_hz:
            continue
        candidates.append(
            Ridge(
                times=t,
                freqs=f,
                db=p,
                score=float(np.sum(p - floor)),
                snr_db=float(np.mean(p) - floor),
            )
        )

    candidates.sort(key=lambda r: (r.snr_db, r.score), reverse=True)
    kept: list[Ridge] = []
    for r in candidates:
        if all(_overlap_fraction(r, k) < 0.5 for k in kept):
            kept.append(r)
    return kept[:max_tracks]


def _track_peaks(
    db: NDArray[np.float64],
    *,
    threshold_db: float,
    max_peaks: int,
    max_step_bins: int,
    max_coast: int,
) -> list[list[tuple[int, int, float]]]:
    """Link peaks across frames into tracks of (time_idx, freq_idx, db)."""
    from scipy.signal import find_peaks

    active: list[dict] = []
    finished: list[list[tuple[int, int, float]]] = []
    _f_count, t_count = db.shape

    for ti in range(t_count):
        column = db[:, ti]
        peaks, _ = find_peaks(column, height=threshold_db, distance=2)
        if peaks.size > max_peaks:
            order = np.argsort(column[peaks])[::-1][:max_peaks]
            peaks = peaks[order]
        remaining = list(map(int, peaks))

        for track in active:
            last_t, last_f, _ = track["points"][-1]
            slope = track.get("slope", 0.0)
            predicted = last_f + slope * (ti - last_t)
            if remaining:
                dist = np.abs(np.array(remaining, dtype=float) - predicted)
                j = int(np.argmin(dist))
                if dist[j] <= max_step_bins:
                    new_f = remaining.pop(j)
                    track["points"].append((ti, new_f, float(column[new_f])))
                    track["slope"] = 0.7 * slope + 0.3 * (new_f - last_f) / max(1, ti - last_t)
                    track["coast"] = 0
                    continue
            track["coast"] += 1
            if track["coast"] > max_coast:
                finished.append(track["points"])

        active = [t for t in active if t["coast"] <= max_coast]
        for f_idx in remaining:
            active.append(
                {
                    "points": [(ti, f_idx, float(column[f_idx]))],
                    "slope": 0.0,
                    "coast": 0,
                }
            )

    finished.extend(t["points"] for t in active)
    return finished


def _overlap_fraction(a: Ridge, b: Ridge) -> float:
    lo = max(float(a.times[0]), float(b.times[0]))
    hi = min(float(a.times[-1]), float(b.times[-1]))
    if hi <= lo:
        return 0.0
    shortest = max(1e-9, min(a.duration_s, b.duration_s))
    return (hi - lo) / shortest
