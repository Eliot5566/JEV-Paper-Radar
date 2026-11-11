# Changelog

## Unreleased

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
