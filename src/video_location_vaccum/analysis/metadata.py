"""Metadata extraction: container, BWF, ID3, EXIF/XMP when available."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MetadataReport:
    tags: dict[str, Any] = field(default_factory=dict)
    gps: tuple[float, float] | None = None
    datetime_utc: str | None = None
    device: str | None = None
    software: str | None = None
    bwf: dict[str, Any] | None = None
    id3: dict[str, Any] | None = None
    sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tags": self.tags,
            "gps": self.gps,
            "datetime_utc": self.datetime_utc,
            "device": self.device,
            "software": self.software,
            "bwf": self.bwf,
            "id3": self.id3,
            "sources": self.sources,
            "notes": self.notes,
        }


def _ffprobe(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return json.loads(out.stdout)
    except Exception:
        return {}


def _riff_chunks(path: Path) -> dict[bytes, bytes]:
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF":
        return {}
    chunks: dict[bytes, bytes] = {}
    pos = 12
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        chunk = data[pos + 8 : pos + 8 + size]
        chunks[cid] = chunk
        pos += 8 + size + (size % 2)
    return chunks


def parse_bext(data: bytes) -> dict[str, Any]:
    """Parse a BWF ``bext`` chunk (602 bytes in the common version)."""

    def text(start: int, length: int) -> str:
        return data[start : start + length].decode("ascii", "replace").strip("\x00 ").strip()

    out: dict[str, Any] = {
        "description": text(0, 256),
        "originator": text(256, 32),
        "originator_reference": text(288, 32),
        "origination_date": text(320, 10),
        "origination_time": text(330, 8),
    }
    if len(data) >= 346:
        out["time_reference"] = struct.unpack("<Q", data[338:346])[0]
    if len(data) >= 348:
        out["version"] = struct.unpack("<H", data[346:348])[0]
    if len(data) >= 412:
        out["umid"] = data[348:412].hex()
    return out


def _mutagen_tags(path: Path) -> dict[str, Any] | None:
    try:
        from mutagen import File as MutagenFile
    except Exception:
        return None
    try:
        audio = MutagenFile(str(path))
        if audio is None or audio.tags is None:
            return None
        out: dict[str, Any] = {}
        for key, value in audio.tags.items():
            out[str(key)] = str(value)
        return out
    except Exception:
        return None


def _exiftool(path: Path) -> dict[str, Any] | None:
    tool = shutil.which("exiftool")
    if not tool:
        return None
    try:
        out = subprocess.run(
            [tool, "-json", "-n", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        parsed = json.loads(out.stdout)
        return parsed[0] if parsed else None
    except Exception:
        return None


def _first(tags: dict[str, Any], keys: list[str]) -> str | None:
    lowered = {str(k).lower(): v for k, v in tags.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return str(value)
    return None


def extract_metadata(path: Path) -> MetadataReport:
    report = MetadataReport()
    probe = _ffprobe(path)
    tags: dict[str, Any] = {}
    if probe:
        report.sources.append("ffprobe")
        tags.update(probe.get("format", {}).get("tags", {}) or {})
        for stream in probe.get("streams", []):
            tags.update(stream.get("tags", {}) or {})

    if path.suffix.lower() == ".wav":
        chunks = _riff_chunks(path)
        if b"bext" in chunks:
            report.bwf = parse_bext(chunks[b"bext"])
            report.sources.append("bwf-bext")

    id3 = _mutagen_tags(path)
    if id3:
        report.id3 = id3
        report.sources.append("mutagen")
        tags.update({f"id3:{k}": v for k, v in id3.items()})

    exif = _exiftool(path)
    if exif:
        report.sources.append("exiftool")
        tags.update({f"exif:{k}": v for k, v in exif.items()})

    report.tags = tags
    report.datetime_utc = _first(
        tags,
        [
            "creation_time",
            "com.apple.quicktime.creationdate",
            "date",
            "datetimeoriginal",
            "exif:DateTimeOriginal",
            "id3:TDRC",
        ],
    )
    report.device = _first(tags, ["make", "model", "com.apple.quicktime.make", "exif:Make", "exif:Model"])
    report.software = _first(tags, ["software", "encoder", "com.apple.quicktime.software", "exif:Software"])
    gps_text = _first(tags, ["location", "com.apple.quicktime.location.ISO6709", "exif:GPSPosition"])
    if gps_text:
        report.gps = _parse_iso6709(gps_text)
    report.notes = [
        "Metadata is editable; treat it as a lead, not proof.",
        "A missing tag is not evidence of tampering.",
    ]
    return report


def _parse_iso6709(text: str) -> tuple[float, float] | None:
    """Parse a simple ISO 6709 ``+lat+lon/`` string."""
    t = text.strip().replace(" ", "")
    if "/" in t:
        t = t.split("/")[0]
    if not t or t[0] not in "+-":
        return None
    parts = []
    i = 0
    for _ in range(2):
        sign = -1.0 if t[i] == "-" else 1.0
        i += 1
        j = i
        while j < len(t) and (t[j].isdigit() or t[j] == "."):
            j += 1
        parts.append(sign * float(t[i:j]))
        i = j
    return (parts[0], parts[1]) if len(parts) == 2 else None
