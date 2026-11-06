# Decision-rule cheatsheet - aircraft Doppler geolocation

| Capability | One-line rule |
|---|---|
| Doppler spectrogram event extraction and curve measurement | Measure each visible track as an interval: depth → velocity band, rate → slant-range band, plus f0 and heard CPA time; count how many events actually exist. |
| ADS-B coarse filter: delayed-CPA timing with range and silence funnel | Delayed CPA on a justified grid, matched to the measured event offset, then velocity/range bands and silence; airport clusters are expected, not signal. |
| Doppler modeling with emission-time radial velocity and the Doppler equation | Per heard time, back out emission time and use Vr_emit through the Doppler equation; receive-time Vr makes the whole shape wrong. |
| Locked scoring: brightness comparison, measurement-error sweep, grid refinement | Brightness sum + Event-1 sweep + locked Event-2 offset + grid refinement pick the winner; compare scores only within one run. |
| Single event plus known time: single-curve search with cross-check | One faint curve plus a known time can still locate the place and cross-check a multi-event winner; time uncertainty propagates into candidate count. |
| Visual verification with score maps and imagery feature sequence | Score maps narrow the block; an ordered feature sequence in street-level imagery confirms the place, otherwise confidence is downgraded. |
| Acoustic leakage risk assessment and defense | High-pass, drowning-out and phone compression do not remove Doppler; only cuts that break the time offset plus masking help, and other vectors remain. |

> Cheatsheet gives conclusions only; read the capability card for reasoning, cases, and counter-examples.
