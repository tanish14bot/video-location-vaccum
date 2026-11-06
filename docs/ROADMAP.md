# Roadmap

> **Revised after the 2026-11-04 prior-art scan.** Two items moved ahead of
> multi-sensor arrays: **winds/temperature aloft** (the largest remaining
> accuracy bias) and a **real public benchmark** (29 CC-BY phone recordings).
> See [PRIOR_ART.md](PRIOR_ART.md).

The current release is an alpha with a working acoustic core, audio-only
support, a triage gate, and a defense module. This roadmap is ordered by
accuracy-per-effort and by what blocks a trustworthy v1.0.

## Phase 0 — Done (0.1 alpha)

- Typed config, WGS-84 geometry, delayed CPA, grid search, refinement.
- Retarded-time Doppler model, robust fit, shared-`dt` locked scoring.
- Audio-only path, metadata, mains hum, tonality, reverb.
- Triage rubric with precision buckets and the Eiffel rule.
- Leakage detection and `notch` / `cut` / `mask` / `decoy` defenses.
- Synthetic ground truth: 4 m with truth events, 100 m detected.

## Phase 1 — Clue extraction (2–3 weeks)

**Goal:** turn the recording into a rich evidence bundle before any search.

| Work | Acceptance |
|---|---|
| EXIF / QuickTime / XMP / IPTC extractor | Every tag with a location or time is surfaced, with an edit-risk label |
| ID3 / RIFF INFO / BWF `bext` / iXML | BWF date/time and originator parsed; sample-accurate time reference exposed |
| Speech language ID | Top-3 accuracy ≥ 80% on a 50-clip eval set |
| Aircraft type from BPF/harmonics | Prop vs jet vs turboprop classified; blade count estimated on synthetic tones |
| Bird/insect classifier | Optional model; species list with confidence, not a location claim |
| Bell/siren/transport templates | Event timestamps + class; no location claim |

## Phase 2 — Visual and chronolocation (3–4 weeks)

**Goal:** add independent Tier-A/B constraints.

| Work | Acceptance |
|---|---|
| Sun/shadow solver | Predicted sun azimuth/elevation error < 1° on a labeled set; latitude band output |
| Star-field solver | RA/Dec + time hypothesis; validated on synthetic night sky |
| Terrain horizon matching | DEM horizon profile vs extracted skyline; top-3 candidate regions |
| OSM/Mapillary feature search | Query several rare features within N metres; returns a ranked block |
| Signage/plate OCR | Jurisdiction candidates with confidence; never a single-cue conclusion |

## Phase 3 — Precision (4–6 weeks)

**Goal:** remove the single-pass ambiguity and push toward metres.

| Work | Acceptance |
|---|---|
| **Winds/temperature aloft (GFS/ERA5)** | Truth-point residual drops toward 0.2 Hz on a known case; range bias < 0.5% |
| **Steady-tone whitening** | Per-bin running median removed before scoring; known hum attractors no longer rank |
| **Event detector v2** | Vendored matched-filter detector now finds both reference flyovers (2155.35 s / 3068.09 s) without borrowed numbers; full-auto ranks the correct pair first at ~400 m. Acceptance: reach the surveyed/benchmark point without manual pins |
| **Wider f0/clock tolerances** | ±8% f0 and ±8 s offset accepted for descending/slowing aircraft |
| **Real benchmark: 29 CC-BY phone recordings** | Report top-1 median, best-of-top-3, abstentions, mirror rate; compare to 391 m median |
| Joint multi-event estimator | Two crossing passes recover a unique point, no mirror pair |
| Two-microphone TDOA | 100 m baseline, 0.1 ms timing; cross-range error < 1 m at 2 km |
| Array bearing | 3–4 element array gives bearing; mirror resolved |
| Track/altitude uncertainty propagation | Covariance carried into the final candidate score |
| Multi-hypothesis output | All surviving mirror/side hypotheses ranked, not silently collapsed |

## Phase 4 — Atmosphere and uncertainty (4–6 weeks)

**Goal:** remove the largest remaining bias.

| Work | Acceptance |
|---|---|
| Vertical sound-speed profile | ERA5/radiosonde ingestion; range bias < 0.5% on a known case |
| Wind shear / effective sound speed | Ray tracing; residual structure in aspect angle reduced |
| Multipath / ground effect | Model or down-weight Lloyd's-mirror nulls |
| MCMC / Laplace posterior | Marginal intervals calibrated on a known-truth case |
| Model-error inflation | 68/95% intervals cover on a held-out set |

## Phase 5 — Scale, calibration, truth (ongoing, blocks v1.0)

| Work | Acceptance |
|---|---|
| Real-data ground truth | A consented/public case with known coordinates; published error |
| Triage calibration set | ≥50 adjudicated cases per precision bucket; Wilson lower bound reported |
| CONUS-scale chunking | One day, partitioned Parquet, bounded memory, reproducible run |
| Adapter coverage | OpenSky Trino, ADS-B Exchange, adsb.lol archive, user files |
| Audit trail | Every result reproducible from a manifest |

## Phase 6 — Release engineering

- Lockfile, signed tag, PyPI, docs site, Docker image.
- Independent security review (scraping, file parsing, secrets).
- Governance: maintainers, roadmap, issue templates, release cadence.
- A published limitations page and a reproducibility statement.

## Signal backlog (impact vs effort)

| Signal | Impact | Effort | Phase |
|---|---|---|---|
| Winds/temperature aloft (GFS/ERA5) | **Highest (range bias)** | M | 3 |
| Real 29-recording benchmark | **Highest (truth)** | M | 3 |
| Steady-tone whitening | High (false candidates) | S | 3 |
| BWF `bext` time reference | High (time) | S | 1 |
| Speech language | High (region) | M | 1 |
| Aircraft BPF/type | High (disambiguation) | M | 1 |
| Sun/shadow | High (independent) | M | 2 |
| Star field | Medium | M | 2 |
| OSM/Mapillary features | High (street) | L | 2 |
| Two-mic TDOA | **Highest (metres)** | L | 3 |
| MCMC posterior | High (honesty) | M | 4 |
| Real ground truth | **Blocking** | L | 5 |

## Non-goals

- Real-time tracking of individuals.
- A location database of people.
- Fabricating evidence. Decoys are a privacy transform, not a truth claim.
- Claims of "military grade" from consumer audio. The documented ceiling is
  tens of metres with excellent ancillary data; see [PRECISION.md](PRECISION.md).
