# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0a0] - 2026-11-04

### Added

- Audio-only mode: triage, metadata, mains hum, tonality, reverb, and the full
  acoustic pipeline without video.
- Defense module: leakage detection, time-frequency notch, event cut, masking
  noise, optional decoy curves, and a transformation manifest.
- `signals`, `leakage`, and `defend` CLI commands.
- Consumer viability audit (`viability`) with multiple/single/visual-only verdicts.
- Visual/chronolocation clues: solar position and shadow latitude band,
  DEM horizon profiles, and OpenStreetMap feature queries.
- Metadata extraction for container tags, BWF `bext`, ID3 (mutagen), EXIF/XMP
  (ExifTool), and ISO 6709 GPS.
- Aircraft blade-pass/harmonic analysis for prop/jet hints.
- `docs/SIGNALS.md`, `docs/DEFENSE.md`, `docs/ROADMAP.md`, and
  `docs/RELEASE_CHECKLIST.md`.

- Typed run configuration with explicit tunable parameters.
- WGS-84 geodesy, local ENU frames, slant distance, delayed CPA.
- Retarded-time Doppler model and robust straight-pass fit with covariance.
- Spectrogram computation and per-frame peak-linking ridge detection.
- Guided Viterbi ridge tracer and flyby fit (`video-location-vaccum trace`), adapted
  from doppler-locate (MIT); see `NOTICE`.
- Automatic flyover detection (`video-location-vaccum auto`), using a vendored copy of the
  MIT doppler-locate matched-filter detector with harmonic grouping.
- `docs/PRIOR_ART.md` with independent implementations, validations, and licenses.
- Flight adapters: local Parquet/CSV/JSON, synthetic, OpenSky (recent), adsb.lol archive.
- Flight-source fallback chain with actionable `DataUnavailable` errors.
- DEM chain: local raster, USGS 3DEP, Open-Meteo, explicit flat fallback; datum recorded.
- Grid search, offset filtering, refinement, locked scoring with shape residual.
- Evidence rubric with precision buckets, gate caps, forcing triggers, and overrides.
- Triage command integrating claude-video's `watch` tool.
- Mandatory intake questionnaire.
- Synthetic end-to-end demo and regression test (recovers truth within 50 m).
- CLI: `doctor`, `intake`, `triage`, `decide`, `events`, `run`, `demo`.
- Documentation: architecture, precision limits, triage, data sources.
- Ethics, security, contributing, code of conduct, notice, citation.
- CI matrix, lint, types, tests, build, and dependency audit.

### Known limitations

- No atmospheric ray tracing, wind shear, multipath, or microphone arrays.
- Single-pass mirror ambiguity is preserved but not automatically resolved.
- Historical flight data before 2023 requires the user's own credentials/archive.
- Triage weights are uncalibrated; the score is not a probability.
- Automatic event detection remains unreliable on faint real recordings; use
  `video-location-vaccum trace` for a guided measurement.
- Region-scale performance only; continent-scale chunking is not yet implemented.
