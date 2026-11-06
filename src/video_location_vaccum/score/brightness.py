"""Curve scoring against a spectrogram."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..audio.spectrogram import Spectrogram
from ..geo.geodesy import LocalFrame
from ..model.doppler import doppler_frequency


def radial_curve(
    *,
    track,
    frame: LocalFrame,
    c_mps: float,
    t_listen_s: ArrayLike,
    dt_s: float = 0.0,
) -> NDArray[np.float64]:
    """Radial velocity (receding positive) at each listener time."""
    t = np.atleast_1d(np.asarray(t_listen_s, dtype=float)) + dt_s
    te = t.copy()
    for _ in range(10):
        pos, _ = track.state_at(te)
        enu = frame.enu_from_ecef(pos)
        r = np.linalg.norm(enu, axis=1)
        te = t - r / c_mps
    pos, vel_ecef = track.state_at(te)
    enu = frame.enu_from_ecef(pos)
    vel_enu = frame.vector_ecef_to_enu(vel_ecef)
    r = np.linalg.norm(enu, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        vr = np.sum(vel_enu * (enu / r[:, None]), axis=1)
    # Do not fabricate a curve outside the track. Mark only those samples;
    # one edge sample must not poison the whole curve.
    out_of_range = (te < track.t_min) | (te > track.t_max)
    vr[out_of_range] = np.nan
    return vr


def frequency_from_vr(f0_hz: float, c_mps: float, vr: ArrayLike) -> NDArray[np.float64]:
    return doppler_frequency(f0_hz, c_mps, vr)


def brightness_score(
    spec: Spectrogram,
    t_s: ArrayLike,
    f_hz: ArrayLike,
    *,
    half_bins: int = 1,
    min_coverage: float = 0.6,
) -> tuple[float, float]:
    """Mean linear power under a curve and the fraction of in-band samples.

    Returns ``(score, coverage)``. ``score`` is in arbitrary linear units; compare
    only within one run and one spectrogram.
    """
    f = np.atleast_1d(np.asarray(f_hz, dtype=float))
    t = np.atleast_1d(np.asarray(t_s, dtype=float))
    ok = np.isfinite(f) & np.isfinite(t)
    f, t = f[ok], t[ok]
    if f.size == 0:
        return 0.0, 0.0
    db = spec.power_at(f, t, half_bins=half_bins)
    finite = np.isfinite(db)
    coverage = float(finite.mean()) if db.size else 0.0
    if coverage < min_coverage:
        return 0.0, coverage
    power = np.power(10.0, db[finite] / 10.0)
    return float(np.mean(power)), coverage
