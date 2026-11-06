<!-- capability_id: cap.doppler.modeling | revision: 2 | status: active -->

# Doppler Modeling: Emission-Time Radial Velocity and the Doppler Equation

## I — Interpretation

Compute "what curve should be heard" from true geometry, rather than fitting a shape to the observed curve. For each listener time, subtract the propagation delay `slant / c` to find when the sound was emitted, take the aircraft's radial velocity **at that emission moment**, and put it through the Doppler equation. Only three inputs are needed: `c`, `Vr_emit`, `f0` — and `f0` is a measured, uncertain value. Using receive-time `Vr` does not shift the curve slightly; it produces a different shape. This is where a correct candidate becomes distinguishable from a wrong one. Note a recording's 130 Hz / 109.9 Hz figures are a worked teaching point, not constants for other recordings.

---

## A1 — Application Example

### Example 1 — CPA 130 Hz, +5 s Vr = 62.7 m/s → 109.9 Hz

- **Type**: worked example.
- **Problem/input**: One observer's true ADS-B flight geometry + measured `f0`
- **How the methodology was used**: Sample listener times → back out emission time → `Vr_emit` → Doppler equation → frequency point → connect the curve
- **Conclusion**: The correct curve matches the spectrogram; the receive-time shortcut does not
- **Result**: Teaching values for magnitude checking only

### Example 2: Any candidate point (generalized case)

- **Problem/input**: Candidate lat/lon, flight track, `f0` band
- **How the methodology was used**: same loop with the local `c` and the measured `f0`; output a curve per candidate × flight
- **Result**: Curves carry a timestamp base aligned to the recording, ready for scoring

---

## A2 — Future Trigger ★

### In what situation will the user need this skill?

1. The user has candidate geometry + flight and wants "what curve would this point hear" to compare against the spectrogram
2. The modelled curve does not match and the user needs to tell whether modeling or the candidate is wrong
3. The user needs to explain "why a delayed curve is not just a shifted curve"

### Language signals

- "model the Doppler curve / emission-time Vr"
- "receive-time Vr is wrong / curve doesn't match spectrogram"
- "Doppler equation modeling"

### Distinction from adjacent skills

- vs `doppler-event-extraction`: modeling derives curves from flight data; extraction reads quantities from curves
- vs `locked-scoring`: modeling produces curves; scoring compares curves to the spectrogram

---

## E — Execution

**Required input**: Candidate point (lat/lon/DEM elevation); flight time series with position/velocity/altitude, interpolated to the needed resolution; measured `f0`; `c`.
**Deliverable & completion**: One modelled curve per candidate × flight (listener time → observed frequency), plus the interpolation and `f0` choices used.

1. **Sample listener times**
 - Cover the curve center and both flanks at a resolution finer than the narrowest feature you intend to score
 - Completion: listener window defined
2. **Back out emission time**
 - `t_emit = t_listen - slant / c`; interpolate flight state at `t_emit`
 - Completion: every listener time maps to an emission state
 - Stop condition: **If the flight time series cannot be interpolated → stop and mark the gap**
3. **Doppler equation**
 - `f = f0 · c / (c + v_r)` with `v_r` positive when receding (form observed on screen); solve `t_e = t_r − r(t_e)/c` iteratively
 - Build the curve point by point
 - Completion: curve spans the listener window and shares the spectrogram's time/frequency axes
4. **Validate the direction of the error**
 - Plot receive-time vs emission-time curves on a known example; confirm the difference is a shape change, not a translation
 - Completion: the anti-pattern is demonstrably excluded

---

## B — Boundary ★

### Do not use this skill when

- Input is only the curve without flight data → no geometry to model
- The Doppler equation is expected to be exact ground truth → the recording gives a worked point; the written form is not verbatim
- A receive-time `Vr` shortcut is tempting → always wrong (ce01)

### Failure modes to watch for

- **ce01: receive-time Vr** → curve wrong enough to fail the search
- Mistaking "delay" for "shift": the wrong curve is not the right curve a few seconds later; it is an entirely wrong curve

### Method limitations

- **Interpolation details undisclosed** ("interpolated ADS-B data" mentioned only): do not invent granularity/smoothing; state what you used
- `c` taken as constant; gradients with temperature/altitude not discussed
- Linear constant-velocity assumption belongs to measurement, not modeling

### Easily confused neighboring methodologies

- `doppler-event-extraction`: measure vs model (inverse pair)
- `locked-scoring`: without correct curves, scoring is meaningless

---

## Related skills

- depends-on: `adsb-coarse-filter`, `doppler-event-extraction`
- composes-with: `locked-scoring`

---

## Audit

- **Verified**: V1 ✓ / V2 ✓ / V3 ✓
- **Generalized**: 2026-11-04 (worked numbers retained as evidence, not defaults)

## Bundled resources

Paths are relative to this file; check preconditions before running anything.

- [resources/parameters.md](../../resources/parameters.md)
- [resources/data-sources.md](../../resources/data-sources.md)