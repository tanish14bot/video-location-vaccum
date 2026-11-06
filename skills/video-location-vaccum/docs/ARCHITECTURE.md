# Architecture

## Data flow

```
media ──► probe/hash ──► triage (watch frames + transcript + rubric)
                              │
                    skip ◄────┤────► pipeline
                              │
audio ──► spectrogram ──► ridge detection ──► event fit (f0, v, d, t0)
                                                     │
region/date ──► flight source chain ──► tracks ──────┤
                                                     ▼
                                   grid + DEM ──► delayed CPA ──► offset filter
                                                          │
                                                          ▼
                              emission-time model ──► locked scoring ──► refine
                                                          │
                                                          ▼
                                        ranked candidates + provenance
```

## Modules

| Module | Responsibility |
|---|---|
| `config` | Typed run configuration; no hidden defaults for derivable values |
| `triage/rubric` | Evidence→score, gates, precision buckets, skip/run decision |
| `triage/provenance` | SHA-256, C2PA check, explicit verification limits |
| `analysis/viability` | Consumer-media feasibility audit |
| `analysis/clues` | Metadata, mains hum, tonality, reverb leads |
| `analysis/metadata` | Container, BWF, ID3, EXIF/XMP extraction |
| `analysis/aircraft` | Blade-pass frequency and harmonic structure |
| `analysis/solar` | Solar position, shadow ratio, latitude band |
| `analysis/terrain` | DEM horizon profile and skyline comparison |
| `analysis/osm` | Overpass feature queries and rarity ranking |
| `defense/leakage` | Detect usable Doppler signatures and risk level |
| `defense/sanitize` | Notch, cut, mask, decoy; transformation manifest |
| `audio/io` | Audio/video decode through soundfile or ffmpeg |
| `audio/spectrogram` | STFT in dB with an explicit band |
| `audio/detect` | Per-frame peak linking into falling ridges |
| `audio/fit` | Robust `(f0, speed, CPA distance, CPA time)` fit with covariance |
| `geo/geodesy` | WGS-84 ECEF and local ENU; no flat-earth shortcuts |
| `geo/grid` | Grid construction, CPA, delayed CPA, offset pairs |
| `geo/dem` | Provenance-aware elevation chain with vertical datum |
| `flights/types` | `Track`, `Flight`, `FlightSource` protocol |
| `flights/local` | Parquet/CSV/JSON adapter with unit validation |
| `flights/opensky` | Recent OpenSky REST (last 30 days only) |
| `flights/adsblol` | Free daily archive traces (ODbL) |
| `flights/chain` | User file → cache → keyed → mirror → ask |
| `model/doppler` | Retarded-time Doppler equation and straight-pass model |
| `score/brightness` | Modelled curve vs spectrogram |
| `score/locked` | Single shared `dt`, per-event `f0`, shape residual |
| `pipeline` | Coarse search and refinement |
| `report` | Provenance and serialisation (via `io`) |

## Time bases

There are three clocks and they are easy to confuse:

1. **Recording time** — seconds from the start of the audio. Spectrograms and
   detected ridges live here.
2. **Track time** — the flight data's epoch (often Unix seconds).
3. **UTC wall time** — what a human reports.

`SearchConfig.t_start_epoch_s` maps recording time to track time. If it is
absent, epoch-based tracks cannot be scored; the pipeline stops rather than
silently assuming an offset. Event times are stored in recording time and
converted at the scoring boundary.

## Vertical datum

Aircraft altitude and DEM height may use different references:

- ADS-B `alt_geom` is normally HAE (ellipsoidal), but not always in practice.
- DEMs are orthometric (EGM2008, EGM96, NAVD88).
- The difference in CONUS is roughly 8–53 m and can exceed 100 m elsewhere.

`DemSample` carries `datum`, `resolution_m`, `source`, and `confidence`. The
pipeline records the datum and never silently subtracts heights from different
frames. If the datum is unknown, the result carries an altitude uncertainty.

## Determinism

- Grid construction, scoring, and refinement are deterministic given inputs.
- No random sampling is used in the search path.
- The demo uses a fixed RNG seed.
- Every result records the parameter set, tool version, input hash, and (when
  available) the git commit.

## Failure model

Expected failures are typed (`DataUnavailable`, `NoSignal`,
`DataFormatError`, `InsufficientEvidence`). Each carries an actionable message:
what was tried and what the user can provide. The CLI exits non-zero and never
substitutes fabricated data.

## Performance

- The coarse grid is the cost driver: `O(points × flights × track_samples)`.
- Scoring is `O(candidates × dt_steps × f0_steps × curve_points)`.
- Spectrogram lookups are vectorised; curves are capped at 150 points for
  scoring.
- Refinement reruns only around the top candidates, at `refine_step_m`.
- A production-scale CONUS run requires partitioning and chunking; the current
  alpha is designed for regional searches and honest benchmarking rather than
  continent-scale throughput.
