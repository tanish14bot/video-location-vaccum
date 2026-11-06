# Glossary — Doppler Geolocation

> Shared terminology across all capabilities. Parameters marked *(generic)* replace values measured from a single recording.

| Term | Definition | Key distinction |
|---|---|---|
| Doppler curve | Frequency-over-time trajectory heard as an aircraft approaches and recedes | Not a single tone — a full spectrogram track shaped by flight geometry |
| ADS-B data | Position/speed/altitude + timestamps for aircraft, with a type field | Not a live API — requires a data source plus type-code classification |
| type-code | An identifier used to classify aircraft class (prop/jet/turboprop/helicopter) | Not directly a class — needs an external lookup; keep the filter explicit |
| CPA | Closest Point of Approach: the time the aircraft is closest (≈ curve midpoint, loudest) | Not a map point — a time anchor |
| delayed CPA | CPA + slant distance / speed of sound — when the observer actually hears CPA | Not flight time; it aligns flight data to the recording clock |
| slant distance | 3-D range using aircraft altitude and ground elevation (DEM) | Not horizontal distance; elevation must be included |
| DEM | Digital elevation model giving ground elevation at a point | ADS-B altitude is AMSL, not height above ground |
| radial velocity (Vr) | Velocity component along the aircraft→observer line | Not ground speed; abeam, Vr ≈ 0 and there is no Doppler shift |
| emission-time velocity | Vr at the moment the sound was emitted; heard time = emission time + slant/c | Not receive-time Vr — the wrong choice changes the curve's shape, not just its timing |
| fundamental frequency (f0) | Baseline frequency of the curve, found by sliding the measured curve | Not a constant — measured, uncertain, and swept during scoring |
| event offset *(generic)* | Time between two heard CPA moments, measured from the audio | A measured offset is one value; never a default |
| audibility radius `R_audible` *(generic)* | Assumed maximum slant range at which a flight can be heard | An engineering assumption, not a physical law; drives candidate count |
| grid step / refine step *(generic)* | Coarse sampling distance and its refinement | Must be fine enough for `R_audible`; quantization error bounds precision |
| locked scoring | Sweep Event-1 f0/time error; lock Event-2's relative offset to flight geometry | Not "two scores added" — locking is the precision core |
| silence constraint | No audible flight during the interval between events | Not "no signal" — a strong negative constraint that removes airport-like points |
| confidence label | Explicit statement of evidence level: confirmed / consistent-unconfirmed / contradicted | Not a substitute for a coordinate, and never omitted |
