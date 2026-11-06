# Signals Beyond Doppler

Doppler is one constraint. The strongest results combine independent clues, and
the honest ones say which clues are independent. This is the roadmap of what to
look for and what is implemented.

## 1. Metadata and container

| Signal | What it can yield | Reliability | Status |
|---|---|---|---|
| EXIF `GPSLatitude/Longitude` | Exact capture point | High if present, but editable | via ffprobe/ExifTool (planned) |
| EXIF `DateTimeOriginal`, `OffsetTime` | Capture time + timezone | Medium; editable | via ffprobe (partial) |
| `Make`, `Model`, `LensModel`, `SerialNumber` | Device class / device linkage | Medium | planned |
| `Software`, `ProcessingSoftware` | Editing pipeline | Low for location | planned |
| XMP / IPTC / `OwnerName` | Author, city, instructions | Low–medium | planned |
| QuickTime `creation_time`, `location.ISO6709` | Time + GPS | Medium | via ffprobe |
| ID3v2 `TXXX`, `PRIV`, `GEOB`, `COMM` | Encoder, source, GPS, notes | Low–medium | planned |
| RIFF `INFO` (`INAM`, `IART`, `ICMT`, `ISFT`) | Title/artist/software | Low | via ffprobe |
| BWF `bext` (Originator, OriginationDate/Time, TimeReference) | Recorder, date, sample-accurate clock | **High for time** | planned |
| iXML / AXML | Production metadata, scene/take | Medium | planned |
| Container encoder/muxer, track UID, chapter names | Workflow fingerprint | Low | partial |
| Filename, upload time, platform IDs | Context | Low alone; useful for provenance | partial |

**Rule:** metadata can contradict a claim more reliably than it can support one.
It is writable by design.

## 2. Acoustic scene

| Signal | What it can yield | Method | Status |
|---|---|---|---|
| Mains hum 50/60 Hz + harmonics | Grid region (Europe/Asia/Africa vs Americas) | Welch PSD, harmonic ratios | **implemented** (`signals`) |
| Hum harmonic fingerprint | Building/device fingerprint, not geolocation | Harmonic amplitude pattern | planned |
| Reverb / RT60 | Indoor/outdoor, room size, cathedral vs room | Schroeder decay from transients | heuristic (`signals`) |
| Speech language / accent | Country/region | ASR language ID, accent model | planned |
| Bird / insect species | Biome and season | BirdNET / insect classifiers | planned |
| Church bells, sirens, school bells | Country/region, time-of-day schedule | Event detection + templates | planned |
| Transport: train, tram, bus, horn | Country/region, line | Spectral templates | planned |
| Water: surf, river, rain | Coast/river/weather | Spectral + temporal statistics | planned |
| Wind, thunder, rain | Weather, season | Event detection + historical weather | planned |
| Room tone / HVAC | Indoor environment | Low-frequency stationarity | planned |
| Recorder clock drift | Device linkage, not location | Pilot tone / drift estimation | planned |
| Codec / platform transcoding | Provenance, processing chain | Bitstream + spectral holes | planned |

**Leads, not proofs.** A 50 Hz hum says "probably a 50 Hz grid", not "this city".

## 3. Aircraft-specific acoustics

| Signal | What it can yield | Method |
|---|---|---|
| Blade-pass frequency `BPF = N_blades · RPM / 60` | Prop/turboprop type, blade count | Harmonic series + fundamental tracking |
| Harmonic ratios | Engine type, prop vs jet | Cepstrum / harmonic product spectrum |
| Tone stability | Turbofan vs turboprop vs drone | Frequency drift over the pass |
| Number of engines | Multi-tone / spatial mixture | Multi-pitch estimation |
| Approach vs departure | Throttle state, airport proximity | Frequency and amplitude evolution |
| Rotor thump (helicopter) | Rotor blade-pass and tail rotor | Low-frequency periodic modulation |
| Jet broadband roar | Aircraft class, range | Spectral slope, no narrow tone |

