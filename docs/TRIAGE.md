# Evidence Triage

The pipeline is expensive and can be invalidated by a music bed, a codec, or a
staged scene. Triage decides whether the location is already established, and
records why.

## The three questions

| Question | Answered by | Failure |
|---|---|---|
| Where was this captured? | Feature matching, terrain, chronolocation | Lookalike place |
| Is this recording what it claims? | Provenance, corroboration, synthetic-media screen | Game engine, film set, AI |
| Is the location established to the standard this use requires? | Evidence chain, independence, custody | Strong match, weak basis |

A clip can score 0.95 on location and 0.30 on authenticity. The gate must not
collapse them into one number.

## Precision buckets

The score is meaningless without the precision it claims:

`country → region → city → street → point`

A result that supports a city does not support a street. `requested_precision`
is what the user asked for; if the evidence is coarser, the pipeline runs.

## Evidence items and weights

| Item | Weight | 1.0 anchor |
|---|---:|---|
| Unique landmark / structure | 0.18 | ≥2 rare features, consistent from ≥2 viewpoints |
| Micro-cues (text, plates, markings) | 0.14 | ≥3 region-specific, mutually consistent |
| Reference imagery | 0.14 | High-resolution, dated within ~±2 years |
| Terrain / skyline | 0.10 | Quantitative profile match |
| Chronolocation | 0.12 | Quantitative sun/shadow match within uncertainty |
| Independent corroboration | 0.16 | A genuinely separate source or method |
| Source reliability | 0.08 | Established source, no incentive to mislead |
| Disconfirmation | 0.08 | ≥3 mismatch hypotheses tested and rejected |

## Gates are caps, not weights

The final score is `min(weighted sum, gate caps, condition caps)`. A weighted
average would let a strong landmark paper over a broken chain of custody.

| Gate | Fail cap | Partial / unknown cap |
|---|---:|---:|
| Provenance | 0.45 | 0.75 |
| Authenticity | 0.00 | 0.35 |
| Uniqueness + eliminated alternatives | 0.50 | 0.50 |
| Temporal consistency | 0.40 | 0.80 |
| Negative control | 0.60 | 0.60 |
| Precision discipline | 0.55 | 0.55 |
| Integrity / custody | 0.60 (0.00 in legal) | 0.60 |

Additional condition caps:

| Condition | Cap |
|---|---:|
| AI geolocator is the sole basis | 0.35 |
| Replicas / lookalikes not excluded | 0.50 |
| Reference imagery undated | 0.70 |
| No cross-source evidence | 0.80 |

## Authenticity and provenance

`video-location-vaccum triage` records the file's SHA-256, container metadata, and a C2PA
check when `c2patool` is installed. Be precise about what this proves:

- a hash proves the bytes have not changed since **you** hashed them;
- a valid C2PA manifest proves the signed assertions are intact and trusted;
- neither proves the scene is real, the date is correct, or the location is true;
- absence of a manifest is normal and is not evidence of tampering.

Forensic/legal mode forces the acoustic pipeline and preserves the provenance
record, even when the visual identification looks conclusive.

## Landmark sufficiency (the Eiffel rule)

At **country / region / city** precision, one unambiguous landmark can be
enough. If:

- the unique-landmark item scores ≥ 0.90,
- dated reference imagery scores ≥ 0.80,
- the uniqueness gate passes and replicas are excluded,
- provenance and authenticity have not failed,

then the score is floored at **0.92**, and the pipeline may be skipped. This
never applies at **street / point** precision, and any evidence failure removes
the floor. That is why "a person in front of the Eiffel Tower" can answer a
city question without acoustics, while "which bench in the park" cannot.

## Decision

```
if mode is forensic/legal/safety/publication     -> pipeline
if authenticity disputed                         -> pipeline
if target is a private individual                -> pipeline + restricted result
if precision is coarser than requested           -> pipeline
if confidence >= 0.90 and gates pass             -> skip (visual/text result)
if 0.75 <= confidence < 0.90                     -> probe (targeted check)
otherwise                                        -> pipeline
```

## Forcing triggers

Any one forces the full pipeline regardless of the visual score:

1. Forensic, legal, insurance, regulatory, or publication use.
2. Disputed authenticity, or metadata inconsistent with the pixels.
3. The claim will describe the acoustic result as independent corroboration.
4. The user asks for the kinematics (speed, heading, pass timing), not just a place.
5. The target is a private individual, vulnerable person, shelter, or sensitive infrastructure.
6. The visual ID rests on one cue, or a landmark with known replicas.
7. The user requests full processing.
8. The file is the only copy and may disappear.

## Overrides

- `force_pipeline` / `--mode doppler` / `--mode forensic`: always allowed.
- `ignore_visuals`: always allowed; acoustics only.
- `force_skip`: allowed only outside legal/forensic, and the result is labelled
  **"not pipeline-verified"**, capped at 0.75.

**Overrides spend money; they do not buy confidence.** A skip never raises the
reported score.

## Filling `evidence.json`

```json
{
  "claim_place": "Eiffel Tower, Paris",
  "precision": "city",
  "requested_precision": "city",
  "mode": "exploration",
  "candidates_examined": 3,
  "target_is_private_individual": false,
  "authenticity_disputed": false,
  "ai_geolocator_sole_basis": false,
  "reference_imagery_undated": false,
  "landmark_replicas_not_excluded": false,
  "has_cross_source": true,
  "gates": {
    "provenance": "pass",
    "authenticity": "pass",
    "uniqueness": "pass",
    "temporal": "pass",
    "negative_control": "pass",
    "precision_discipline": "pass",
    "integrity": "pass"
  },
  "evidence": [
    {"kind": "unique_landmark", "score": 1.0, "note": "tower geometry from two angles"},
    {"kind": "micro_cue", "score": 0.9, "note": "street furniture and signage"},
    {"kind": "reference_imagery", "score": 0.9, "note": "street-level imagery dated 2025"},
    {"kind": "terrain", "score": 0.6, "note": "river bank and bridge line"},
    {"kind": "chronolocation", "score": 0.8, "note": "shadow consistent with timestamp"},
    {"kind": "independent_corroboration", "score": 0.8, "note": "second uploader, different angle"}
  ]
}
```

Then:

```bash
video-location-vaccum decide --evidence evidence.json
video-location-vaccum decide --evidence evidence.json --force-pipeline
```

## Calibration warning

The weights and caps are a design proposal, not validated probabilities. Until
an audit set exists, the output is an **uncalibrated score**. Do not call it a
probability, and do not quote ">90%" as if it were a frequency.
