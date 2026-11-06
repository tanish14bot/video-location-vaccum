"""Doppler physics.

Sign convention matches the source method: the Doppler equation is

    f = f0 * c / (c + v_r)

where ``v_r`` is the radial component of the aircraft velocity along the
aircraft -> observer line, positive when receding. The observer is stationary.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

SPEED_OF_SOUND_20C = 343.0


def speed_of_sound(temperature_c: float = 20.0, humidity_pct: float = 50.0) -> float:
    """Approximate speed of sound in moist air (Cramer 1993 simplification).

    The humidity term is small (<0.5%) but is included so the parameter is
    explicit rather than silently ignored.
    """
    t = float(temperature_c)
    h = max(0.0, min(100.0, float(humidity_pct)))
    # Dry-air approximation, accurate to ~0.2% over -20..40 C.
    c_dry = 331.3 + 0.606 * t
    # Very small moist-air correction; scaled to 0 at 0% RH.
    c_moist = c_dry * (1.0 + 0.000_16 * h)
    return float(c_moist)


def doppler_frequency(f0_hz: float, c_mps: float, v_radial_mps: ArrayLike) -> NDArray[np.float64]:
    """Observed frequency for a receding-positive radial velocity."""
    vr = np.asarray(v_radial_mps, dtype=float)
    return f0_hz * c_mps / (c_mps + vr)


def radial_velocity(
    position_m: ArrayLike, velocity_mps: ArrayLike, observer_m: ArrayLike
) -> NDArray[np.float64]:
    """Radial velocity along aircraft -> observer, receding positive."""
    p = np.asarray(position_m, dtype=float)
    v = np.asarray(velocity_mps, dtype=float)
    o = np.asarray(observer_m, dtype=float)
    delta = p - o
    r = np.linalg.norm(delta, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        unit = delta / r[..., None]
    return np.sum(v * unit, axis=-1)


def slant_range(position_m: ArrayLike, observer_m: ArrayLike) -> NDArray[np.float64]:
    return np.linalg.norm(np.asarray(position_m, dtype=float) - np.asarray(observer_m, dtype=float), axis=-1)


def delayed_cpa_time(t_cpa_s: float, slant_m: float, c_mps: float) -> float:
    """When an observer hears the closest approach."""
    return t_cpa_s + slant_m / c_mps


@dataclass(frozen=True)
class StraightLinePass:
    """Constant-speed, constant-altitude straight pass used for curve fitting.

    The aircraft moves along +x at speed ``v`` and passes closest to the
    observer at ``t0`` with horizontal miss distance ``d`` and height ``h``
    above the observer. This is the parameterisation exposed by the source
    tool: ``(f0, v, d, t0)``.
    """

    f0_hz: float
    speed_mps: float
    cpa_horizontal_m: float
    cpa_time_s: float
    height_m: float = 0.0

    def state(self, t_s: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        t = np.asarray(t_s, dtype=float)
        x = self.speed_mps * (t - self.cpa_time_s)
        y = np.full_like(x, self.cpa_horizontal_m)
        z = np.full_like(x, self.height_m)
        pos = np.stack([x, y, z], axis=-1)
        vel = np.zeros_like(pos)
        vel[..., 0] = self.speed_mps
        return pos, vel

    def frequency(self, t_s: ArrayLike, c_mps: float) -> NDArray[np.float64]:
        """Observed frequency at *listen* time, including propagation delay.

        The emission-time fixed point is solved for the whole array at once;
        the contraction is fast because range changes much slower than ``c``.
        """
        t = np.atleast_1d(np.asarray(t_s, dtype=float))
        te = t.copy()
        for _ in range(12):
            pos, _ = self.state(te)
            r = np.linalg.norm(pos, axis=-1)
            te = t - r / c_mps
        pos, vel = self.state(te)
        vr = radial_velocity(pos, vel, np.zeros(3))
        return doppler_frequency(self.f0_hz, c_mps, vr)

    def frequency_no_delay(self, t_s: ArrayLike, c_mps: float) -> NDArray[np.float64]:
        pos, vel = self.state(t_s)
        vr = radial_velocity(pos, vel, np.zeros(3))
        return doppler_frequency(self.f0_hz, c_mps, vr)