This is the highest-value acoustic addition: it turns a candidate flight into a
**type-checked** candidate, and it can disambiguate two flights with similar CPA
timing.

## 4. Visual and cross-modal

| Signal | What it can yield | Method | Status |
|---|---|---|---|
| Sun direction / shadow length | Latitude ring + time check | SunCalc / Shadow Finder | planned |
| Star field | Latitude, date, time | Astro pattern matching | planned |
| Moon phase / position | Date/time corroboration | Ephemeris | planned |
| Terrain / skyline profile | Region, route | DEM horizon matching | planned |
| Vegetation / soil / crop state | Climate band, season | Classifier + seasonal priors | planned |
| Architecture / road furniture | Country/city | OSM/Mapillary feature search | planned |
| License plates | Jurisdiction | OCR + format rules | planned |
| Signage / language | Country/region | OCR + language ID | planned |
| Reflections in glass | Opposite-side scene | Manual/geometry | planned |
| Utility poles, bollards, hydrants | City/region | Object detection + OSM | planned |
| Camera sensor fingerprint (PRNU) | Device linkage | PRNU correlation | research |
| Lens/sensor artifacts, rolling shutter | Device class, drone/camera | Metadata + geometry | planned |
| Weather / clouds | Date/time corroboration | Historical weather + classifier | planned |

## 5. Independence hierarchy

| Tier | Evidence | Independent of |
|---|---|---|
| A | Terrain, sun/shadow, measured geometry, dated reference imagery | The claimant |
| B | Signage, language, plates, road markings | Other cues in the same frame (not the claimant) |
| C | A second recording, witness, sensor, official record | The original uploader |
| D | Caption, geotag, uploader claim | Nothing |
| E | Other posts citing the same original | Nothing |

**Within-frame convergence supports location, not authenticity.** Only Tier C
breaks circularity. The triage rubric encodes this as the cross-source cap.

## 6. Improvement roadmap

| Priority | Improvement | Impact | Effort | Status |
|---:|---|---|---|---|
| 1 | Audio-only triage + signals | Enables music/audio cases | S | **done** |
| 2 | Metadata extractor (EXIF/ID3/BWF/XMP) | High-value leads | S | partial |
| 3 | Mains hum + reverb | Region/environment prior | S | **done (basic)** |
| 4 | Speech language ID | Country/region | M | planned |
| 5 | Aircraft type from BPF/harmonics | Candidate disambiguation | M | planned |
| 6 | Sun/shadow + star-field solver | Independent chronolocation | M | planned |
| 7 | OSM/Mapillary feature search | Street-level narrowing | L | planned |
| 8 | Multi-event / multi-sensor (TDOA, array) | Resolves mirror; metres | L | planned |
| 9 | Atmospheric ray tracing + wind profile | 1.5–4% range error removed | L | planned |
| 10 | Calibrated audit set (≥50/bucket) | Makes confidence a probability | L | planned |
| 11 | Real-data ground truth | Proves the physics | L | **blocking v1.0** |
| 12 | Continent-scale chunking | CONUS runs | L | planned |

## 7. How to combine clues without double counting

1. List each clue with its tier and its independent source.
2. Remove duplicates that share the same capture event.
3. Apply the triage gates: provenance, authenticity, uniqueness, temporal,
   negative control, precision discipline, integrity.
4. Use the acoustic pipeline as an **independent** constraint, not as a
   tie-breaker for a visual guess.
5. Report the result at the coarsest precision that all surviving evidence
   supports.

## 8. What not to do

- Do not treat a single landmark as proof of a street address; replicas exist.
- Do not treat a geotag as ground truth; it is editable.
- Do not treat "no C2PA manifest" as evidence of tampering.
- Do not treat a metadata mismatch as proof of a deepfake; platforms rewrite
  metadata routinely.
- Do not add clues that are not independent and call it corroboration.
