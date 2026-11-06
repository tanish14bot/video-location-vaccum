# Release Checklist

Run this before tagging a public release.

## 1. Clean the tree

- [ ] `git status` shows only intended files.
- [ ] No media (`.mp4`, `.webm`, `.wav`, `.jpg`, `.png`) tracked.
- [ ] No `runs/`, `dist/`, `build/`, `*.egg-info/`, `__pycache__/`, `.pytest_cache/`.
- [ ] No `tools/`, research packs, or downloaded archives tracked.
- [ ] No absolute local paths (`C:\Users\...`, `/home/...`) in tracked text.
- [ ] No secrets, API keys, cookies, or `.env` files.

## 2. Metadata and URLs

- [ ] Repository URL in `pyproject.toml` and `CITATION.cff` is the real one.
- [ ] Copyright holder is correct in `LICENSE`/`NOTICE`.
- [ ] Version bumped in `pyproject.toml`, `src/video_location_vaccum/__init__.py`, `CITATION.cff`.
- [ ] `CHANGELOG.md` has a dated entry.

## 3. Quality gates

```bash
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src/video_location_vaccum
python -m pytest -q -m "not slow"
python -m pytest -q -m slow
python -m build
python -m twine check dist/*
python -m pip check
```

- [ ] All pass.
- [ ] `video-location-vaccum doctor` is green.
- [ ] `video-location-vaccum demo` recovers the synthetic truth within the documented tolerance.
- [ ] Audio-only path works: `triage`, `signals`, `events`, `run`.
- [ ] Defense: `leakage` → `defend --mode notch` → `leakage` reports none.
- [ ] Triage: Eiffel evidence skips; `--force-pipeline` overrides; street precision forces the pipeline.

## 4. Content and claims

- [ ] README does not claim "any video" or "military grade".
- [ ] `docs/PRECISION.md` limits are current.
- [ ] `docs/TRIAGE.md` rubric and Eiffel rule match the code.
- [ ] `docs/DEFENSE.md` warnings match the CLI guardrails.
- [ ] No screenshots, frames, audio, or video from third parties are bundled.
- [ ] Third-party license and attribution notices in `NOTICE` are accurate.

## 5. Packaging

- [ ] Wheel contains the package and `py.typed`.
- [ ] sdist contains README, LICENSE, NOTICE, pyproject, src.
- [ ] `pip install dist/*.whl` works in a clean venv.
- [ ] `video-location-vaccum --help` lists all commands.
- [ ] Docker build works (optional).

## 6. Repository settings

- [ ] Description, topics, and license set on the host.
- [ ] Branch protection and required checks enabled.
- [ ] Security advisories enabled.
- [ ] Issue/PR templates present.
- [ ] `ETHICS.md` and `SECURITY.md` linked from the README.

## 7. Tag

```bash
git tag -s v0.1.0a0 -m "v0.1.0a0"
git push origin v0.1.0a0
```

Do not publish media or data with the release.
