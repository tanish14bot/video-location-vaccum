<!-- capability_id: cap.doppler.defense-assessment | revision: 2 | status: active -->

# Acoustic Leakage Risk Assessment & Defense

## I — Interpretation

Start from a self-check: does the audio you plan to publish contain a measurable Doppler signature? If it does, the defenses people reach for do not remove it. High-pass filtering sits in the same band as the voice, so it damages speech and the curve returns after lossy re-encoding. Drowning it out (playing music, adding noise) masks but does not erase the curve. Phone codecs and noise reduction do not erase it either; they leave other artifacts. What actually helps is destroying the **time relationship** the method depends on: cuts that break the event offset, plus masking parts of the voice, plus care about what absolute time you reveal. A useful boundary: acoustic leakage is one vector among many easier ones, so do not treat "no Doppler" as "not locatable."

---

## A1 — Application Example

### Example 1 — drown-out still visible; phone mute gap

- **Type**: worked example.
- **Problem/input**: Video with audible voice (speaker playing in the room + phone call)
- **How the methodology was used**: Test cut / high-pass / drown / phone compression one by one; muting reveals the phone-path gap
- **Conclusion**: All three fail; cut/mask still work
- **Result**: risk judgment + defense checklist

### Example 2: General publishing workflow (generalized case)

- **Problem/input**: A normal publishing edit: music bed, EQ, phone-recorded audio, cuts
- **How the methodology was used**: check each stage for curve survival; test the final export rather than the source
- **Result**: defense decisions are made on the **published** file, not the project file

---

## A2 — Future Trigger ★

### In what situation will the user need this skill?

1. The user wants to post a video but is worried about being located
2. The user knows the recording time and sends it via phone/messaging, wanting a leak self-check
3. The user wants a pre-posting assessment (should I cut? which defenses are theater?)

### Language signals

- "defend / protect myself / avoid location / prevent geolocation"
- "high-pass / silence / noise / is a phone call easier to locate"
- "can this be defended"

### Distinction from adjacent skills

- vs `single-event-known-time`: defense judges your own video; that card is how the other side locates you
- vs `doppler-event-extraction`: defense is risk judgment; extraction is concrete measurement
- Not a substitute for checking metadata, visuals, or network vectors

---

## E — Execution

**Required input**: The exact file to be published (final export, not the project); delivery channel (edited / phone / social platform).
**Deliverable & completion**: A risk list + recommended actions + a statement of what remains unprotected.

1. **Check the published file for curves**
 - Spectrogram the final export; mark any falling narrowband tracks and their times
 - Completion: curve presence/absence stated per segment
2. **Check the time surface**
 - Does the recording or its metadata reveal the recording time? Do multiple curves give an offset?
 - Completion: time-leak list
3. **Test the three common defenses**
 - high-pass: same band as voice, untrustworthy, damages speech
 - drown: masking ≠ erasing
 - phone: compression ≠ erasing
 - Completion: each marked "not sufficient alone"
4. **Apply workable actions**
 - Cut to break the event offset; mask parts of the voice; remove/round absolute time
 - Completion: at least one executable action with its cost stated
5. **Re-test after editing**
 - Spectrogram the new export; confirm the offset is actually broken
 - Completion: before/after evidence

---

## B — Boundary ★

### Do not use this skill when

- high-pass / drown / phone is treated as "defended"
- Defense is treated as "never locatable" → real-world probability is low but hundreds of easier vectors exist
- "No visual clues" is confused with "no acoustic clues"
- The check is done on the project file instead of the published export

### Failure modes to watch for

- ce02 high-pass, ce03 drown, ce04 phone (see each card's B section for verbatim quotes)

### Method limitations

- Defense judgment is limited to the three live tests in the recording; no frequency/time parameters given
- There are likely hundreds of easier vectors; this card covers only the acoustic surface
- Platform re-encoding after upload can change results; test the platform's output too

### Easily confused neighboring methodologies

- `single-event-known-time`: known-time leak multiplies risk
- `doppler-event-extraction`: measure before defending

---

## Related skills

- depends-on: `doppler-event-extraction`
- composes-with: `single-event-known-time`, `visual-verification`

---

## Audit

- **Verified**: V1 ✓ / V2 ✓ / V3 ✓
- **Generalized**: 2026-11-04 (defense advice framed as general publishing self-check)

## Bundled resources

Paths are relative to this file; check preconditions before running anything.

- [resources/parameters.md](../../resources/parameters.md)
- [resources/data-sources.md](../../resources/data-sources.md)