# Defense: Removing, Masking, and Decoying Doppler Signatures

This module is for **your own recordings**, or recordings you are authorized to
modify. It changes the evidence. Keep the transformation manifest and do not
present an altered file as an unmodified original.

## What the defense is trying to break

The acoustic method needs:

1. a measurable curve,
2. a second event (or a known time),
3. a time offset that survives processing.

Defense can attack any of the three. Removing the curve is the most direct;
breaking the offset is the most robust.

## Implemented

```bash
# 1. Does this file leak a usable signature?
video-location-vaccum leakage --audio clip.wav --out-dir runs/leak

# 2. Remove the ridge corridor (default)
video-location-vaccum defend --audio clip.wav --out sanitized.wav --mode notch --width-hz 25

# 3. Break the two-event offset by cutting the stronger event
video-location-vaccum defend --audio clip.wav --out cut.wav --mode cut

# 4. Notch + shaped masking noise
video-location-vaccum defend --audio clip.wav --out masked.wav --mode mask --snr-db 12

# 5. Notch + synthetic decoy curves (requires acknowledgement)
video-location-vaccum defend --audio clip.wav --out decoy.wav --mode decoy --decoys 2 --i-understand
```

Every output writes `*.transform.json` with:

- source/output SHA-256,
- mode and parameters,
- before/after leakage summary,
- a warning that the file is altered.

## Measured result (synthetic regression)

| Stage | Events | Max SNR | Risk |
|---|---:|---:|---|
| Before | 1 | 51.6 dB | medium |
| Notch, 25 Hz | **0** | — | **none** |

The notch follows the **ridge trajectory**, not the constant `f0`. That
distinction is the difference between removing the leak and removing nothing.

## What works and what does not

| Defense | Works? | Why |
|---|---|---|
| High-pass filter | No | Curve and voice share the band; lossy re-encoding restores the curve |
| Drown out with music/noise | No | Masking raises the floor but does not erase a narrowband ridge |
| Phone codec / noise reduction | No | Compression preserves the curve; gating leaves artifacts |
| Time-cut one event | **Yes** | Destroys the two-event offset |
| Notch the ridge corridor | **Yes** | Removes the measurable curve |
| Notch + masking noise | **Yes** | Removes the ridge and lowers residual SNR |
| Decoy curves | **Ambiguous by design** | Adds competing signatures; may invalidate authenticity |

Measured with the synthetic fixture: before `medium` (51.6 dB), after `notch`
`none`, after `cut` `none`, after `mask` `none`. The detector is the same one
the attack path uses, so this is a real before/after test, not a visual claim.

## Limits

- **Re-recording through a speaker and microphone** can reintroduce a curve in
  the room, though it also changes the geometry and levels.
- **Other vectors remain**: metadata, visuals, language, mains hum, upload time.
  Removing Doppler is not "anonymous".
- **Cuts are audible** and may be detected as edits.
- **Decoys are counter-forensic.** They can make a file look fabricated, break
  C2PA/authenticity claims, and may be unlawful in some contexts (fraud,
  insurance, legal evidence). The CLI requires `--i-understand`.
- **No guarantee**: an adversary with the original, another recording, or
  independent data can still geolocate.

## Recommended workflow

1. `video-location-vaccum leakage` — record the before state.
2. Choose the least destructive mode that clears the risk:
   - `cut` if one of two events can be removed without ruining the content;
   - `notch` if the background is important;
   - `mask` if residual artifacts are acceptable;
   - `decoy` only with a clear disclosure plan.
3. `video-location-vaccum leakage` on the output — verify the ridge is gone.
4. Review metadata, visuals, speech, and platform upload settings separately.
5. Keep `*.transform.json`; disclose that the file was altered when required.

## Ethics and law

- Only your own content, or content you are authorized to modify.
- Do not use decoys to fabricate evidence, defraud, or mislead an investigation.
- Do not strip provenance from someone else's file.
- Removing a signature can reduce the evidentiary value of a recording. If the
  file is needed for a legal or journalistic purpose, preserve the original and
  work on a copy.
- See [ETHICS.md](../ETHICS.md).
