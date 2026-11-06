# Security Policy

## Supported versions

`0.1.x` is an alpha. Security fixes are applied to the latest release only.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately to the
maintainers through the repository's private security advisory feature, or by
email to the address listed in `pyproject.toml` once a maintainer address is
published. Include:

- affected version and platform,
- a minimal reproduction,
- impact (what an attacker gains),
- whether the issue is in the package or in an optional adapter.

We aim to acknowledge within 7 days and to publish a coordinated fix.

## Threat model

`video-location-vaccum` processes untrusted media and (optionally) fetches third-party data.

| Asset | Threat | Mitigation |
|---|---|---|
| Local files | Malicious media exploits the decoder | Use a maintained ffmpeg; the package never executes media |
| Network | SSRF via user-supplied URLs | Adapters only call fixed provider hosts, except explicit user URLs |
| Credentials | API keys leak into logs or configs | Keys are read from environment/config, never written to reports |
| Scraped pages | Prompt injection in page text | Scraped content is data, never instructions; never auto-executed |
| Browser fetchers | Arbitrary page execution | Disabled by default; `scrapling install` is explicit |
| Output | A confident wrong location causes harm | Confidence labels, gate caps, and sensitivity checks are mandatory |

## Secrets

- Never commit `.env`, API keys, cookies, or downloaded personal media.
- `.gitignore` excludes media and env files.
- Reports record the source URL and retrieval time, not credentials.

## Data provenance

Every run can emit a provenance record: file hash, source, retrieval time,
parameter values, tool version, and rubric version. Keep it with the result.

## Scraping

The optional Scrapling integration must respect `robots.txt`, rate limits, and
each provider's terms. It must not bypass authentication or CAPTCHAs. Legal
classification of each source is documented in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Dependency hygiene

CI runs `pip-audit` and a locked install. Optional adapters are isolated behind
extras so the core package has a small attack surface.
