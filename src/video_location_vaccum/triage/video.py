"""Evidence extraction: media metadata, hashes, and claude-video frames."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ..errors import DataUnavailable
from .rubric import (
    EvidenceItem,
    EvidenceKind,
    Gate,
    GateResult,
    PrecisionBucket,
    TriageAssessment,
    UseMode,
)

_FRAME_RE = re.compile(r"- `([^`]+\.(?:jpg|jpeg|png))` \(t=([0-9:]+)")

AUDIO_SUFFIXES = {
    ".wav",
    ".flac",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".aiff",
    ".aif",
}


def is_audio(path: Path) -> bool:
    return Path(path).suffix.lower() in AUDIO_SUFFIXES


@dataclass
class VideoEvidence:
    frames: list[tuple[Path, str]]
    report: str
    work_dir: Path


def find_watch_script(explicit: Path | None = None) -> Path:
    candidates = []
    if explicit is not None:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            Path.home() / ".config/opencode/skills/claude-video/skills/watch/scripts/watch.py",
            Path.home() / ".claude/skills/claude-video/skills/watch/scripts/watch.py",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise DataUnavailable(
        "claude-video's watch script was not found",
        tried=[str(c) for c in candidates],
        ask="clone https://github.com/bradautomates/claude-video and pass --watch-script",
    )


def probe_media(path: Path) -> dict:
    """Container/stream metadata plus a SHA-256 of the exact bytes."""
    from .provenance import provenance_report

    path = Path(path)
    if not path.exists():
        raise DataUnavailable(f"media not found: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    info: dict = {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": digest,
        "ffprobe": None,
        "provenance": provenance_report(path),
    }
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                capture_output=True,
                check=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            info["ffprobe"] = json.loads(out.stdout)
        except Exception as exc:
            info["ffprobe_error"] = str(exc)
    return info


def extract_evidence(
    video: Path,
    *,
    out_dir: Path,
    question: str | None = None,
    watch_script: Path | None = None,
    detail: str = "balanced",
    resolution: int = 1024,
    max_frames: int = 120,
    timestamps: list[str] | None = None,
) -> VideoEvidence:
    """Run claude-video's watch tool and return its frames and report."""
    script = find_watch_script(watch_script)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(script),
        str(video),
        "--detail",
        detail,
        "--resolution",
        str(resolution),
        "--max-frames",
        str(max_frames),
        "--out-dir",
        str(out_dir),
    ]
    if question:
        cmd.extend(["--question", question])
    if timestamps:
        cmd.extend(["--timestamps", ",".join(timestamps)])
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = (proc.stdout or "") + (proc.stderr or "")
    frames: list[tuple[Path, str]] = []
    for line in report.splitlines():
        m = _FRAME_RE.search(line)
        if m:
            frames.append((Path(m.group(1)), m.group(2)))
    work_dir = out_dir
    for line in report.splitlines():
        if "working dir:" in line:
            work_dir = Path(line.split("working dir:", 1)[1].strip().splitlines()[0])
            break
    if proc.returncode not in (0, 1) and not frames:
        raise DataUnavailable(
            "claude-video failed to extract evidence",
            tried=[str(script)],
            ask="check the video path and ffmpeg/yt-dlp availability",
        )
    return VideoEvidence(frames=frames, report=report, work_dir=work_dir)


