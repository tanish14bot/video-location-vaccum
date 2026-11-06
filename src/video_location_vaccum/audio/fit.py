"""Fit a constant-speed straight pass to an observed Doppler ridge."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares

from ..config import EventConfig, FitQuality
from ..model.doppler import StraightLinePass


@dataclass
class FitResult:
    pass_: StraightLinePass
    sigma: dict[str, float]
    rmse_hz: float
    n_points: int
    success: bool
    message: str
    covariance: NDArray[np.float64] | None = None

    @property
    def f_pre_hz(self) -> float:
        return float(self.pass_.frequency_no_delay(-1e5, 343.0))

    @property
    def f_post_hz(self) -> float:
        return float(self.pass_.frequency_no_delay(+1e5, 343.0))

    def heard_cpa_time(self, c_mps: float = 343.0) -> float:
        """Listen time at which the CPA is heard (emission CPA + slant/c)."""
        p = self.pass_
        slant = float(np.hypot(p.cpa_horizontal_m, p.height_m))
        return p.cpa_time_s + slant / c_mps

    def to_event(self, *, event_id: int, c_mps: float = 343.0) -> EventConfig:
        p = self.pass_
        slant = float(np.hypot(p.cpa_horizontal_m, p.height_m))
        sigma_d = max(50.0, 6.0 * self.sigma.get("cpa_horizontal_m", 0.0))
        sigma_v = max(5.0, 6.0 * self.sigma.get("speed_mps", 0.0))
        return EventConfig(
            id=event_id,
            t_heard_s=self.heard_cpa_time(c_mps),
            f0_hz=p.f0_hz,
            f0_sigma_hz=self.sigma.get("f0_hz", 0.0),
            velocity_band_mps=(max(1.0, p.speed_mps - sigma_v), p.speed_mps + sigma_v),
            slant_band_m=(max(0.0, slant - sigma_d), slant + sigma_d),
            fit_quality=FitQuality.PERFECT if self.rmse_hz < 2.0 else FitQuality.IMPERFECT,
        )


def _model(
    params: NDArray[np.float64], t: NDArray[np.float64], c: float, height: float
) -> NDArray[np.float64]:
    f0, v, d, t0 = params
    return StraightLinePass(
        f0_hz=f0, speed_mps=v, cpa_horizontal_m=d, cpa_time_s=t0, height_m=height
    ).frequency(t, c)


def fit_pass(
    t_s: ArrayLike,
    f_hz: ArrayLike,
    *,
    c_mps: float = 343.0,
    height_m: float = 0.0,
    f0_guess: float | None = None,
    max_nfev: int = 400,
) -> FitResult:
    """Robustly fit ``(f0, speed, cpa distance, cpa time)`` to ridge samples."""
    t = np.asarray(t_s, dtype=float)
    f = np.asarray(f_hz, dtype=float)
    good = np.isfinite(t) & np.isfinite(f) & (f > 0)
    t, f = t[good], f[good]
    if t.size < 8:
        raise ValueError(f"need at least 8 finite samples, got {t.size}")

    order = np.argsort(t)
    t, f = t[order], f[order]
    t0_guess = float(t[np.argmin(f)])
    f0_guess = float(f0_guess if f0_guess is not None else np.median(f))
    fmax, fmin = float(np.max(f)), float(np.min(f))
    v_asym = c_mps * (fmax - fmin) / max(1e-9, (fmax + fmin))

    lower = np.array([max(20.0, fmin * 0.5), 1.0, 0.0, t.min() - 120.0])
    upper = np.array([max(1000.0, fmax * 2.0), 500.0, 50_000.0, t.max() + 120.0])

    starts = [
        (f0_guess, max(10.0, v_asym), 2000.0, t0_guess),
        (f0_guess, max(10.0, v_asym * 0.7), 5000.0, t0_guess),
        (f0_guess, max(10.0, v_asym * 1.4), 800.0, t0_guess),
        (float(np.percentile(f, 20)), max(10.0, v_asym), 3000.0, t0_guess),
    ]

    best: least_squares | None = None
    for x0 in starts:
        x0c = np.clip(np.asarray(x0, dtype=float), lower, upper)
        try:
            res = least_squares(
                lambda p: _model(p, t, c_mps, height_m) - f,
                x0c,
                bounds=(lower, upper),
                loss="soft_l1",
                f_scale=max(1.0, float(np.std(f)) * 0.1),
                max_nfev=max_nfev,
            )
        except Exception:
            continue
        if best is None or res.cost < best.cost:
            best = res

    if best is None:
        raise RuntimeError("all fit starts failed")

    f0, v, d, t0 = (float(x) for x in best.x)
    residual = _model(best.x, t, c_mps, height_m) - f
    rmse = float(np.sqrt(np.mean(residual**2)))

    sigma: dict[str, float] = {}
    cov = None
    try:
        jac = best.jac
        dof = max(1, t.size - best.x.size)
        s2 = float(np.sum(residual**2) / dof)
        cov = np.linalg.inv(jac.T @ jac) * s2
        names = ("f0_hz", "speed_mps", "cpa_horizontal_m", "cpa_time_s")
        for name, value in zip(names, np.sqrt(np.maximum(0.0, np.diag(cov))), strict=True):
            sigma[name] = float(value)
    except np.linalg.LinAlgError:
        pass

    return FitResult(
        pass_=StraightLinePass(f0_hz=f0, speed_mps=v, cpa_horizontal_m=d, cpa_time_s=t0, height_m=height_m),
        sigma=sigma,
        rmse_hz=rmse,
        n_points=int(t.size),
        success=bool(best.success),
        message=str(best.message),
        covariance=cov,
    )
