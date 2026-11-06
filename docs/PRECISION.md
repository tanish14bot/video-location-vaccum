# Precision Limits

> Read this before making an accuracy claim. The binding limits are the source
> tone, the atmosphere, and the track — not the microphone or the FFT.

## What one pass determines

A single straight pass gives four identifiable quantities:

```
f_e (emitted frequency), M = v/c, a = v/r0, t0
```

so `r0 = M·c/a` and `v = M·c`. But:

- **Heading is a gauge freedom.** One microphone cannot observe the azimuth of
  the flight line.
- **The side is ambiguous.** `d → −d` is an exact symmetry: you get two mirror
  points.
- **Altitude, range, and sound speed are degenerate** when all three are unknown.

A single event therefore yields a **distance to a line plus a mirror pair**, not
a point. A second event helps only if its geometry differs materially. Two
passes on the same track add almost nothing; two passes crossing near 90° give
`GDOP ≈ 1.4`.

## Error budget (reference case)

Turboprop, `h = 2000 m`, `v = 120 m/s`, CPA ground distance `d = 1500 m`,
`r0 = 2500 m`, 60 s pass, 100 Hz tone. Cross-track amplification `r0/d = 1.67`.

| Term | 1σ input | → Δr0 | → Δposition |
|---|---|---:|---:|
| Frequency noise (white) | 1e−5 relative | 0.03 m | 0.05 m |
| Timing | 5 ms | 0.6 m | 1 m |
| Source tone drift | 0.1 % / pass | 2.5 m | 4 m |
| Sound speed: temperature | 1 K | 4.3 m | 7 m |
| Sound speed: humidity | 20 % RH | 5 m | 8 m |
| Vertical profile unmodelled | 1.5 % | 37 m | 62 m |
| Wind shear / refraction | 0.5 % | 12 m | 20 m |
| Altitude (barometric) | 20 m | 27 m | 45 m |
| Track position (NACp 8) | σ ≈ 47 m | 47 m | 78 m |
| Source vs antenna lever arm | 20 m | 20 m | 33 m |
| DEM (observer elevation) | 5 m | 5 m | 8 m |
| Multipath | 0.2 % | 5 m | 8 m |
| **RSS, best case** | GPS alt, NACp 10, modelled profile | **~15 m** | **~25 m** |
| **RSS, typical** | baro alt, NACp 8, unmodelled lever arm | **~71 m** | **~120 m** |

A ~100 m reference result is consistent with the typical column. It is not a
promise for another recording.

## What dominates, in order

1. **Source frequency stability.** A wandering tone is indistinguishable from a
   change in geometry. A 0.5 % wander caps range at ~0.5 %.
2. **Aircraft altitude and track knowledge**, including ADS-B quantization and
   the lever arm between the navigation antenna and the noise source.
3. **Atmospheric profile and wind shear.** Surface weather is not enough for an
   elevated source; 1.5–4 % range error is typical.
4. **Multipath and source directivity.**
5. **Frequency measurement and timing** — effectively free by comparison.

## Is "military grade" achievable?

If that means **< 10 m CEP from one consumer recording**: no.

| Scenario | Achievable (1σ horizontal) | Requires |
|---|---|---|
| Phone recording, no track, urban | 0.5–5 km | essentially a line |
| One recording + ADS-B NACp 8 + surface weather | ~100–200 m | baro alt, unmodelled lever arm |
| One recording + NACp 10 + met profile + GPS alt | ~25–40 m | calibration, multipath modelling |
| Stable tone, close pass, two-mic array, three passes | 5–10 m | array + multi-event + calibration |

The defensible claim: **tens of metres with disciplined ancillary data; metres
is not achievable from a bare phone recording.**

## Estimator design

- Robust least squares with a soft-loss and covariance from the Jacobian.
- Report marginal intervals, not just a point.
- Inflate statistical covariance with a model-error term calibrated against a
  known-truth case.
- Keep mirror hypotheses until a second geometry or a second sensor resolves them.
- Cross-validate: fit the approach, predict the departure.
- Sensitivity-test `R_audible`, grid step, class filter, `c`, `dt_tol`, sweep
  widths before believing a winner.

## What the implementation currently does

- Delayed (retarded-time) model, not a shifted instantaneous model.
- Robust fit with covariance.
- Single shared `dt` and per-event `f0` sweep.
- Frequency-shape residual in addition to brightness, so a thick ridge cannot
  produce a flat score surface.
- Grid refinement around top candidates.
- Explicit mirror ambiguity is preserved by scoring all grid cells; the report
  should be read as "best cell plus alternatives", not a unique point.

Not yet implemented: ray-traced atmospheric profiles, wind shear, multipath
modelling, multi-microphone arrays, MCMC posteriors. These are the next
accuracy levers.
