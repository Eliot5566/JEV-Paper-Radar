# Changelog

## 0.1.1 — Unreleased

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
