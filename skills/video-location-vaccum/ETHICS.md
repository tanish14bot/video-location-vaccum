# Acceptable Use and Ethics

`video-location-vaccum` recovers the location of a recording. That capability can protect
people (verifying a claim, checking your own leakage) or harm them (stalking,
doxxing, harassment, targeting). The license limits use to non-commercial
research and excludes unauthorized surveillance; this document adds the
maintainers' expectations and the project's ethical boundaries.

## Allowed

- Your own recordings, or recordings you have permission to analyze.
- Journalistic, research, humanitarian, and forensic verification with a
  legitimate public interest.
- Privacy self-checks: does my own video leak my location?
- Safety and emergency response where a false positive is treated as a serious risk.
- Education and reproducible research on synthetic or consented data.

## Not allowed

- Locating a private individual's home, workplace, shelter, or routine.
- Harassment, stalking, doxxing, intimidation, or "doxxing by proxy".
- Real-time tracking or persistent surveillance of people.
- Circumventing platform protections, paywalls, or access controls to obtain data.
- Publishing coordinates of vulnerable people, safe houses, or critical
  infrastructure whose location is itself sensitive.
- Presenting an uncalibrated score as a certainty, or stripping the confidence
  label from a result.

## Harm triage comes before the confidence gate

If the target is a private individual, a vulnerable person, a shelter, or
sensitive infrastructure, the correct output is a **restricted result**:
coarser precision, no published coordinates, or a refusal. A high confidence
score does not override this. The rubric encodes this as a forcing condition.

## Data minimization

Collect only what the question requires. Prefer aggregate coordinates over
per-person tracks. Set a retention limit for cached media and derived artifacts.
Do not build a location database of individuals.

## Overrides

A user may force the acoustic pipeline at any time. A user may not force a
higher confidence, and may not use an override to suppress a red flag. In
legal or forensic use, a forced skip is refused.

## Accuracy and honesty

- A coordinate without a precision bucket and confidence label is not a result.
- A single pass gives a distance and a mirror pair, not a point. Say so.
- If the evidence does not support a claim, the correct answer is "not determined".
- Do not describe this tool as "military grade". The published precision limits
  are in [docs/PRECISION.md](docs/PRECISION.md).

## Reporting misuse

Maintainers may decline contributions that add targeting, real-time tracking,
or individual-surveillance features, even where a separate licence might permit
the code to be used that way. Report concerns privately via the process in
[SECURITY.md](SECURITY.md).

This document is guidance, not legal advice. Local law may impose additional
obligations (privacy, data protection, wiretapping, harassment).
