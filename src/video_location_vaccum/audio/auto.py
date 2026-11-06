"""Automatic flyover detection, backed by the vendored MIT detector.

This adapter turns the detector's flyovers into our event configuration. It is
deliberately thin: the detector owns detection, harmonic grouping, and refinement.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..config import EventConfig, FitQuality
from ..vendor.doppler_locate.detect import Params, Result, detect


def detect_events(
    path: Path,
    *,
    start: float = 0.0,
    duration: float | None = None,
    params: Params | None = None,
    log: Callable[[str], None] | None = None,
) -> tuple[list[EventConfig], Result]:
    """Detect flyovers and convert high/medium-confidence ones to events."""
    result = detect(
        str(path),
        start=start,
        dur=duration,
        p=params or Params(),
        log=log or (lambda _msg: None),
    )
    events: list[EventConfig] = []
    for flyover in result.flyovers:
        if flyover.confidence == "low" or not flyover.refined or not flyover.ranges:
            continue
        payload = flyover.event(name=f"E{len(events) + 1}")
        if not payload:
            continue
        times = None
        freqs = None
        trace = getattr(flyover, "_trace", None)
        if trace:
            times = [float(v) for v in trace[0]]
            harmonic = max(1, round(flyover.f_main / flyover.f0)) if flyover.f0 else 1
            freqs = [float(v) / harmonic for v in trace[1]]
        events.append(
            EventConfig(
                id=len(events) + 1,
                t_heard_s=float(payload["audio_cpa"]),
                f0_hz=float(payload["f0"]),
                velocity_band_mps=(float(payload["speed_ms"][0]), float(payload["speed_ms"][1])),
                slant_band_m=(float(payload["slant_m"][0]), float(payload["slant_m"][1])),
                fit_quality=(FitQuality.PERFECT if flyover.rms < 2.0 else FitQuality.IMPERFECT),
                times_s=times,
                freqs_hz=freqs,
                half_width_s=60.0,
            )
        )
    return events, result