def write_worksheet(
    *,
    out_dir: Path,
    video: Path,
    media: dict,
    evidence: VideoEvidence,
    question: str | None,
) -> Path:
    """Write the human/agent worksheet that is filled before any search."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "triage-worksheet.md"
    lines = [
        "# Triage worksheet",
        "",
        "Fill `evidence.json` from this worksheet, then run `video-location-vaccum decide`.",
        "Do not run the acoustic pipeline until the decision is recorded.",
        "",
        "## Media",
        "",
        f"- Path: `{video}`",
        f"- SHA-256: `{media.get('sha256')}`",
        f"- Size: {media.get('size_bytes')} bytes",
        f"- Question: {question or '(none)'}",
        "",
        "## Frames to inspect",
        "",
    ]
    if evidence.frames:
        for p, t in evidence.frames:
            lines.append(f"- [ ] t={t} — `{p}`")
    else:
        lines.append("- No frames were produced (transcript-only run or Gemini engine).")
    lines.extend(
        [
            "",
            "## Evidence checklist",
            "",
            "- [ ] Unique landmark(s): name, geometry, at least two viewpoints",
            "- [ ] Micro-cues: signage, language, plates, markings, utility hardware",
            "- [ ] Reference imagery: source, resolution, **date**, match quality",
            "- [ ] Terrain/skyline: quantitative profile, not just 'looks similar'",
            "- [ ] Chronolocation: date/time, shadow direction/length, sun angle",
            "- [ ] Independent corroboration (a genuinely separate source)",
            "- [ ] Source reliability and motive",
            "- [ ] Disconfirmation: at least one plausible alternative eliminated",
            "- [ ] Metadata: creation time, GPS, device; record whether it contradicts",
            "- [ ] Replicas/lookalikes: documented alternatives excluded",
            "",
            "## Red flags (any ⇒ do not skip)",
            "",
            "- Single distinctive cue, no second independent cue",
            "- Landmark with known replicas not excluded",
            "- Reference imagery undated",
            "- All 'sources' trace to one original upload",
            "- Metadata stripped or inconsistent with pixels",
            "- Game-engine / film-set / staged-scene indicators",
            "- Audio replaced, music-bedded, clipped, or heavily denoised",
            "",
            "## Decision",
            "",
            "Run: `video-location-vaccum decide --evidence evidence.json`",
            "Override: `--force-pipeline` or `--ignore-visuals`.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_audio_worksheet(*, out_dir: Path, audio: Path, media: dict, question: str | None) -> Path:
    """Audio-only worksheet: metadata, acoustic clues, no visual claims."""
    from ..analysis.clues import analyze_audio

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        clues = analyze_audio(audio)
        hum = clues.hum
        clue_lines = [
            f"- Mains hum: 50 Hz {hum.hz_50_db:.1f} dB, 60 Hz {hum.hz_60_db:.1f} dB — {hum.hint}",
            f"- Tonal peaks (Hz): {', '.join(f'{p:.1f}' for p in clues.tonal_peaks_hz) or 'none'}",
            f"- Reverb estimate: {clues.reverb_rt60_s if clues.reverb_rt60_s else 'n/a'} s "
            f"({clues.reverb_confidence} confidence)",
            f"- Dynamic range: {clues.dynamic_range_db:.1f} dB; clipping: {clues.clipping_fraction:.4f}",
        ]
    except Exception as exc:
        clue_lines = [f"- Acoustic clue extraction failed: {exc}"]

    path = out_dir / "triage-worksheet.md"
    lines = [
        "# Audio-only triage worksheet",
        "",
        "No visual triage is possible. Treat every clue as a lead, then run the",
        "acoustic pipeline. If a video exists, use video mode instead.",
        "",
        "## Media",
        "",
        f"- Path: `{audio}`",
        f"- SHA-256: `{media.get('sha256')}`",
        f"- Size: {media.get('size_bytes')} bytes",
        f"- Question: {question or '(none)'}",
        "",
        "## Acoustic clues",
        "",
        *clue_lines,
        "",
        "## Checklist",
        "",
        "- [ ] Speech language / accent (needs an ASR or a human listener)",
        "- [ ] Mains hum: 50 vs 60 Hz, harmonic strength",
        "- [ ] Reverb / room size; indoor vs outdoor",
        "- [ ] Wildlife, insects, birds, weather",
        "- [ ] Church bells, sirens, school bells, transport",
        "- [ ] Aircraft type: prop vs jet, blade-pass harmonics",
        "- [ ] Music / broadcast audio: station or track identification",
        "- [ ] Cuts, fades, denoising, music beds, codec artifacts",
        "- [ ] Embedded metadata: ID3, RIFF INFO, BWF bext, iXML, XMP",
        "- [ ] File naming, upload time, platform identifiers (context only)",
        "",
        "## Next",
        "",
        "```bash",
        f"video-location-vaccum signals --audio {audio} --out-dir {out_dir}",
        f"video-location-vaccum events --audio {audio} --out-dir {out_dir}",
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_assessment(path: Path) -> TriageAssessment:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    evidence = [
        EvidenceItem(
            kind=EvidenceKind(item["kind"]),
            score=float(item.get("score", 0.0)),
            note=str(item.get("note", "")),
            independent=bool(item.get("independent", True)),
        )
        for item in data.get("evidence", [])
    ]
    gates = {Gate(k): GateResult(v) for k, v in data.get("gates", {}).items()}
    return TriageAssessment(
        claim_place=str(data.get("claim_place", "")),
        precision=PrecisionBucket(data.get("precision", "city")),
        requested_precision=PrecisionBucket(data.get("requested_precision", "city")),
        mode=UseMode(data.get("mode", "exploration")),
        evidence=evidence,
        gates=gates,
        candidates_examined=int(data.get("candidates_examined", 0)),
        target_is_private_individual=bool(data.get("target_is_private_individual", False)),
        authenticity_disputed=bool(data.get("authenticity_disputed", False)),
        ai_geolocator_sole_basis=bool(data.get("ai_geolocator_sole_basis", False)),
        reference_imagery_undated=bool(data.get("reference_imagery_undated", False)),
        landmark_replicas_not_excluded=bool(data.get("landmark_replicas_not_excluded", False)),
        has_cross_source=bool(data.get("has_cross_source", False)),
        rubric_version=str(data.get("rubric_version", "1.0")),
    )
