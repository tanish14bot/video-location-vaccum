"""Run configuration.

Every knob is a parameter here. Defaults are deliberately conservative and
documented; none of them is silently assumed when the value can be derived
from the recording.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TriageMode(str, Enum):
    """How the location is allowed to be determined."""

    AUTO = "auto"  # visual triage may skip the acoustic pipeline
    VISUAL = "visual"  # visual/text clues only; never run acoustics
    DOPPLER = "doppler"  # always run the acoustic pipeline
    FORENSIC = "forensic"  # always run acoustics + full provenance chain


class FitQuality(str, Enum):
    PERFECT = "perfect"
    IMPERFECT = "imperfect"
    UNKNOWN = "unknown"


class EventConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    t_heard_s: float = Field(..., description="Heard CPA time, seconds from recording start")
    f0_hz: float
    f0_sigma_hz: float = 0.0
    velocity_band_mps: tuple[float, float] | None = None
    slant_band_m: tuple[float, float] | None = None
    fit_quality: FitQuality = FitQuality.UNKNOWN
    times_s: list[float] | None = None
    freqs_hz: list[float] | None = None
    half_width_s: float = Field(20.0, gt=0)

    @model_validator(mode="after")
    def _check(self) -> EventConfig:
        if self.f0_hz <= 0:
            raise ValueError("f0_hz must be positive")
        if self.t_heard_s < 0:
            raise ValueError("t_heard_s must be >= 0")
        for name in ("velocity_band_mps", "slant_band_m"):
            band = getattr(self, name)
            if band is not None and band[0] > band[1]:
                raise ValueError(f"{name} must be (low, high)")
        return self


class RegionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    min_lat: float = Field(..., ge=-90, le=90)
    min_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)
    max_lon: float = Field(..., ge=-180, le=180)

    @model_validator(mode="after")
    def _check(self) -> RegionConfig:
        if self.min_lat >= self.max_lat:
            raise ValueError("min_lat must be < max_lat")
        if self.min_lon >= self.max_lon:
            raise ValueError("min_lon must be < max_lon")
        return self


class SearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: RegionConfig
    date: _date
    date_end: _date | None = None
    t_start_utc: datetime | None = None
    t_start_epoch_s: float | None = None
    timezone: str = "UTC"
    c_mps: float = Field(343.0, gt=200, lt=400)
    r_audible_m: float = Field(10_000.0, gt=0)
    grid_step_m: float = Field(200.0, gt=0)
    refine_step_m: float = Field(100.0, gt=0)
    type_filter: Literal["all", "props", "jets", "turboprops"] = "all"
    dt_tol_s: float = Field(5.0, gt=0)
    silence_min_gap_s: float | None = Field(None, gt=0)
    silence_max_signal_db: float | None = None
    sweep_t_s: float = Field(5.0, ge=0)
    sweep_f0_pct: float = Field(5.0, ge=0)
    max_candidates: int | None = Field(None, gt=0)
    apply_bands: bool = True

    @model_validator(mode="after")
    def _check(self) -> SearchConfig:
        if self.date_end is not None and self.date_end < self.date:
            raise ValueError("date_end must be >= date")
        if self.grid_step_m > self.r_audible_m:
            raise ValueError("grid_step_m must be <= r_audible_m")
        if self.refine_step_m > self.grid_step_m:
            raise ValueError("refine_step_m must be <= grid_step_m")
        return self

    @property
    def dates(self) -> list[_date]:
        if self.date_end is None or self.date_end == self.date:
            return [self.date]
        out: list[_date] = []
        cur = self.date
        while cur <= self.date_end:
            out.append(cur)
            cur += timedelta(days=1)
        return out


class FlightsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred: Literal["user_file", "cache", "api", "mirror", "ask"] = "user_file"
    user_file: Path | None = None
    altitude_unit: Literal["ft", "m"] = "ft"
    cache_dir: Path | None = None
    allow_network: bool = True
    opensky_client_id: str | None = None
    opensky_client_secret: str | None = None
    adsb_exchange_key: str | None = None
    allow_mirrors: bool = True
    ask_on_missing: bool = True


class DemConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred: Literal["user_file", "cache", "api", "flat", "ask"] = "user_file"
    user_file: Path | None = None
    cache_dir: Path | None = None
    allow_network: bool = True
    product: str = "copernicus-glo30"
    ask_on_missing: bool = True
    allow_flat_fallback: bool = False
    flat_height_m: float = 0.0


class TriageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TriageMode = TriageMode.AUTO
    min_confidence: float = Field(0.90, ge=0.0, le=1.0)
    force_pipeline: bool = False
    ignore_visuals: bool = False
    watch_script: Path | None = None
    max_frames: int = Field(120, gt=0)
    frame_width: int = Field(1024, ge=256, le=2048)
    evidence_file: Path | None = None

    @model_validator(mode="after")
    def _check(self) -> TriageConfig:
        if self.mode is TriageMode.FORENSIC and self.ignore_visuals:
            raise ValueError("forensic mode cannot ignore visual evidence")
        return self


class InputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video: Path | None = None
    audio: Path | None = None
    question: str | None = None

    @model_validator(mode="after")
    def _check(self) -> InputConfig:
        if self.video is None and self.audio is None:
            raise ValueError("at least one of video/audio is required")
        return self


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: InputConfig
    triage: TriageConfig = Field(default_factory=TriageConfig)
    search: SearchConfig | None = None
    events: list[EventConfig] = Field(default_factory=list)
    flights: FlightsConfig = Field(default_factory=FlightsConfig)
    dem: DemConfig = Field(default_factory=DemConfig)
    output_dir: Path = Field(default_factory=lambda: Path("runs"))

    @model_validator(mode="after")
    def _check(self) -> RunConfig:
        if self.search is None and self.triage.mode is TriageMode.DOPPLER:
            raise ValueError("doppler mode requires a search configuration")
        if self.search is not None and not self.events:
            raise ValueError(
                "a search configuration requires at least one measured event; "
                "run the event-extraction step first"
            )
        return self


def load_config(path: Path) -> RunConfig:
    from .io import read_yaml

    data = read_yaml(path)
    return RunConfig.model_validate(data)
