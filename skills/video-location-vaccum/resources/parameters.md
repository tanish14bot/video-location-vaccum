# Parameter Model — Doppler Geolocation for Any Video, Any Location

> Every number a recording yields (event offset, audibility radius, grid step, region, date, start time, duration, tone frequency) is an **instance**, not a default. This file defines the generic parameters and how to choose them. Fill the config before running; record every value you chose.

---

## 1. Inputs you must obtain first

| Parameter | Symbol / key | Required | How to get it | If missing |
|---|---|---|---|---|
| Audio stream | `audio_path` | yes | Extract with `ffmpeg -i video.mp4 -vn -ac 1 -ar 48000 audio.wav`; keep the original sample rate for alias checks | Stop. No audio, no measurement. |
| Recording start time (absolute) | `t_start_utc` | optional | Container metadata, upload time minus offset, message timestamps, camera clock | Use the event-offset path (two or more events); a single event cannot be solved without time or a second constraint |
| Recording date | `date` | yes | Same sources as above; if unknown run a date sweep | Date sweep costs one full pass per candidate day; cap it |
| Search region | `region` | yes | User statement, country/state, or a bounding polygon; if wholly unknown, use the full ADS-B coverage area at coarse resolution | Full-planet runs are usually infeasible; ask for at least a country or continent |
| Time zone / UTC offset | `tz` | yes if time is local | Metadata or user statement | Ambiguous time means ±12 h; treat as two time hypotheses |
| Frequency band of the curve | `band_hz` | yes | Spectrogram inspection (aircraft Doppler is usually low-frequency, narrow, and falling) | Estimate from the strongest narrowband track |

---

## 2. Quantities measured from the audio (never defaulted)

| Parameter | Symbol | Unit | Measured by | Notes |
|---|---|---|---|---|
| Number of usable events | `N_events` | count | Manual/assisted spectrogram review | 2+ allows the offset method; 1 requires known time |
| Heard CPA time per event | `t_i` | s from recording start | Curve midpoint / loudest point | This is **heard** time, not emission time |
| Event offset | `dt_ij` | s | `t_j - t_i` | A measured interval; never a default |
| Fundamental frequency per event | `f0_i` | Hz | Slide the measured curve up/down until it matches | Uncertain; must be swept. Do not treat as a constant |
| Velocity band per event | `v_i` | m/s | Curve **depth** | Widen until the observed curve is inside the band |
| Slant-range band per event | `r_i` | m | Curve **rate of change** | 3-D range, includes aircraft altitude |
| Fit quality | `q_i` | perfect / imperfect | Visual overlay | Imperfect → widen bands, never tighten |

**Rule:** measurement uncertainty must be carried forward explicitly. A single point estimate for `v`, `r`, `f0`, or `t` is a modeling error, not precision.

---

## 3. Physical and method settings (tunable; defaults are starting points only)

| Parameter | Key | Unit | Starting value | How to choose | Sensitivity |
|---|---|---|---|---|---|
| Speed of sound | `c` | m/s | 343 (20 °C, dry air) | `c ≈ 331.3 + 0.606·T(°C)`; use site temperature if known. Humidity changes it by <1% | Low–medium: affects delay by ~0.3% per 1 °C |
| Assumed audible slant range | `R_audible` | m | 10 000 as a *conservative* start | Large jets at altitude and quiet rural sites can be heard farther (try 20–30 km); dense city/terrain can be shorter (3–5 km). Calibrate on a known-location recording | **Highest**: too small deletes the true point; too large multiplies candidates |
| Coarse grid step | `grid_step` | m | 200 | Fine enough for the target area. For a state/region prior, use 2–5 km for a coarse pass and refine; a coarse grid can miss a narrow offset match, so widen `dt_tol` on that pass. Cost scales as `1/grid_step²`. | High |
| Refinement step | `refine_step` | m | `grid_step / 2` (100) | Half the coarse step, or finer where the score surface is broad | Medium: only affects final precision, not candidate discovery |
| Aircraft classes | `type_filter` | set | all types | Start with all; run a second pass restricted to props/turboprops as a noise-reduction sensitivity test. Never silently drop a class | **High**: dropping the true class makes the search unsolvable |
| Event-offset tolerance | `dt_tol` | s | 5 | ≥ combined timing measurement error (curve midpoint + propagation uncertainty) | Medium: too tight loses truth, too loose floods candidates |
| Silence policy | `silence_min_gap`, `silence_max_signal` | s, dB/relative | gap ≥ observed quiet interval; signal ≤ noise floor + margin | Derive from the actual recording: what does "no curve" look like in *this* file? | **High**: silence is one of the strongest filters |
| Event-1 time sweep | `sweep_t` | s | ±5 | A few seconds, scaled by timing error | Medium |
| f0 sweep | `sweep_f0` | Hz or % | ±5% of `f0` | Scaled by how well the curve slide is constrained | Medium |
| Candidate budget | `max_candidates` | count | machine-dependent | Stop expanding before memory/time blow-up; report truncation | Operational |
| Confidence gap | `gap_strong`, `gap_weak` | ratio | 1.15 / 1.05 (heuristic) | Winner ÷ runner-up score. State it as a local convention | Reporting only |

