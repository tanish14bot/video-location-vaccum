<!-- capability_id: cap.doppler.event-extraction | revision: 2 | status: active -->

# Doppler Spectrogram Event Extraction & Curve Measurement

## I — Interpretation

Turn spectrogram tracks that are inaudible to the ear into physical quantities. Curve **depth** gives an aircraft-velocity band; curve **rate** gives a CPA slant-range band. `f0` and heard CPA time are the curve's anchors. This is a *measurement* step, so its output is always an interval plus an error note, never a single hard number. How many events you need depends on what else is known: two or more events allow the offset method with unknown time; one event requires a known recording time. A recording's 920 s offset, 130 Hz / 109.9 Hz points, and 1-hour duration are that recording's instance — read the same quantities from whatever recording you actually have. Note the ideal-curve assumption (linear, constant velocity): real flights turn and accelerate, so imperfect fits are normal and must widen the bands rather than be forced.

---

## A1 — Application Example

### Example 1 — two curves, 100 m/s fit, 70 m/s excluded

- **Type**: worked example.
- **Problem/input**: Two heard Doppler curves need a velocity bound and range band for candidate filtering
- **How the methodology was used**: Slide/stretch the curve on the spectrogram: drop depth → velocity; drop rate → CPA slant range; align CPA time to the audio stamp; estimate f0
- **Conclusion**: One event fits ~100 m/s (70 m/s ruled out); the other does not fit the ideal curve and was marked "uncertain"
- **Result**: Per event: velocity band + range band + f0 + CPA audio stamp; generous ranges prevent accidental deletion

### Example 2: One event only (generalized case)

- **Problem/input**: A single faint curve and no second event
- **How the methodology was used**: Measure it the same way, then branch: known time → single-event path; unknown time → ask for time/second event/spatial prior
- **Conclusion**: Measurement is identical; feasibility is decided by the missing constraint, not by the curve

---

## A2 — Future Trigger ★

### In what situation will the user need this skill?

1. The user supplies audio/video that may contain inaudible aircraft Doppler sound (or explicitly says Doppler)
2. The user asks "can this audio be located / can we measure aircraft speed from audio"
3. The user needs velocity/range bands as input to flight-data filtering

### Language signals

- "Doppler / spectrogram / frequency curve / speed from curve"
- "inaudible / background sound location"
- "does this audio contain an aircraft sound"

### Distinction from adjacent skills

- vs `doppler-modeling`: this card reads quantities *from* the curve (measurement); modeling computes "what curve should be heard" from flight data
- vs `adsb-coarse-filter`: this card produces the filter inputs; the coarse filter consumes them

---

## E — Execution

**Required input**: An audio file or accessible raw audio stream; the recording's time base. Without audio, do not start — ask for the file/link.
**Deliverable & completion**: An **event table**: per event, start/end time, `t_heard`, velocity band, slant-range band, `f0` + uncertainty, fit quality, and the frequency band used.

1. **Render the spectrogram**
 - x = time, y = frequency; zoom to the suspected aircraft band and raise resolution
 - Completion: falling tracks are visible, or record "no discernible curve at this sampling point"
2. **Enumerate events**
 - Pick every track that is isolated enough to measure; do not stop at two if more exist
 - Completion: `N_events` known, with each event's heard CPA timestamp
3. **Read the quantities**
 - Drop depth → velocity band; drop rate → slant-range band; f0 by sliding; CPA time aligned
 - Measurement contract: fit `(f0, v, d, t0)` and record the derived `f_pre`, `f_post`, `max RoC`
 - Completion: every event yields all four values plus a fit-quality note
 - Note: two fits can share `f0` and `t0` but differ in `v` and `d` (observed 106.5 m/s / 3130 m vs 125 m/s / 4295 m) — keep both as a band
4. **Annotate uncertainty**
 - Imperfect fit → widen; never tighten to make a later step look clean
 - Completion: event table carries explicit uncertainty; missing → rework
5. **Decide the branch**
 - `N ≥ 2` → offset path; `N = 1` + known time → single-event path; otherwise stop and ask
 - Completion: branch recorded with its justification

---

## B — Boundary ★

### Do not use this skill when

- No raw audio available → cannot measure
- Curve indiscernible or outside the recorded band → seek another signal; thunder/acoustic fingerprints are not aircraft Doppler
- Treating `f0` as a physical constant → `f0` is measured and must be swept
- Forcing an ideal curve fit → mark imperfect regions, do not delete them

### Failure modes to watch for

- Forcing an ideal fit (modeling-side anti-pattern ce01; here: not marking imperfect regions)
- Treating a quiet sample as "no signal" and giving up (ce05: many airport points do not mean no signal; silence itself is a clue)

### Method limitations

- **Event detector missing (needs_review nr-01)**: event selection relies on human judgment in the recording; no threshold rule is given — this card does not invent one
- **Generous-range values undisclosed**: ranges are implementation choices; only the requirement to annotate them is transferable
- `c` is treated as constant; temperature/humidity correction is not discussed

### Easily confused neighboring methodologies

- `doppler-modeling`: measure vs model (inverse pair)
- `locked-scoring`: where these measurements enter the scoring sweep

---

## Related skills

- depends-on: (none)
- composes-with: `adsb-coarse-filter`, `doppler-modeling`, `locked-scoring`

---

## Audit

- **Verified**: V1 ✓ / V2 ✓ / V3 ✓
- **Generalized**: 2026-11-04 (all recording-specific values reframed as instances)

## Bundled resources

Paths are relative to this file; check preconditions before running anything.

- [resources/parameters.md](../../resources/parameters.md)
- [resources/data-sources.md](../../resources/data-sources.md)