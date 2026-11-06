"""Synthetic end-to-end demo and regression fixture.

Builds a known observer, two straight passes, and the audio those passes would
produce. The search must recover the observer's cell from the audio and tracks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .audio.detect import detect_ridges
from .audio.fit import fit_pass
from .audio.spectrogram import compute_spectrogram
from .config import EventConfig, RegionConfig, SearchConfig
from .flights.synthetic import straight_pass
from .flights.types import Flight
from .geo.dem import ConstantDem, DemChain
from .geo.geodesy import LocalFrame, destination_point
from .model.doppler import StraightLinePass
from .pipeline import search
from .score.brightness import frequency_from_vr, radial_curve


@dataclass
class Scene:
    lat: float
    lon: float
    elevation_m: float
    flights: list[Flight]
    audio: np.ndarray
    sr: int
    cpa_times_s: tuple[float, float]
    truth_passes: list[StraightLinePass]


def build_scene(
    *,
    lat: float = 39.7000,
    lon: float = -105.0000,
    elevation_m: float = 1600.0,
    sr: int = 8000,
    duration_s: float = 520.0,
) -> Scene:
    """Two straight passes crossing near the observer at different azimuths."""
    c = 343.0
    frame = LocalFrame(lat, lon, elevation_m)

    # Flight A: eastbound, CPA at t=120 s, 1200 m north of the observer.
    a_speed = 90.0
    a_t0 = 120.0
    a_lat, a_lon = destination_point(lat, lon, 0.0, 1200.0)
    a_start_lat, a_start_lon = destination_point(a_lat, a_lon, 270.0, a_speed * a_t0)
    flight_a = straight_pass(
        start_lat=a_start_lat,
        start_lon=a_start_lon,
        bearing_deg=90.0,
        speed_mps=a_speed,
        altitude_m=elevation_m + 800.0,
        t0_s=0.0,
        duration_s=duration_s,
        flight_id="A",
        sample_hz=1.0,
    )

    # Flight B: northbound, CPA at t=430 s, 900 m east of the observer.
    b_speed = 85.0
    b_t0 = 430.0
    b_lat, b_lon = destination_point(lat, lon, 90.0, 900.0)
    b_start_lat, b_start_lon = destination_point(b_lat, b_lon, 180.0, b_speed * b_t0)
    flight_b = straight_pass(
        start_lat=b_start_lat,
        start_lon=b_start_lon,
        bearing_deg=0.0,
        speed_mps=b_speed,
        altitude_m=elevation_m + 700.0,
        t0_s=0.0,
        duration_s=duration_s,
        flight_id="B",
        sample_hz=1.0,
    )

    n = int(duration_s * sr)
    t = np.arange(n, dtype=float) / sr
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    audio = np.zeros(n, dtype=float)
    for flight, t0 in ((flight_a, a_t0), (flight_b, b_t0)):
        vr = radial_curve(track=flight.track, frame=frame, c_mps=c, t_listen_s=epoch + t)
        f = frequency_from_vr(140.0, c, vr)
        f = np.where(np.isfinite(f), f, 140.0)
        amp = np.exp(-0.5 * ((t - (t0 + 5.0)) / 35.0) ** 2)
        phase = 2.0 * np.pi * np.cumsum(f) / sr
        audio += 0.35 * amp * np.sin(phase)
    rng = np.random.default_rng(3)
    audio += rng.normal(0.0, 0.01, n)
    passes = [
        StraightLinePass(
            f0_hz=140.0, speed_mps=a_speed, cpa_horizontal_m=1200.0, cpa_time_s=a_t0, height_m=800.0
        ),
        StraightLinePass(
            f0_hz=140.0, speed_mps=b_speed, cpa_horizontal_m=900.0, cpa_time_s=b_t0, height_m=700.0
        ),
    ]
    return Scene(lat, lon, elevation_m, [flight_a, flight_b], audio, sr, (a_t0, b_t0), passes)


def run_demo(out_dir: Path, *, use_detected: bool = True, known_start: bool = True) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = build_scene()

    import soundfile as sf

    wav = out_dir / "synthetic.wav"
    sf.write(wav, scene.audio, scene.sr)

    spec = compute_spectrogram(scene.audio, scene.sr, nperseg=2048, hop=128, fmin=60, fmax=400)
    ridges = detect_ridges(spec, fmin=60, fmax=320, threshold_db=-30.0, max_slope_hz_s=4.0, max_tracks=4)
    if use_detected and len(ridges) < 2:
        raise RuntimeError(f"demo expected 2 ridges, found {len(ridges)}")

    events: list[EventConfig] = []
    if use_detected:
        for i, ridge in enumerate(ridges[:2], start=1):
            fit = fit_pass(
                ridge.times,
                ridge.freqs,
                c_mps=343.0,
                height_m=750.0,
                f0_guess=float(np.median(ridge.freqs)),
            )
            events.append(
                fit.to_event(event_id=i).model_copy(
                    update={
                        "times_s": ridge.times.tolist(),
                        "freqs_hz": ridge.freqs.tolist(),
                    }
                )
            )
    else:
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
        frame = LocalFrame(scene.lat, scene.lon, scene.elevation_m)
        for i, (flight, t0) in enumerate(zip(scene.flights, scene.cpa_times_s, strict=True), start=1):
            times = np.arange(t0 - 90.0, t0 + 90.0, 0.5)
            vr = radial_curve(track=flight.track, frame=frame, c_mps=343.0, t_listen_s=epoch + times)
            freqs = frequency_from_vr(140.0, 343.0, vr)
            truth = scene.truth_passes[i - 1]
            slant = float(np.hypot(truth.cpa_horizontal_m, truth.height_m))
            events.append(
                EventConfig(
                    id=i,
                    t_heard_s=truth.cpa_time_s + slant / 343.0,
                    f0_hz=140.0,
                    times_s=times.tolist(),
                    freqs_hz=freqs.tolist(),
                )
            )

    # Search a 4 km box around the true point at 200 m, then refine.
    dlat = 2000.0 / 111_320.0
    dlon = 2000.0 / (111_320.0 * np.cos(np.radians(scene.lat)))
    region = RegionConfig(
        min_lat=scene.lat - dlat,
        max_lat=scene.lat + dlat,
        min_lon=scene.lon - dlon,
        max_lon=scene.lon + dlon,
    )
    search_cfg = SearchConfig(
        region=region,
        date=datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
        t_start_epoch_s=(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() if known_start else None),
        r_audible_m=10_000.0,
        grid_step_m=200.0,
        refine_step_m=100.0,
        dt_tol_s=8.0,
        sweep_t_s=6.0,
        sweep_f0_pct=8.0,
        apply_bands=False,
    )
    results = search(
        search_cfg=search_cfg,
        events=events,
        spec=spec,
        flights=scene.flights,
        dem=DemChain([ConstantDem(scene.elevation_m)]),
        refine_top=3,
    )
    if not results:
        raise RuntimeError("demo search returned no candidates")

    best = results[0]
    err_m = float(
        np.hypot(
            (best.lat - scene.lat) * 111_320.0,
            (best.lon - scene.lon) * 111_320.0 * np.cos(np.radians(scene.lat)),
        )
    )
    payload = {
        "truth": {"lat": scene.lat, "lon": scene.lon, "elevation_m": scene.elevation_m},
        "events": [e.model_dump() for e in events],
        "best": best.to_dict(),
        "error_m": err_m,
        "ridges": [
            {
                "start_s": float(r.times[0]),
                "end_s": float(r.times[-1]),
                "drop_hz": r.drop_hz,
                "snr_db": r.snr_db,
            }
            for r in ridges
        ],
        "top5": [r.to_dict() for r in results[:5]],
    }
    (out_dir / "demo-report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
