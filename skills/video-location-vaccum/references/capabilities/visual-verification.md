<!-- capability_id: cap.doppler.visual-verification | revision: 2 | status: active -->

# Visual Verification to the Scene: Heat Maps + Street-View Feature Sequence

## I — Interpretation

A score is not a place. Visual verification has two jobs: (1) view per-event score surfaces over flight routes to see whether the high-score region is a coherent block or scattered noise; (2) match a **feature sequence** in street-level imagery by relative order and shape, not by keyword. The recording's "V-shaped tree → point → big rounded part" plus a pole camera is one instance; the general rule is to pick durable, orderable features (tree lines, shoreline curvature, building silhouettes, poles, signs) and require several to align in sequence. A single matching feature is weak; a sequence that locks in order is strong.

---

## A1 — Application Example

### Example 1 — bank point + V tree + camera

- **Type**: worked example.
- **Problem/input**: refined winner (bank in water) + reference photo (pixelated treeline + pole)
- **How the methodology was used**: score heat map → streets near the bank → treeline sequence → pole camera
- **Conclusion**: the same feature sequence appears at matching points; the pole camera is the recording device
- **Result**: coordinates land on a specific camera and the scene it faces

### Example 2: No durable landmark (generalized case)

- **Problem/input**: winner point in open terrain with no structures
- **How the methodology was used**: verify terrain shape, road geometry, horizon profile; state that confidence is lower
- **Result**: "geometrically consistent, visually unconfirmed" — not a confirmed place

---

## A2 — Future Trigger ★

### In what situation will the user need this skill?

1. The user has a winner point (lat/lon) and needs imagery confirmation
2. The user needs to explain why the point sits on water/roof/road edge
3. The user needs to turn a numeric win into a presentable place

### Language signals

- "verify the location / Street View / map confirmation"
- "which tree / pole / building is this"
- "scores won, so where is it"

### Distinction from adjacent skills

- vs `locked-scoring`: scoring is the numeric entry; verification is place confirmation
- vs `single-event-known-time`: verification is final confirmation; cross-check is method-to-method agreement

---

## E — Execution

**Required input**: Winner lat/lon (+ runner-up); a map/QGIS tool; street-level imagery or reference photos.
**Deliverable & completion**: A place description with an ordered feature sequence, the camera/landmark if visible, and an explicit confidence level.

1. **Overlay score surfaces**
 - Per-event heat maps + flight routes over the region → narrow to a coherent high-score block
 - Completion: block pinned; scattered scores flagged as unstable
2. **Build a feature list from the recording**
 - Ordered durable features: skyline, tree line, shoreline, poles, signage, road curvature
 - Completion: at least 3 orderable features, or "insufficient features"
3. **Match in imagery**
 - Walk the candidate streets; require the sequence to match in order and relative position
 - Completion: sequence match or explicit failure
4. **Check the recording device**
 - If a pole/box/camera is visible, align it item by item with the recording's viewpoint
 - Completion: device located, or confidence downgraded
5. **State the conclusion**
 - "Confirmed at feature-sequence level", "geometrically consistent but visually unconfirmed", or "contradicted"
 - Completion: never a bare coordinate without a confidence label

---

## B — Boundary ★

### Do not use this skill when

- No imagery available → cannot land the point; report the coordinate as unverified
- No durable visual detail and forced feature matching → easy false match
- Forcing a water/roof high point into the nearest building → check geometry/elevation first

### Failure modes to watch for

- Treating "high point in water" as an error — a bank camera is a reasonable point (this recording's winner is exactly that)
- Matching a single feature and calling it confirmation
- Ignoring imagery dates: a tree may have grown or a building may be gone

### Method limitations

- Only one imagery-matching example is shown; feature extraction has no rule or threshold
- Coverage and update cadence of street-level imagery vary by country; some regions have none
- Image dates can postdate or predate the recording

### Easily confused neighboring methodologies

- `locked-scoring`: scores are not the final place
- `single-event-known-time`: method agreement is not visual confirmation

---

## Related skills

- depends-on: `locked-scoring`, `single-event-known-time`
- composes-with: `defense-assessment` (risk awareness)

---

## Audit

- **Verified**: V1 ✓ / V2 ✓ / V3 ✓
- **Generalized**: 2026-11-04 (QGIS/Street View are examples; any map/imagery tool qualifies)

## Bundled resources

Paths are relative to this file; check preconditions before running anything.

- [resources/parameters.md](../../resources/parameters.md)
- [resources/data-sources.md](../../resources/data-sources.md)