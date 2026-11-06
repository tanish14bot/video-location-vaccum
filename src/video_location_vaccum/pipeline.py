"""End-to-end search pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .audio.spectrogram import Spectrogram
from .config import EventConfig, SearchConfig
from .flights.types import Flight
from .geo.dem import DemChain
from .geo.geodesy import LocalFrame
from .geo.grid import CandidatePair, make_grid, offset_pairs
from .score.locked import EventObservation, sweep_locked


@dataclass
class CandidateResult:
    lat: float
    lon: float
    flight_a: str
    flight_b: str
    score: float
    score_a: float
    score_b: float
    dt_s: float
    f0_a: float
    f0_b: float
    coverage_a: float
    coverage_b: float
    offset_s: float

    def to_dict(self) -> dict:
        return asdict(self)


def _event_observation(
    event: EventConfig,
    spec: Spectrogram,
    *,
    t_offset_s: float = 0.0,
    window_s: float | None = None,
    max_points: int = 150,
) -> EventObservation:
    if window_s is None:
        window_s = event.half_width_s
    if event.times_s and event.freqs_hz:
        times_all = np.asarray(event.times_s, dtype=float)
        freqs_all = np.asarray(event.freqs_hz, dtype=float)
        if times_all.size != freqs_all.size:
            raise ValueError(f"event {event.id}: times_s and freqs_hz must have equal length")
        if times_all.size > max_points:
            idx = np.linspace(0, times_all.size - 1, max_points).astype(int)
            times = times_all[idx]
            freqs = freqs_all[idx]
        else:
            times = times_all
            freqs = freqs_all
        return EventObservation(
            times_s=times,
            f0_hz=event.f0_hz,
            track_times_s=times + t_offset_s,
            freqs_hz=freqs,
        )
    lo = max(float(spec.times[0]), event.t_heard_s - window_s)
    hi = min(float(spec.times[-1]), event.t_heard_s + window_s)
    if hi <= lo:
        raise ValueError(f"event {event.id} lies outside the spectrogram time base")
    times = np.arange(lo, hi, max(0.5, (hi - lo) / 80.0))
    return EventObservation(times_s=times, f0_hz=event.f0_hz, track_times_s=times + t_offset_s)


def _score_pair(
    pair: CandidatePair,
    *,
    spec: Spectrogram,
    events: list[EventConfig],
    by_id: dict[str, Flight],
    dem: DemChain,
    c_mps: float,
    sweep_t_s: float,
    sweep_f0_pct: float,
    t_offset_s: float | None = None,
) -> CandidateResult:
    elev = float(dem.elevation(pair.lat, pair.lon).height_m)
    frame = LocalFrame(pair.lat, pair.lon, elev)

    # If the recording start is unknown, each candidate defines its own clock:
    # align Event 1 to the earlier delayed CPA, then test whether Event 2 lands
    # at the measured offset. This is the absolute-time-free dual-event method.
    if t_offset_s is None:
        if pair.cpa_a.delayed_s <= pair.cpa_b.delayed_s:
            early_id, late_id = pair.flight_a, pair.flight_b
            early_delayed = pair.cpa_a.delayed_s
        else:
            early_id, late_id = pair.flight_b, pair.flight_a
            early_delayed = pair.cpa_b.delayed_s
        offset = early_delayed - events[0].t_heard_s
        track_a = by_id[early_id].track
        track_b = by_id[late_id].track
    else:
        offset = t_offset_s
        track_a = by_id[pair.flight_a].track
        track_b = by_id[pair.flight_b].track

    obs_a = _event_observation(events[0], spec, t_offset_s=offset)
    obs_b = _event_observation(events[1], spec, t_offset_s=offset)
    score = sweep_locked(
        spec,
        track_a=track_a,
        track_b=track_b,
        frame=frame,
        obs_a=obs_a,
        obs_b=obs_b,
        c_mps=c_mps,
        sweep_t_s=sweep_t_s,
        sweep_f0_pct=sweep_f0_pct,
    )
    return CandidateResult(
        lat=pair.lat,
        lon=pair.lon,
        flight_a=pair.flight_a,
        flight_b=pair.flight_b,
        score=score.score,
        score_a=score.score_a,
        score_b=score.score_b,
        dt_s=score.dt_s,
        f0_a=score.f0_a,
        f0_b=score.f0_b,
        coverage_a=score.coverage_a,
        coverage_b=score.coverage_b,
        offset_s=pair.delta_s,
    )


def search(
    *,
    search_cfg: SearchConfig,
    events: list[EventConfig],
    spec: Spectrogram,
    flights: list[Flight],
    dem: DemChain,
    max_flights: int = 500,
    refine_top: int = 5,
) -> list[CandidateResult]:
    """Run the coarse search, score candidates, then refine the best cells."""
    if len(events) < 2:
        raise ValueError("dual-event search needs at least two measured events")
    events = sorted(events, key=lambda e: e.t_heard_s)
    if not flights:
        raise ValueError("no flights supplied")

    if len(flights) > max_flights:
        raise ValueError(
            f"{len(flights)} flights is more than max_flights={max_flights}; "
            "narrow the region/date or filter the flight file first"
        )
    flights = flights[:max_flights]
    by_id = {f.flight_id: f for f in flights}
    grid = make_grid(search_cfg.region, search_cfg.grid_step_m)
    dt_target = abs(events[1].t_heard_s - events[0].t_heard_s)

    # shortcut: all flight pairs are evaluated. Filter the flight file for
    # continent-scale areas; a central-CPA prefilter drops true pairs when an
    # aircraft has multiple passes in one day.
    pairs = offset_pairs(
        grid=grid,
        dem=dem,
        flights=flights,
        dt_s=dt_target,
        dt_tol_s=search_cfg.dt_tol_s,
        c_mps=search_cfg.c_mps,
        max_pairs=search_cfg.max_candidates,
        slant_bands=[e.slant_band_m for e in events] if search_cfg.apply_bands else None,
        velocity_bands=[e.velocity_band_mps for e in events] if search_cfg.apply_bands else None,
    )
    if not pairs:
        return []

    # Deduplicate (point, flight-pair) keys while preserving the best offset.
    unique: dict[tuple[int, str, str], CandidatePair] = {}
    for pair in pairs:
        key = (pair.point_index, pair.flight_a, pair.flight_b)
        if key not in unique:
            unique[key] = pair
    candidates = list(unique.values())

    results: list[CandidateResult] = []
    for pair in candidates:
        try:
            results.append(
                _score_pair(
                    pair,
                    spec=spec,
                    events=events,
                    by_id=by_id,
                    dem=dem,
                    c_mps=search_cfg.c_mps,
                    sweep_t_s=search_cfg.sweep_t_s,
                    sweep_f0_pct=search_cfg.sweep_f0_pct,
                    t_offset_s=search_cfg.t_start_epoch_s,
                )
            )
        except Exception:
            continue
    results.sort(key=lambda r: r.score, reverse=True)

    # Refine the best cells on a finer grid around each winner.
    refined: list[CandidateResult] = []
    for res in results[:refine_top]:
        refined.extend(
            _refine(
                res,
                search_cfg=search_cfg,
                events=events,
                spec=spec,
                by_id=by_id,
                dem=dem,
            )
        )
    combined = refined + results[refine_top:]
    combined.sort(key=lambda r: r.score, reverse=True)
    return combined


def _refine(
    base: CandidateResult,
    *,
    search_cfg: SearchConfig,
    events: list[EventConfig],
    spec: Spectrogram,
    by_id: dict[str, Flight],
    dem: DemChain,
) -> list[CandidateResult]:
    from .config import RegionConfig

    step = search_cfg.refine_step_m
    half = search_cfg.grid_step_m
    dlat = half / 111_320.0
    dlon = half / (111_320.0 * max(0.05, np.cos(np.radians(base.lat))))
    region = RegionConfig(
        min_lat=base.lat - dlat,
        max_lat=base.lat + dlat,
        min_lon=base.lon - dlon,
        max_lon=base.lon + dlon,
    )
    grid = make_grid(region, step)
    pairs = offset_pairs(
        grid=grid,
        dem=dem,
        flights=[by_id[base.flight_a], by_id[base.flight_b]],
        dt_s=abs(events[1].t_heard_s - events[0].t_heard_s),
        dt_tol_s=search_cfg.dt_tol_s,
        c_mps=search_cfg.c_mps,
    )
    out: list[CandidateResult] = []
    for pair in pairs:
        try:
            out.append(
                _score_pair(
                    pair,
                    spec=spec,
                    events=events,
                    by_id=by_id,
                    dem=dem,
                    c_mps=search_cfg.c_mps,
                    sweep_t_s=search_cfg.sweep_t_s,
                    sweep_f0_pct=search_cfg.sweep_f0_pct,
                    t_offset_s=search_cfg.t_start_epoch_s,
                )
            )
        except Exception:
            continue
    out.sort(key=lambda r: r.score, reverse=True)
    return out[:1] if out else []
