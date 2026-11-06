"""Command-line interface."""

from __future__ import annotations

import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .audio.detect import detect_ridges
from .audio.fit import fit_pass
from .audio.io import load_audio
from .audio.spectrogram import compute_spectrogram
from .config import TriageMode, load_config
from .demo import run_demo
from .errors import DopplerGeoError
from .flights.chain import resolve_flights
from .geo.dem import ConstantDem, DemChain, DemSource, LocalRasterDem, OpenMeteoDem, UsgsEpqsDem
from .io import write_json
from .pipeline import search
from .triage.rubric import decide as decide_triage
from .triage.video import extract_evidence, load_assessment, probe_media, write_worksheet

app = typer.Typer(add_completion=False, help="High-assurance geolocation from aircraft Doppler signatures.")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"video-location-vaccum {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """video-location-vaccum command group."""


@app.command()
def doctor() -> None:
    """Check the runtime and optional integrations."""
    table = Table(title="video-location-vaccum doctor")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Detail")

    table.add_row("python", "ok", sys.version.split()[0])
    table.add_row("package", "ok", __version__)
    for mod in ("numpy", "scipy", "pandas", "pydantic", "httpx", "yaml"):
        try:
            __import__(mod)
            table.add_row(mod, "ok", "")
        except Exception as exc:
            table.add_row(mod, "missing", str(exc))
    for binary in ("ffmpeg", "ffprobe"):
        path = shutil.which(binary)
        table.add_row(binary, "ok" if path else "missing", path or "")
    for mod, label in (("soundfile", "audio"), ("pyarrow", "parquet"), ("rasterio", "geo"), ("c2pa", "c2pa")):
        try:
            __import__(mod)
            table.add_row(label, "ok", mod)
        except Exception:
            table.add_row(label, "optional", f"{mod} not installed")
    watch = Path.home() / ".config/opencode/skills/claude-video/skills/watch/scripts/watch.py"
    table.add_row(
        "claude-video", "ok" if watch.exists() else "optional", str(watch) if watch.exists() else "not found"
    )
    console.print(table)


@app.command()
def intake(
    out_dir: Path = typer.Option(Path("runs/intake"), help="Where to write the questionnaire."),
) -> None:
    """Print the mandatory pre-analysis questions.

    Nothing is analyzed until these are answered or explicitly marked unknown.
    """
    questions = [
        (
            "goal",
            "What do you need: a precise point, city/region confirmation, authenticity, or leakage defense?",
        ),
        ("precision", "What precision do you require: country, region, city, street, or point?"),
        ("date", "Recording date (YYYY-MM-DD), and is it certain?"),
        ("time", "Recording start time, timezone, and UTC offset. Is it second-level accurate?"),
        ("region", "Any known region, country, city, or bounding box?"),
        ("clues", "Visible clues: landmarks, language, signage, plates, terrain, weather, events."),
        ("audio", "Was the audio edited, music-bedded, denoised, compressed, or recorded on a phone?"),
        ("permission", "Is this your recording, or do you have permission to analyze it?"),
        ("harm", "Is the target a private individual, vulnerable person, shelter, or sensitive site?"),
        ("mode", "Use mode: exploration, publication, forensic, legal, or safety?"),
        ("override", "Force the Doppler pipeline even if visuals are conclusive? (yes/no)"),
        ("data", "Do you have a flight file, DEM, or API credentials? (paths, not secrets)"),
        ("network", "May the tool use the network or scrape public sources? (yes/no)"),
    ]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Pre-analysis intake", "", "Answer these before running any analysis.", ""]
    for key, q in questions:
        lines.append(f"- **{key}**: {q}")
        lines.append("  - answer:")
    (out_dir / "questions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(out_dir / "questions.json", [{"key": k, "question": q} for k, q in questions])
    console.print(f"[green]wrote[/green] {out_dir / 'questions.md'}")
    for key, q in questions:
        console.print(f"[bold]{key}[/bold]: {q}")


@app.command()
def triage(
    media_input: Path = typer.Option(..., "--media", "--video", exists=True, help="Video or audio file."),
    out_dir: Path = typer.Option(Path("runs/triage"), help="Output directory."),
    question: str | None = typer.Option(None, help="What the user wants to know."),
    watch_script: Path | None = typer.Option(None, help="Path to claude-video's watch.py."),
    detail: str = typer.Option("balanced", help="transcript|efficient|balanced|token-burner"),
    resolution: int = typer.Option(1024, help="Frame width."),
    max_frames: int = typer.Option(120, help="Frame cap."),
) -> None:
    """Extract metadata, frames, and transcript; write the evidence worksheet."""
    from .triage.video import VideoEvidence, is_audio, write_audio_worksheet

    media = probe_media(media_input)
    if is_audio(media_input):
        evidence = VideoEvidence(frames=[], report="audio-only", work_dir=out_dir)
        worksheet = write_audio_worksheet(out_dir=out_dir, audio=media_input, media=media, question=question)
    else:
        evidence = extract_evidence(
            media_input,
            out_dir=out_dir,
            question=question,
            watch_script=watch_script,
            detail=detail,
            resolution=resolution,
            max_frames=max_frames,
        )
        worksheet = write_worksheet(
            out_dir=out_dir, video=media_input, media=media, evidence=evidence, question=question
        )
    write_json(out_dir / "media.json", media)
    console.print(f"[green]worksheet[/green] {worksheet}")
    console.print(f"frames: {len(evidence.frames)}  work dir: {evidence.work_dir}")
    for path, t in evidence.frames[:10]:
        console.print(f"  t={t}  {path}")


@app.command()
def signals(
    audio: Path = typer.Option(..., exists=True, help="Audio file."),
    out_dir: Path = typer.Option(Path("runs/signals"), help="Output directory."),
) -> None:
    """Report non-Doppler acoustic clues: metadata, mains hum, tonality, reverb."""
    from dataclasses import asdict

    from .analysis.aircraft import harmonic_analysis
    from .analysis.clues import analyze_audio
    from .audio.io import load_audio

    report = analyze_audio(audio)
    y, sr = load_audio(audio, sr=8000)
    if y.ndim > 1:
        y = y.mean(axis=1)
    aircraft = harmonic_analysis(y, sr)
    payload = {**asdict(report), "aircraft": asdict(aircraft)}
    write_json(out_dir / "signals.json", payload)
    console.print_json(json.dumps(payload, indent=2, default=str))
    console.print("[yellow]These are leads, not location proofs.[/yellow]")


@app.command()
def viability(
    media: Path = typer.Option(..., exists=True, help="Video or audio file."),
    out_dir: Path = typer.Option(Path("runs/viability"), help="Output directory."),
) -> None:
    """Audit whether the acoustic method is feasible for this consumer media."""
    from dataclasses import asdict

    from .analysis.viability import assess_viability

    report = assess_viability(media)
    write_json(out_dir / "viability.json", asdict(report))
    console.print_json(json.dumps(asdict(report), indent=2, default=str))
    console.print(f"[bold]verdict:[/bold] {report.verdict}")


@app.command()
def metadata(
    media: Path = typer.Option(..., exists=True, help="Video or audio file."),
    out_dir: Path = typer.Option(Path("runs/metadata"), help="Output directory."),
) -> None:
    """Extract container, BWF, ID3, EXIF/XMP metadata."""
    from .analysis.metadata import extract_metadata

    report = extract_metadata(media)
    payload = report.to_dict()
    write_json(out_dir / "metadata.json", payload)
    console.print_json(json.dumps(payload, indent=2, default=str))


@app.command()
def sun(
    lat: float = typer.Option(..., help="Latitude."),
    lon: float = typer.Option(..., help="Longitude."),
    time: str = typer.Option(..., help="ISO-8601 date/time (UTC if no offset)."),
    shadow_ratio: float | None = typer.Option(None, help="Observed shadow length / object height."),
) -> None:
    """Solar position and shadow-based latitude band."""
    from .analysis.solar import hour_angle, latitude_band_from_shadow, night_at, solar_position

    dt = datetime.fromisoformat(time.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    az, el, dec = solar_position(lat, lon, dt)
    payload: dict[str, object] = {
        "azimuth_deg": round(az, 2),
        "elevation_deg": round(el, 2),
        "declination_deg": round(dec, 2),
        "night": night_at(lat, lon, dt),
        "shadow_ratio": (None if el <= 1 else round(1.0 / math.tan(math.radians(el)), 3)),
    }
    if shadow_ratio is not None:
        payload["latitude_band_deg"] = [
            round(v, 2) for v in latitude_band_from_shadow(shadow_ratio, dec, hour_angle(dt, lon))
        ]
    console.print_json(json.dumps(payload, indent=2))


@app.command()
def horizon(
    lat: float = typer.Option(..., help="Observer latitude."),
    lon: float = typer.Option(..., help="Observer longitude."),
    azimuth: list[float] = typer.Option([0.0, 90.0, 180.0, 270.0], help="Azimuth(s) in degrees."),
    dem: Path | None = typer.Option(None, exists=True, help="Local DEM GeoTIFF."),
    allow_network: bool = typer.Option(True, help="Allow public DEM point queries."),
) -> None:
    """Terrain horizon profile from a DEM."""
    from dataclasses import asdict

    from .analysis.terrain import horizon_profile
    from .geo.dem import DemChain, LocalRasterDem, OpenMeteoDem, UsgsEpqsDem
    from .geo.dem import DemSource as _DemSource

    sources: list[_DemSource] = []
    if dem is not None:
        sources.append(LocalRasterDem(dem))
    if allow_network:
        sources.extend([UsgsEpqsDem(), OpenMeteoDem()])
    profile = horizon_profile(DemChain(sources), lat, lon, list(azimuth))
    console.print_json(json.dumps([asdict(p) for p in profile], indent=2))


@app.command()
def features(
    lat: float = typer.Option(..., help="Latitude."),
    lon: float = typer.Option(..., help="Longitude."),
    radius_m: float = typer.Option(1000.0, help="Search radius in metres."),
    tag: list[str] = typer.Option([], help="Tag filter, e.g. amenity=school (repeatable)."),
) -> None:
    """Query OpenStreetMap for co-located features (lead generation)."""
    from dataclasses import asdict

    from .analysis.osm import query_features

    filters: dict[str, str] = {}
    for item in tag:
        if "=" not in item:
            raise typer.BadParameter(f"tag must be key=value, got {item!r}")
        key, value = item.split("=", 1)
        filters[key] = value
    if not filters:
        raise typer.BadParameter("provide at least one --tag key=value")
    found = query_features(lat, lon, radius_m, filters)
    console.print_json(json.dumps([asdict(f) for f in found[:20]], indent=2, default=str))


@app.command()
def decide(
    evidence: Path = typer.Option(..., exists=True, help="evidence.json produced from the worksheet."),
    min_confidence: float = typer.Option(0.90, help="Skip threshold."),
    mode: str = typer.Option("auto", help="auto|visual|doppler|forensic"),
    force_pipeline: bool = typer.Option(False, help="Ignore the visual result and run acoustics."),
    ignore_visuals: bool = typer.Option(False, help="Do not use visual evidence at all."),
    force_skip: bool = typer.Option(False, help="Skip despite the rule (not allowed in legal/forensic)."),
) -> None:
    """Apply the evidence rubric and print the skip/run decision."""
    from .config import TriageConfig

    assessment = load_assessment(evidence)
    cfg = TriageConfig(
        mode=TriageMode(mode),
        min_confidence=min_confidence,
        force_pipeline=force_pipeline,
        ignore_visuals=ignore_visuals,
    )
    decision = decide_triage(assessment, cfg, force_skip=force_skip)
    console.print_json(json.dumps(decision.__dict__, indent=2))
    if decision.action == "skip" and decision.allowed_skip:
        console.print(
            "[yellow]Skipping acoustics. This is a visual/text result, not pipeline-verified.[/yellow]"
        )


@app.command()
def events(
    audio: Path | None = typer.Option(None, exists=True, help="Audio/video file."),
    config: Path | None = typer.Option(None, exists=True, help="Run config with input.audio/video."),
    out_dir: Path = typer.Option(Path("runs/events"), help="Output directory."),
    fmin: float = typer.Option(60.0, help="Band low Hz."),
    fmax: float = typer.Option(320.0, help="Band high Hz."),
    threshold_db: float = typer.Option(-30.0, help="Detection threshold."),
    max_tracks: int = typer.Option(4, help="Maximum ridges."),
) -> None:
    """Detect ridges and fit Doppler events."""
    if config is not None:
        cfg = load_config(config)
        source = audio or cfg.input.audio or cfg.input.video
    else:
        source = audio
    if source is None:
        raise typer.BadParameter("provide --audio or --config")
    y, sr = load_audio(source, sr=8000)
    spec = compute_spectrogram(y, sr, nperseg=2048, hop=128, fmin=40, fmax=800)
    ridges = detect_ridges(
        spec,
        fmin=fmin,
        fmax=fmax,
        threshold_db=threshold_db,
        max_slope_hz_s=25.0,
        max_tracks=max_tracks,
        min_duration_s=8.0,
        min_drop_hz=5.0,
    )
    events_out = []
    for i, ridge in enumerate(ridges, start=1):
        try:
            fit = fit_pass(ridge.times, ridge.freqs, c_mps=343.0, height_m=0.0)
            ev = fit.to_event(event_id=i)
            ev = ev.model_copy(update={"times_s": ridge.times.tolist(), "freqs_hz": ridge.freqs.tolist()})
            events_out.append(ev.model_dump())
        except Exception as exc:
            console.print(f"[yellow]ridge {i} fit failed: {exc}[/yellow]")
    write_json(out_dir / "events.json", events_out)
    console.print(f"wrote {len(events_out)} events to [green]{out_dir / 'events.json'}[/green]")


@app.command()
def trace(
    audio: Path = typer.Option(..., exists=True, help="Audio or video file."),
    t0: float = typer.Option(..., help="Window start, seconds."),
    t1: float = typer.Option(..., help="Window end, seconds."),
    fmin: float = typer.Option(70.0, help="Band low Hz."),
    fmax: float = typer.Option(300.0, help="Band high Hz."),
    f_start: float | None = typer.Option(None, help="Pin the ridge near this frequency at the start."),
    f_end: float | None = typer.Option(None, help="Pin the ridge near this frequency at the end."),
    harmonic: int = typer.Option(1, help="Harmonic number of the traced curve."),
    line_s: float = typer.Option(0.0, help="Suppress steady tones over this many seconds."),
    min_z: float = typer.Option(1.0, help="Minimum whitened brightness for the trace."),
    out: Path = typer.Option(Path("runs/trace"), help="Output directory."),
) -> None:
    """Trace one visible Doppler ridge and fit a flyby. Use when auto-detect fails."""
    from .audio.trace import trace_ridge

    y, sr = load_audio(audio, sr=8000)
    a, b = max(0, int(t0 * sr)), min(y.size, int(t1 * sr))
    spec = compute_spectrogram(y[a:b], sr, nperseg=4096, hop=128, fmin=40, fmax=800)
    spec = spec.whiten(line_s=line_s)
    mask = (spec.freqs >= fmin) & (spec.freqs <= fmax)
    from .audio.spectrogram import Spectrogram

    band = Spectrogram(spec.db[mask], spec.freqs[mask], spec.times + t0, sr, spec.nperseg, spec.hop)
    tr = trace_ridge(band, f_start=f_start, f_end=f_end, min_z=min_z)
    if tr.times.size < 10:
        raise typer.BadParameter("ridge too short; adjust the window or the start/end pins")
    fit = fit_pass(tr.times, tr.freqs / harmonic, c_mps=343.0, height_m=0.0)
    event = fit.to_event(event_id=1)
    out.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        out / "trace.csv",
        np.c_[tr.times, tr.freqs, tr.score],
        delimiter=",",
        header="t,f,z",
        comments="",
    )
    write_json(
        out / "fit.json",
        {
            "f0_hz": fit.pass_.f0_hz,
            "speed_mps": fit.pass_.speed_mps,
            "slant_m": fit.pass_.cpa_horizontal_m,
            "t_cpa_s": fit.pass_.cpa_time_s,
            "rmse_hz": fit.rmse_hz,
            "event": event.model_dump(mode="json"),
        },
    )
    console.print(
        f"points={tr.times.size} f0={fit.pass_.f0_hz:.3f} Hz "
        f"v={fit.pass_.speed_mps:.1f} m/s d={fit.pass_.cpa_horizontal_m:.0f} m "
        f"rmse={fit.rmse_hz:.2f} Hz"
    )
    console.print(f"wrote {out / 'trace.csv'} and {out / 'fit.json'}")


@app.command()
def auto(
    audio: Path = typer.Option(..., exists=True, help="Audio or video file."),
    start: float = typer.Option(0.0, help="Start offset in seconds."),
    duration: float | None = typer.Option(None, help="Length to scan in seconds."),
    out: Path = typer.Option(Path("runs/auto"), help="Output directory."),
) -> None:
    """Automatically detect flyovers with the vendored matched-filter detector."""
    from .audio.auto import detect_events

    events, result = detect_events(
        audio,
        start=start,
        duration=duration,
        log=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "events.json", [e.model_dump(mode="json") for e in events])
    write_json(
        out / "flyovers.json",
        [
            {
                "confidence": f.confidence,
                "t_cpa": f.t_cpa,
                "f0": f.f0,
                "speed": f.v,
                "slant": f.d,
                "rms": f.rms,
                "harmonics": f.harmonics,
            }
            for f in result.flyovers
        ],
    )
    console.print(
        f"[green]{len(events)} usable events[/green] from "
        f"{len(result.flyovers)} flyovers; wrote {out / 'events.json'}"
    )
    for event in events:
        console.print(
            f"  E{event.id} t={event.t_heard_s:.2f}s f0={event.f0_hz:.3f}Hz "
            f"v={event.velocity_band_mps} slant={event.slant_band_m}"
        )


@app.command()
def run(
    config: Path = typer.Option(..., exists=True, help="Run config YAML."),
    out_dir: Path | None = typer.Option(None, help="Override output directory."),
) -> None:
    """Run the acoustic search described by a config."""
    cfg = load_config(config)
    if cfg.search is None:
        raise typer.BadParameter("config has no search section")
    if not cfg.events:
        raise typer.BadParameter("config has no events; run 'video-location-vaccum events' first")
    source = cfg.input.audio or cfg.input.video
    if source is None:
        raise typer.BadParameter("config has no input.audio/video")
    y, sr = load_audio(source, sr=8000)
    spec = compute_spectrogram(y, sr, nperseg=2048, hop=128, fmin=40, fmax=800)

    sources: list[DemSource] = []
    if cfg.dem.user_file is not None:
        sources.append(LocalRasterDem(cfg.dem.user_file))
    if cfg.dem.allow_network:
        sources.extend([UsgsEpqsDem(), OpenMeteoDem()])
    if cfg.dem.allow_flat_fallback:
        sources.append(ConstantDem(cfg.dem.flat_height_m))
    dem = DemChain(sources, allow_flat=cfg.dem.allow_flat_fallback)

    results = search(
        search_cfg=cfg.search,
        events=cfg.events,
        spec=spec,
        flights=resolve_flights(
            cfg.flights, region=cfg.search.region, days=cfg.search.dates, type_filter=cfg.search.type_filter
        ),
        dem=dem,
    )
    target = out_dir or cfg.output_dir
    payload = {
        "config": cfg.model_dump(mode="json"),
        "input": str(source),
        "event_count": len(cfg.events),
        "candidates": [r.to_dict() for r in results],
    }
    write_json(target / "report.json", payload)
    if results:
        top = results[0]
        console.print(
            f"[green]best[/green] {top.lat:.6f}, {top.lon:.6f} score={top.score:.6f} "
            f"dt={top.dt_s:.2f}s offset={top.offset_s:.2f}s"
        )
    else:
        console.print("[yellow]no candidate matched the constraints[/yellow]")


@app.command()
def leakage(
    audio: Path = typer.Option(..., exists=True, help="Audio or video file."),
    out_dir: Path = typer.Option(Path("runs/leakage"), help="Output directory."),
) -> None:
    """Report whether the recording contains a usable Doppler signature."""
    from .defense.leakage import analyze_leakage

    report = analyze_leakage(audio)
    payload = report.to_dict()
    write_json(out_dir / "leakage.json", payload)
    console.print_json(json.dumps(payload, indent=2, default=str))
    console.print(f"[bold]risk:[/bold] {report.risk}")


@app.command()
def defend(
    audio: Path = typer.Option(..., exists=True, help="Audio or video file."),
    out: Path = typer.Option(..., help="Output WAV path."),
    mode: str = typer.Option("notch", help="notch|cut|mask|decoy"),
    event_index: int | None = typer.Option(None, help="Only process this event index."),
    width_hz: float = typer.Option(10.0, help="Notch half-width in Hz."),
    snr_db: float = typer.Option(12.0, help="Masking-noise SNR."),
    decoys: int = typer.Option(2, help="Number of synthetic curves for mode=decoy."),
    i_understand: bool = typer.Option(
        False, "--i-understand", help="Required for decoys: acknowledges the file is altered."
    ),
) -> None:
    """Remove, mask, or decoy Doppler signatures in your own recording."""
    from .defense.sanitize import sanitize_file

    if mode == "decoy" and not i_understand:
        raise typer.BadParameter(
            "decoy mode fabricates signatures; pass --i-understand and keep the manifest"
        )
    result = sanitize_file(
        audio,
        out,
        mode=mode,
        event_index=event_index,
        width_hz=width_hz,
        snr_db=snr_db,
        decoys=decoys,
    )
    console.print_json(json.dumps(result.manifest, indent=2, default=str))
    console.print(
        "[yellow]Altered file. Keep the .transform.json manifest; do not present it as an original.[/yellow]"
    )


@app.command()
def demo(
    out_dir: Path = typer.Option(Path("runs/demo"), help="Output directory."),
    detected: bool = typer.Option(True, help="Use detected ridges (false = truth events)."),
) -> None:
    """Run the synthetic end-to-end validation."""
    result = run_demo(out_dir, use_detected=detected)
    console.print_json(
        json.dumps(
            {
                "truth": result["truth"],
                "best": result["best"],
                "error_m": result["error_m"],
                "ridges": result["ridges"],
            },
            indent=2,
            default=str,
        )
    )


def entrypoint() -> None:
    try:
        app()
    except DopplerGeoError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(2) from exc


if __name__ == "__main__":
    entrypoint()