---

## 4. Adaptive recipes

### A. Two or more events, time unknown
Run the offset method: `dt_ij` from audio → delayed-CPA matching → geometry bands → silence → locked scoring. Substitute the interval measured from the recording.

### B. One event, time known
Run the single-event path: time slice → velocity/range filter → trace-line scoring. Requires `t_start_utc` with second-level confidence.

### C. One event, time unknown
Not solvable by this method alone. Ask for: another event, the recording time, or an independent spatial prior (city/landmark). Do not fabricate a time.

### D. Date unknown
Repeat the coarse pass for each candidate day (cap the number). A location that wins repeatedly across days is stronger evidence than a single-day win.

### E. Region unknown
Run a multi-resolution sweep: continent-scale coarse grid → refine only the top region. State the resolution used at each level.

### F. Time zone ambiguous
Run both UTC hypotheses (local time interpreted as UTC±offset). Report both.

### G. Airport-dominated candidate set
Expected: route density concentrates delayed-CPA matches near airports. Do not treat this as signal; the silence filter and full-curve scoring are what separate a real quiet-site match from airport noise.

---

## 5. Config template (copy before a run)

```yaml
# doppler-run-config.yaml
input:
  audio_path: ""
  video_path: ""
  date: ""              # YYYY-MM-DD
  t_start_utc: null     # ISO-8601 or null
  tz: "UTC"
  region: ""            # name or GeoJSON path
  band_hz: [0, 0]       # observed curve band
events:
  - id: 1
    t_heard_s: null
    f0_hz: null
    f0_uncertainty_hz: null
    velocity_band_mps: [null, null]
    slant_band_m: [null, null]
    fit_quality: ""
  - id: 2
    t_heard_s: null
    f0_hz: null
    f0_uncertainty_hz: null
    velocity_band_mps: [null, null]
    slant_band_m: [null, null]
    fit_quality: ""
settings:
  c_mps: 343
  R_audible_m: 10000
  grid_step_m: 200
  refine_step_m: 100
  type_filter: all
  dt_tol_s: 5
  silence_min_gap_s: null
  silence_max_signal_db: null
  sweep_t_s: 5
  sweep_f0_pct: 5
  max_candidates: null
reporting:
  gap_strong: 1.15
  gap_weak: 1.05
```

Every field that stays `null` is a documented gap; the run must not silently substitute a value.

---

## 6. Sensitivity protocol (run before believing a winner)

1. **`R_audible` ±50%** — does the winner survive? If it disappears when widening, the candidate set was truncated.
2. **`grid_step` halved** — does a better point appear? If yes, the original grid was too coarse.
3. **`type_filter` all ↔ props-only** — does the winner change class? A class-dependent winner is fragile.
4. **`c` ±3%** (temperature range) — does the delay ordering change? Usually no; if yes, timing is over-tight.
5. **`dt_tol` halved/doubled** — is the winner inside the overlap of both runs?
6. **`sweep_t` / `sweep_f0` doubled** — does the gap collapse? A gap that only exists at one sweep width is a tuning artifact.

Report the winner under each perturbation. A conclusion that survives all six is worth presenting; one that does not is a hypothesis.
