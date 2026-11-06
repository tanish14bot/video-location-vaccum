# Contributing

Thanks for helping. This project values reproducible evidence over confident
claims.

## Development setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
python -m pip install -e ".[audio,geo,parquet,dev]"
pre-commit install
```

## Checks

```bash
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src/video_location_vaccum
python -m pytest -q -m "not slow"
python -m pytest -q -m slow        # end-to-end synthetic run, ~15 s
python -m build
```

All must pass before a pull request is reviewed.

## What we accept

- Bug fixes with a regression test.
- New data adapters that state their license, auth, and historical coverage.
- Better uncertainty quantification, validation, and documentation.
- Performance improvements with a benchmark.

## What we decline

- Features for real-time tracking, targeting individuals, or evading platform
  protections.
- Removing confidence labels, gate caps, or stop conditions.
- Claims of accuracy without a reproducible validation case.
- Vendored third-party media or data.

## Adding a data source

Implement the `FlightSource` / `DemSource` protocol and provide:

1. license and redistribution terms,
2. auth requirements,
3. historical coverage and update cadence,
4. field mapping and units,
5. a recorded fixture (synthetic or public-domain) for tests,
6. a failure path that raises `DataUnavailable` with an actionable ask.

## Commit style

Conventional commits are appreciated: `feat:`, `fix:`, `docs:`, `test:`,
`refactor:`, `chore:`.

## Developer Certificate of Origin

By contributing, you certify that you have the right to submit the work under
the project's Research-Only License (see `LICENSE`) and the DCO 1.1. Add
`Signed-off-by: Name <email>` to each commit.
