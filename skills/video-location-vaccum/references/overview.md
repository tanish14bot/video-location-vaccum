# Overview — Doppler Geolocation from Ordinary Audio

> Reference content for the `video-location-vaccum` skill.

## What this is

An aircraft passing overhead writes a **falling frequency track** into any recording whose microphone can hear it — even when the plane is inaudible to the listener. Given flight data, that track can be inverted into a location. This skill covers the whole chain, generalized to any recording, region, date, and duration: measure the curves, filter flights by delayed-CPA timing, model what each candidate should hear, score the match, confirm visually, and (in the other direction) decide whether a recording leaks a location this way and what to do about it.

## The chain

1. **Measure** — spectrogram → isolated tracks → velocity band from curve depth, slant-range band from curve rate, `f0`, heard CPA time. Count the events you actually have.
2. **Filter by time** — compute each flight's CPA, convert to **delayed CPA** with 3-D slant distance and DEM elevation, and keep grid points whose delayed-CPA pairs match the **measured** event offset.
3. **Filter by geometry and silence** — velocity/range bands plus the requirement that the quiet interval stays quiet. Airport points dominate counts; they are not winners.
4. **Model** — for every candidate × flight, rebuild the curve using **emission-time** radial velocity and the Doppler equation.
5. **Rank** — brightness-sum scoring, sweeping only the user's own Event-1 error, locking Event-2 to geometry, then refining the grid.
6. **Confirm** — per-event score maps over flight routes; ordered feature sequence in street-level imagery; explicit confidence label.
7. **Cross-check** — one event + known time is an independent path to the same place; agreement is stronger than any gap.
8. **Defend** — high-pass, drowning-out, and phone compression fail; cutting the time offset and masking help; other vectors remain.

## Generalization rule

Every number a recording yields is an **instance**, not a default:

| Observed quantity | Generic parameter | Where it comes from |
|---|---|---|
| Offset between heard CPAs | `dt` | Measured from the audio |
| Audibility radius | `R_audible` | Environment, aircraft class, calibration; sensitivity-tested |
| Coarse grid and refinement | `grid_step`, `refine_step` | Target precision and compute budget |
| Search area and date | `region`, `date` | User, metadata, or a sweep |
| Recording start time | `t_start_utc` | Metadata/messages; optional |
| Recording duration | file duration | The recording |
| Tone frequency and geometry | `f0`, `c`, `Vr` | Measured or physical |

See `resources/parameters.md` for the full parameter model, config template, and sensitivity protocol. A run that does not record its parameter values is not reproducible.

## Bounds that do not go away

- **Exact implementation and thresholds are local choices.** Different recordings, detectors, and scoring budgets produce different numbers; treat every threshold as tunable.
- **Absolute scores are not comparable across runs.** Only within-run ranking is meaningful.
- **The result is a ranked estimate plus confidence**, not a guaranteed address. Visual confirmation is what upgrades it to "place".
- **One event with unknown time is not solvable** by this method alone.
- **Coverage varies** by region, year, altitude, and receiver density; absence of flights is not absence of aircraft.

## Related resources

- `resources/parameters.md` — every tunable parameter, config template, and sensitivity protocol.
- `resources/data-sources.md` — flights, DEM, type lookups, and imagery, with provenance rules.
- `video-location-vaccum demo` — synthetic end-to-end smoke test with known geometry.
