# Prior Art: Aircraft-Doppler Geolocation

The method is public and has been independently implemented many times. This
document records the landscape as of **2026-11-04**, what each project does,
what is reusable, and what we should adopt. It is based on repository metadata
and READMEs; **no code was copied** from these projects.

> If you are one of these authors and want a correction, open an issue.

## Direct implementations

| Repository | Stars | License | Validation | Notes |
|---|---:|---|---|---|
| [digitalis-p/doppler-locate](https://github.com/digitalis-p/doppler-locate) | 10 | MIT | **Real Oyster Bay case: rank 1 of 1,060 pairs, 67 m; 13 m peak in a 25 m heat map** | Best-documented real result. Uses NOAA GFS winds/temperature aloft, steady-tone removal, ±8% f0 / ±8 s tolerances, CPU/GPU. Single-event mode not reproduced. |
| [Espaye/aircraft-doppler](https://github.com/Espaye/aircraft-doppler) | 2 | MIT | **2 real recordings: 17 m and 114 m; 68/90% radii 35/125 m and 214/292 m** | Explicit uncertainty and a verdict. Synthetic 9 m with a 90% radius of 25 m. Straight-ray layered atmosphere, no refraction/terrain shadowing. |
| [leo-aa88/aerodoppler](https://github.com/leo-aa88/aerodoppler) | 7 | MIT | **29 real CC-BY phone recordings: median 391 m, 18 answered / 11 abstained; 55% within 500 m** | Honest benchmark, synthetic + semi-synthetic + real. Single-pass mirror solutions; uncalibrated scores. |
| [1337isnot1337/DOPPLERGEIST](https://github.com/1337isnot1337/DOPPLERGEIST) | 220 | **PolyForm Noncommercial 1.0.0** | 476 m from an *inferred* reference; **no blind real validation** | Most stars. Automatic discovery, browser UI, three country profiles, caches. Source-available, **not OSI open source**. |
| [Dicklesworthstone/franken_doppler_finder](https://github.com/Dicklesworthstone/franken_doppler_finder) | 25 | **MIT + AI rider** (custom) | One real recording, 267–306 m, graded low; documented wrong answers | Rust, end-to-end, five gates, weather/terrain/geocoding, ZIP output. Very honest status table. |
| [mojomast/hermes-aircraft-doppler-geolocation](https://github.com/mojomast/hermes-aircraft-doppler-geolocation) | 8 | MIT | 2 of 18 held-out runs under 3 km | Hermes plugin + CLI; clean multi-pass to ~1 km, mostly fails unseen clips. |
| [AlanBacker/audio-flyover-geolocation](https://github.com/AlanBacker/audio-flyover-geolocation) | 2 | MIT | 46 m synthetic, 0.9-score radius 182 m | Agent skill + Python pipeline, CI, English/Chinese. Closest to our skill positioning. |
| [Mearman/doppler](https://github.com/Mearman/doppler) | 1 | **none** | No published validation | TypeScript library, CLI, PWA, real-time ambition. Ideas only; no license. |
| [y0d4a/doppler-locator](https://github.com/y0d4a/doppler-locator) | 1 | **none** | Offline proof only | Streamlit workbench; explicitly "not a verified geolocation engine". |
| [cbonitz/doppler-experiments](https://github.com/cbonitz/doppler-experiments) | 1 | **none** | Synthetic: correct pair 6/6, observer 85–465 m | Independent verification report, built with a coding agent. |
| [jamesbiederbeck/acoustic-geolocation](https://github.com/jamesbiederbeck/acoustic-geolocation) | 0 | **none** | None published | Minimal Python implementation. |

## Adjacent and defensive

| Repository | Stars | License | What it does | Relevance |
|---|---:|---|---|---|
| [EvanBoyar/doppstop](https://github.com/EvanBoyar/doppstop) | 5 | **none** | Removes aircraft Doppler tones, 50/60 Hz mains hum, metadata; adds time/frequency warp; refills noise | **Direct defense competitor.** Per-frame tone subtraction + noise refill; metadata stripping; ENF removal. No license: ideas only. |
| [jdak907/provenance](https://github.com/jdak907/provenance) | 0 | **NOASSERTION** | Doppler + mains-hum ENF grid/time + video flicker + seismic reference | Broadest forensic clue set; privacy-check framing. No clear license: ideas only. |
| [Hexay/thunderprint](https://github.com/Hexay/thunderprint) | 12 | MIT | Thunder-delay geolocation against lightning networks; posterior map + 90% ellipse | Real recording, PyPI/crates, excellent uncertainty presentation. |
| [cajdata/earwitness](https://github.com/cajdata/earwitness) | 1 | Apache-2.0 | Thunder + aircraft Doppler; audit-first, defensive | Closest to our ethics/positioning; pre-alpha, no real validation yet. |
| [30hours/adsb2dd](https://github.com/30hours/adsb2dd) | 26 | MIT | ADS-B to delay-Doppler truth for passive radar | Useful independent truth generator; not acoustic. |
| [SiDongG/Multi-Source-Localization](https://github.com/SiDongG/Multi-Source-Localization) | 10 | none | TDOA/GCC-PHAT microphone-array localization | Array path for Phase 3; ideas only. |
| [matrn/AcousticDetection](https://github.com/matrn/AcousticDetection) | 8 | MIT | Two-microphone acoustic detection/localization | Simple TDOA reference. |

## What we should adopt

Ordered by accuracy-per-effort, based on their published results.

### 1. Winds and temperature aloft (highest impact)

`doppler-locate` reports the truth-point curve residual dropping from **0.55 Hz**
(still air, `c = 343`) to **0.21 Hz** with NOAA GFS profiles; a wind fitted from
the audio alone (14.4 m/s from 316°) agreed with GFS (15.1 m/s from 322°).

Our current model uses a constant `c`. This is now the largest correctness gap.
Adopt a GFS/ERA5 profile and an effective sound speed `c + w·n̂`, then ray-trace
or use a layered model. This is Phase 4 work, but it has a **larger** return
than multi-sensor arrays for real recordings.

### 2. Steady-tone removal before scoring

`doppler-locate` removes steady tones with a running median per frequency bin
before scoring; otherwise intermittent hums at 107, 160, and 241 Hz attract
wrong candidates. We already have `analysis/clues` for hum, but we do not
subtract steady tones from the scoring spectrogram. Add a `whiten` step:
subtract the per-bin median (or a robust baseline) before brightness scoring.

### 3. Wide f0 and clock tolerances

Their winning run used **±8% f0** and **±8 s** offset because straight-line fits
are biased when an aircraft descends or slows (event 2: fit 134.4 Hz vs true
geometry 126 Hz). Our defaults are ±5% and ±5 s. Widen, or fit a slow drift.

### 4. A real benchmark, not just synthetic

`aerodoppler` publishes a **29-recording CC-BY phone benchmark** (Pathak
Livermore set, Zenodo 23424278) with a manifest and per-case JSON, including
**11 abstentions** and mirror failures. This is the right external test for us:

- run our single-event known-time path on the 29 recordings;
- report top-1 median, best-of-top-3, abstention rate, and mirror rate;
- compare to their 391 m median and 55% within 500 m.

This directly addresses our "no real ground truth" blocker.

### 5. Uncertainty and verdict gates

`Espaye` reports 68/90% radii that contained both real errors; `franken` uses
five gates and documents wrong answers at low and medium confidence. Our triage
has gates, but the acoustic result still needs a calibrated radius and an
explicit "abstain" verdict. Adopt a bootstrap/Laplace radius and refuse when the
margin is thin.

### 6. Defense: tone subtraction, noise refill, metadata, hum

`doppstop` does what our defense module does **plus**:

- per-frame tone subtraction with **noise refill** (no bright or dark gap);
- 50/60 Hz mains-hum removal (ENF);
- metadata stripping (creation time, GPS, device, telemetry, subtitles, cover art);
- optional frequency/time warp.

We have notch/cut/mask/decoy but no metadata scrub, no ENF removal, and no
explicit noise refill. Add those. **Do not copy the code** (no license); the
techniques are standard DSP.

### 7. Browser/PWA and automatic discovery

`DOPPLERGEIST` and `Mearman/doppler` offer local browser/PWA workflows;
`DOPPLERGEIST` scans an entire recording for moving tracks and groups harmonics.
Our CLI is stronger for reproducibility, but a local UI would broaden adoption.
Lower priority than accuracy.

## What not to copy

| Project | Restriction |
|---|---|
| DOPPLERGEIST | PolyForm **Noncommercial**; source-available, not OSI. Ideas only. |
| franken_doppler_finder | "MIT + AI rider" custom license. Verify before any reuse. |
| doppstop, cbonitz, Mearman, y0d4a, jamesbiederbeck | **No license**; default copyright. Ideas only. |
| jdak907/provenance | NOASSERTION; unclear terms. Ideas only. |

For MIT/Apache projects, reuse is possible with attribution and license
retention, but we should prefer independent implementation to keep the
authorship and license story clean.

## Honest positioning

We are **not first** and **not the most validated**. As of this scan:

- `doppler-locate` has a **67 m** real result;
- `Espaye` has **17 m / 114 m** on two real recordings with uncertainty;
- `AeroDoppler` has a **29-recording** real benchmark at **391 m median**.

Our differentiators are:

1. **Triage-first**: visual/chronolocation, metadata, Eiffel rule, precision
   buckets, and explicit overrides before any acoustics.
2. **Audio-only** as a first-class path.
3. **Defense integrated** with a transformation manifest.
4. **Research-only licence** and no bundled media/data.
5. **Honest precision limits** and a refusal to call the score a probability.

The right response to this landscape is not to claim novelty. It is to adopt
the proven techniques, run the public benchmark, and publish our error.

## Sources

Repository metadata and READMEs were read via the GitHub API on 2026-11-04.
Validation numbers are the projects' own claims; they have not been independently
reproduced here. See each repository for its current status.
