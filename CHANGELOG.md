# Changelog

## 0.1.4 — 2026-11-12

- Fix `__version__` lagging behind `pyproject.toml`: it still read 0.1.0
  on the 0.1.3 install, so `paper-radar --version` printed 0.1.0 while
  pip reported 0.1.3. New regression test asserts `__version__` matches
  `pyproject.toml`, so a future bump cannot silently drift again.

## 0.1.3 — 2026-11-11

- Discoverability: the PyPI description now names Claude as an alternative
  backend alongside Jev, and the keywords add `claude` and `anthropic`;
  the README first screen says the radar also runs on Claude (Haiku), with
  a link to the Claude section and the first-look calibration doc. The PyPI
  page itself only changes once this release is published.
- Claude calibration, first look: new `docs/claude-calibration.md` — Claude
  Haiku 5.5 judged 49 papers from the 2026-11-11 arXiv listing (6 relevant),
  Brier 0.040, ECE 0.081, suggested Claude thresholds must_read 0.65 /
  maybe 0.35 (versus Jev 0.80 / 0.50). Labels were made by Muse, not by the
  user, from titles and trimmed abstracts — a first look, not a
  user-validated calibration. Thresholds in `radar.toml` are unchanged.

## 0.1.2 — 2026-11-11

- Honest calibration labelling (A6): `paper-radar check` now warns when
  the backend is Claude that its probabilities are self-reported, not
  calibrated, and `paper-radar calibrate` says the same when fitting
  thresholds to Claude-judged labels. The Cochrane screening numbers
  (96.9% recall, 78% work saved) were measured with Jev and do not
  apply to Claude.
- GitHub Action (A7): new `action.yml` at the repo root — any repo with
  a `radar.toml` can run Paper Radar with
  `uses: Eliot5566/JEV-Paper-Radar@main` (pin a release tag once one is
  cut; `@v0.1.1` predates this file). Keys go in as secrets and are
  never printed.
- Screening story (A8): new `docs/screening.md` for systematic-review
  readers — how screening mode works, how to run and measure it, and
  the CLEF TAR 2019 benchmark against Cochrane reviewers' decisions.

## 0.1.1 — 2026-11-11

- Claude backend: stop sending `temperature` — `claude-haiku-5-5` rejects it
  with 400 "`temperature` is deprecated for this model" (verified against
  the live API 2026-11-11). Without this fix every Claude run failed.

## 0.1.0 — 2026-11-11

First packaged release (`pip install paper-radar`).

- Claude backend: `backend = "claude"` in `radar.toml` (or
  `paper-radar run --backend claude`) judges papers with Claude via the
  Anthropic Messages API, using `ANTHROPIC_API_KEY` and defaulting to
  `claude-haiku-5-5`. Stdlib only, like the Jev backends. Claude's
  probabilities are self-reported, not calibrated — run
  `paper-radar calibrate` on your own labels before trusting a run, and
  note that the Cochrane screening numbers in the README were measured
  with Jev and do not apply to Claude.
- PyPI publishing: a tag-triggered workflow (`.github/workflows/publish.yml`)
  publishes the sdist and wheel with PyPI Trusted Publishing (OIDC, no
  token stored in the repo).
