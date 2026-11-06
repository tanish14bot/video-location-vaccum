<!-- capability_id: cap.doppler.single-event | revision: 2 | status: active -->

# Single Event + Known Time: Single-Curve Search and Cross-Check

## I — Interpretation

When only one isolated curve remains, the missing event can be replaced by a **known recording time**. The search then keeps only flight segments that could produce that curve at that absolute moment, and scores a single traced line by distance rather than two-curve brightness. The value is not just coverage of the one-event case: running it independently on a recording that also has two events is a **method-level cross-check**. Agreement at the same location is strong evidence; disagreement is a finding, not a failure to hide. The recording's 20:37 UTC and 40.87 score are that recording's instance; any recording with second-level time works the same way.

---

## A1 — Application Example

### Example 1 — 1-minute faint curve + 20:37 UTC → first place

- **Type**: worked example.
- **Problem/input**: One faint Doppler curve + known time; continent-wide search
- **How the methodology was used**: velocity bounds + time slicing → candidates → trace-line distance scoring → histogram
- **Conclusion**: The single-event winner coordinates equal the multi-event winner's location
- **Result**: two-methodology cross-check holds; second place visibly deviates from the curve

### Example 2: One event, approximate time (generalized case)

- **Problem/input**: Time known only to ±10 minutes
- **How the methodology was used**: widen the time slice, rank candidates, report the time-induced candidate explosion
- **Result**: feasibility degrades gracefully but precision does not; state the time uncertainty

---

## A2 — Future Trigger ★

### In what situation will the user need this skill?

1. Only a single (even inaudible) aircraft curve remains, but the recording time is known
2. The user needs to check whether a multi-event conclusion is robust (second path)
3. The user wants to self-assess their own leakage risk (known-time exposure)

### Language signals

- "only one curve / single event + time known"
- "single event + known time / validate with UTC"
- "cross-check / cross-validation"

### Distinction from adjacent skills

- vs `locked-scoring`: single-curve distance scoring vs multi-event locked scoring
- vs `adsb-coarse-filter`: this card constrains candidates by absolute time; the coarse filter uses the event offset

---

## E — Execution

**Required input**: One Doppler curve (traced line) + known time with stated uncertainty; flight data for the date and region; `c`, `R_audible`, `type_filter`.
**Deliverable & completion**: Candidate ranking + winner + explicit agreement/disagreement with any multi-event result.

1. **Measure the curve**
 - Same measurement as the multi-event path (velocity band / slant band / f0)
 - Completion: curve reproducible as a trace-line scoring input
2. **Slice by time**
 - Keep only flight segments inside `t_known ± time_uncertainty` (including propagation delay)
 - Completion: non-empty candidate set; report the count
3. **Score the single curve**
 - Rank by distance from modelled curve to traced line; plot a histogram
 - Completion: winner unique, or explicit "gap insufficient"
4. **Cross-check**
 - If a multi-event conclusion exists, compare coordinates and state agreement/disagreement
 - Completion: both outcomes reported; never force "cross-check succeeded"

---

## B — Boundary ★

### Do not use this skill when

- Time unknown and only one event → constraints insufficient (needs a second event, a time, or a spatial prior)
- Faint curve cannot be traced → return to `doppler-event-extraction`
- A cross-check is treated as confirmation → imagery or an independent constraint must still confirm

### Failure modes to watch for

- Calling a small-gap winner "the same location" without a geographic agreement check
- Running a single event without a histogram and being misled by the gap
- Trusting a "known" time that is actually local time, or off by a time zone

### Method limitations

- **Line-trace threshold undisclosed (nr-06)**: distance scoring recorded as method only
- Depends on second-level time; everyday channels (phone, messaging, file metadata) leak such times — that is the premise risk
- Time uncertainty propagates directly into candidate count; report it

### Easily confused neighboring methodologies

- `locked-scoring`: single-event scoring vs multi-event referee
- `defense-assessment`: known time is both a risk factor and a self-check entry

---

## Related skills

- depends-on: `doppler-event-extraction`, `adsb-coarse-filter`
- composes-with: `locked-scoring`, `visual-verification`

---

## Audit

- **Verified**: V1 ✓ / V2 ✓ / V3 ✓
- **Generalized**: 2026-11-04 (20:37 UTC / 40.87 retained as reference example)

## Bundled resources

Paths are relative to this file; check preconditions before running anything.

- [resources/parameters.md](../../resources/parameters.md)
- [resources/data-sources.md](../../resources/data-sources.md)