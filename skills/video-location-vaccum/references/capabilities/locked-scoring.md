<!-- capability_id: cap.doppler.locked-scoring | revision: 2 | status: active -->

# Locked Scoring: Brightness Comparison, Measurement-Error Sweep, Grid Refinement

## I — Interpretation

Score each candidate by how much spectrogram brightness its modelled curves cover, then sweep away **measurement** error without sweeping away **true timing**. Event 1 absorbs the user's own f0/timing error; the relative offset of Event 2 is locked to flight geometry. If a candidate still misses after that sweep, the candidate is wrong — not the sweep. Finish by refining the surviving grid cells, because a coarse cell center can be up to ~0.7 × `grid_step` from the true point (141 m at 200 m). The recording's 20.48-vs-15 gap is an instance: compare scores within one run, never across recordings.

---

## A1 — Application Example

### Example 1 — 20.48 winner vs ~15 runner-up

- **Type**: worked example.
- **Problem/input**: ~15k candidates + two true curves + spectrogram
- **How the methodology was used**: Per-candidate dual curves → brightness sum → pair clustering → refinement of the 200 m winners
- **Conclusion**: The winner's curves are nearly invisible against the spectrogram because they cover it; the runner-up's Event 2 visibly misses
- **Result**: One highest-scoring point per flight pair → a single wide-gap winner

### Example 2: Same method, other grid (generalized case)

- **Problem/input**: Coarse grid 500 m in a large region
- **How the methodology was used**: refine winners at 250 m, then 125 m if the score surface stays broad
- **Result**: precision is a function of refinement budget, not of the recording's numbers

---

## A2 — Future Trigger ★

### In what situation will the user need this skill?

1. The user needs to pick the unique (or few) true location(s) inside a candidate set
2. The user needs to explain why sweep/locking is necessary (measurement error vs mis-ranking)
3. The user needs to refine a coarse winner and judge whether the gap is meaningful

### Language signals

- "locked scoring / brightness scoring / sweep / grid refinement"
- "why is the runner-up's second event off yet still ranked high"
- "final winner determination"

### Distinction from adjacent skills

- vs `doppler-modeling`: scoring is the referee; modeling is the contestant
- vs `single-event-known-time`: this card is the multi-event referee; single event uses trace-distance scoring
- vs `visual-verification`: scoring gives a point; verification turns the point into a place

---

## E — Execution

**Required input**: Candidate set; observed curves + spectrogram; modelled curves per candidate × flight; `sweep_t`, `sweep_f0`; `refine_step`.
**Deliverable & completion**: Per-candidate per-event scores, winner lat/lon, runner-up comparison, and a confidence statement.

1. **Place the curves**
 - Align Event 1's modelled delayed CPA to the recorded CPA stamp; place Event 2 using the geometry-determined offset
 - Completion: both curves land in spectrogram coordinates
2. **Sweep Event 1 only**
 - Sweep `t ± sweep_t`, `f0 ± sweep_f0`; take the best brightness sum
 - Completion: optimum and score recorded
 - Stop condition: **If sweep windows are unset → label "sweep window unset" and do not claim a ranking**
3. **Lock Event 2**
 - Apply **one shared** `dt` to both curves: only the clock anchor moves; the inter-event separation stays fixed by geometry
 - Sweep `f0` per event only
 - Completion: locked score recorded separately per event (observed 8.89 / 8.43) plus the shared `dt` used
4. **Refine**
 - Re-run the top cells on a `refine_step` sub-grid; aggregate by flight pair; keep the best per pair
 - Completion: refined winner + runner-up gap
5. **Judge the gap**
 - Apply local `gap_strong` / `gap_weak` conventions; report "ambiguous" when the gap is small
 - Completion: explicit confidence label, never a bare coordinate

---

## B — Boundary ★

### Do not use this skill when

- No spectrogram / no curves → no brightness to count
- Only one event with unknown time → locked multi-event scoring cannot start (use `single-event-known-time`)
- Absolute scores compared across recordings → normalization is undisclosed; only within-run comparison is valid
- A wide gap is treated as proof → it is evidence, not confirmation; visual verification still required

### Failure modes to watch for

- ce06: ranking directly on a coarse grid is scrambled by quantization error
- ce01: wrong model → wrong score

### Method limitations

- **Sweep step and normalization undisclosed (nr-05)**: record the method; do not promise absolute score bands
- Refinement is expensive: each point is scored independently; plan compute before starting
- Score gap heuristics are local conventions, not the recording's numbers

### Easily confused neighboring methodologies

- `visual-verification`: scores are not the final place; imagery confirms
- `single-event-known-time`: multi-event referee vs single-event referee

---

## Related skills

- depends-on: `doppler-modeling`, `adsb-coarse-filter`
- composes-with: `visual-verification`

---

## Audit

- **Verified**: V1 ✓ / V2 ✓ / V3 ✓
- **Generalized**: 2026-11-04 (200 m/100 m/141 m reframed as grid + refinement policy)

## Bundled resources

Paths are relative to this file; check preconditions before running anything.

- [resources/parameters.md](../../resources/parameters.md)
- [resources/data-sources.md](../../resources/data-sources.md)