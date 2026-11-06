"""Audio loading with ffmpeg fallback."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


class AudioLoadError(RuntimeError):
    pass


def load_audio(path: Path, *, sr: int = 8000, mono: bool = True) -> tuple[NDArray[np.float64], int]:
    """Load an audio or video file as float64 samples.

    Uses soundfile when available; otherwise extracts via ffmpeg. Video files
    are always routed through ffmpeg.
    """
    path = Path(path)
    if not path.exists():
        raise AudioLoadError(f"audio/video not found: {path}")

    if path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".avi"}:
        return _load_with_ffmpeg(path, sr=sr, mono=mono)

    try:
        import soundfile as sf

        data, file_sr = sf.read(str(path), always_2d=True, dtype="float64")
        y = data.mean(axis=1) if mono else data[:, 0]
        if file_sr != sr:
            y = _resample(y, file_sr, sr)
        return np.asarray(y, dtype=np.float64), sr
    except Exception:
        return _load_with_ffmpeg(path, sr=sr, mono=mono)


def _load_with_ffmpeg(path: Path, *, sr: int, mono: bool) -> tuple[NDArray[np.float64], int]:
    channels = "1" if mono else "2"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "audio.raw"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            channels,
            "-ar",
            str(sr),
            "-f",
            "f32le",
            "-y",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except FileNotFoundError as exc:
            raise AudioLoadError("ffmpeg is required to decode this file") from exc
        except subprocess.CalledProcessError as exc:
            raise AudioLoadError(exc.stderr.decode("utf-8", "replace")[:500]) from exc
        raw = np.fromfile(out, dtype=np.float32)
        if mono:
            return raw.astype(np.float64), sr
        return raw.reshape(-1, 2).astype(np.float64), sr


def _resample(y: NDArray[np.float64], sr_in: int, sr_out: int) -> NDArray[np.float64]:
    from scipy.signal import resample_poly

    g = np.gcd(sr_in, sr_out)
    return np.asarray(resample_poly(y, sr_out // g, sr_in // g), dtype=np.float64)
