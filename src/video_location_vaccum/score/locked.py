"""Locked multi-event scoring.

One shared clock offset shifts both modelled curves; each event's fundamental
frequency is swept independently. This is the precision core: the relative
separation of the two events is never free.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from ..audio.spectrogram import Spectrogram
from ..geo.geodesy import LocalFrame
from .brightness import brightness_score, frequency_from_vr, radial_curve


@dataclass
class LockedScore:
    score: float
    score_a: float
    score_b: float
    dt_s: float
    f0_a: float
    f0_b: float
    coverage_a: float
    coverage_b: float


@dataclass
class EventObservation:
    times_s: ArrayLike  # spectrogram-relative times
    f0_hz: float
    track_times_s: ArrayLike | None = None  # absolute/track times for the model
    freqs_hz: ArrayLike | None = None  # observed ridge frequencies

    def track_times(self) -> ArrayLike:
        return self.times_s if self.track_times_s is None else self.track_times_s


def score_event(
    spec: Spectrogram,
    *,
    vr: ArrayLike,
    f0_hz: float,
    c_mps: float,
    times_s: ArrayLike,
    observed_freqs_hz: ArrayLike | None = None,
    freq_scale_hz: float = 2.0,
    half_bins: int = 1,
) -> tuple[float, float]:
    f = frequency_from_vr(f0_hz, c_mps, vr)
    bright, coverage = brightness_score(spec, times_s, f, half_bins=half_bins)
    if observed_freqs_hz is not None and bright > 0.0:
        obs = np.asarray(observed_freqs_hz, dtype=float)
        if obs.shape == f.shape and np.any(np.isfinite(obs)):
            rmse = float(np.sqrt(np.nanmean((f - obs) ** 2)))
            bright *= float(np.exp(-0.5 * (rmse / max(1e-6, freq_scale_hz)) ** 2))
    return bright, coverage


def sweep_locked(
    spec: Spectrogram,
    *,
    track_a,
    track_b,
    frame: LocalFrame,
    obs_a: EventObservation,
    obs_b: EventObservation,
    c_mps: float,
    sweep_t_s: float = 5.0,
    sweep_f0_pct: float = 5.0,
    dt_steps: int = 7,
    f0_steps: int = 3,
    half_bins: int = 1,
) -> LockedScore:
    """Search the shared clock offset and per-event f0; return the best pair."""
    dts = np.linspace(-sweep_t_s, sweep_t_s, max(2, dt_steps))
    fa = np.linspace(
        obs_a.f0_hz * (1 - sweep_f0_pct / 100.0),
        obs_a.f0_hz * (1 + sweep_f0_pct / 100.0),
        max(1, f0_steps),
    )
    fb = np.linspace(
        obs_b.f0_hz * (1 - sweep_f0_pct / 100.0),
        obs_b.f0_hz * (1 + sweep_f0_pct / 100.0),
        max(1, f0_steps),
    )

    best = LockedScore(-np.inf, 0.0, 0.0, 0.0, obs_a.f0_hz, obs_b.f0_hz, 0.0, 0.0)
    for dt in dts:
        vr_a = radial_curve(
            track=track_a, frame=frame, c_mps=c_mps, t_listen_s=obs_a.track_times(), dt_s=float(dt)
        )
        vr_b = radial_curve(
            track=track_b, frame=frame, c_mps=c_mps, t_listen_s=obs_b.track_times(), dt_s=float(dt)
        )
        for f0a in fa:
            sa, ca = score_event(
                spec,
                vr=vr_a,
                f0_hz=float(f0a),
                c_mps=c_mps,
                times_s=obs_a.times_s,
                observed_freqs_hz=obs_a.freqs_hz,
                half_bins=half_bins,
            )
            if sa <= 0.0:
                continue
            for f0b in fb:
                sb, cb = score_event(
                    spec,
                    vr=vr_b,
                    f0_hz=float(f0b),
                    c_mps=c_mps,
                    times_s=obs_b.times_s,
                    observed_freqs_hz=obs_b.freqs_hz,
                    half_bins=half_bins,
                )
                total = sa + sb
                if total > best.score:
                    best = LockedScore(
                        score=float(total),
                        score_a=float(sa),
                        score_b=float(sb),
                        dt_s=float(dt),
                        f0_a=float(f0a),
                        f0_b=float(f0b),
                        coverage_a=float(ca),
                        coverage_b=float(cb),
                    )
    return best
