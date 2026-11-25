# Changelog

## Unreleased

- Screening: `paper-radar screen --progress` for reading in ranked order. Label as you read; it lists the next records and says when a dry run of max(100, 3% of the ranked records) irrelevant records makes it safe to stop. Records without an abstract are listed apart and never counted by the rule. On the twelve CLEF TAR reviews, with the rule chosen on the other eleven each time, Jev found 98.0% of eligible studies and saved 69% of the reading, against 92.4% / 46% for a fixed threshold.
- Benchmark: `stopping.py` (stopping rules vs a fixed threshold, chosen leaving one review out) and `ensemble.py` (average several models' dumps). Jev, Claude Haiku 5.5 and both together compared on the same 27,889 records, and Gemini Decision 1 on the eight development reviews it finished, in `results.stopping.md`. Reports now print the exact command that reproduces them, backend and model included.
- New backend: Gemini Decision 1 (`backend = "gemini"`, `GEMINI_API_KEY`), a decision model with the same noul / choice / score questions as Jev. From PR #29. Its usage is now recorded before the reply is validated, so a malformed but billed reply still counts in `usage.jsonl`.
- Claude backend:
  - Structured outputs: the reply is constrained to a JSON schema built from the questions (choices as `enum`). The 0..1 and score ranges are still checked, and the one repair attempt stays for answers outside them.
  - `output_config.effort` defaults to `low` (`jev.effort`; `""` sends none). Haiku 5.5 otherwise runs at `medium` and spends output tokens thinking. `max_tokens` is 2048.
  - Prompt caching: the instructions and questions are a cached system prefix (sorted JSON, so the bytes are stable) and the paper is the whole user turn. Configure `cache_read_price_per_mtok` and `cache_creation_price_per_mtok`, or a cached run shows cost unknown.
  - `jev.batch = true` judges a run through the Message Batches API at half price, with per-paper fallback to ordinary calls for malformed, errored or expired results and a `jev.batch_timeout_minutes` cancel. Batch usage records carry `"batch": true` and cost estimates apply the 50% discount.
  - A refusal (`stop_reason: "refusal"`) is reported as such and not repaired.
- Benchmark results with thresholds fixed in advance (`results.loto.*.md`, 2026-11-25, `jev-1.13.0`): fitted on the 8 development reviews and applied to the 4 held-out ones, 99.2% recall (95% CI 95.7–99.9%) and 44.0% pooled WSS, against 96.9% and 77.8% when tuned per review. `run.py` now retries PubMed efetch on truncated or 429/5xx responses.
- Benchmark: `run.py --backend claude|gemini` (and `--batch` for Claude) scores the CLEF TAR records with another model into its own results file, with cost from every request's usage. Dumps gain a `triggered` column. New `loto.py` reports leave-one-topic-out (or dev-to-holdout) thresholds, a Wilson interval for recall, and a reliability table, from dumps only.

## 0.2.0 — 2026-11-13

- Reject out-of-range, non-finite and boolean numeric answers before ranking or screening.
- Audit judging input/output/cache usage, including repair responses, failed judgements and aborted batches, in `data/usage.jsonl`.
- Configure output/cache rates and a pricing date; show unknown totals when usage or a required rate is missing. Day, archive and directory costs use request-level accounting.
- Keep historical and per-decision estimates distinct from complete judging costs; optional TL;DR generation is outside the audit.
- Tests also clear `ANTHROPIC_API_KEY` from the inherited environment.
- Keep CLI logging usable when a Windows pipe uses a legacy encoding: unrepresentable characters are escaped instead of aborting the command.
- Compatibility: `RunResult.cost`, `ScreenResult.cost` and run-level `cost_usd` can now be null when the total is unknown. Downstream consumers must handle that value rather than treating it as zero.


## 0.1.5 — 2026-11-12

- Claude backend: a malformed answer no longer fails the paper outright.
  The parser now tolerates prose around the JSON object and probabilities
  written as strings ("0.85"); a still-malformed answer gets one repair
  attempt, with the model's own reply echoed back and what was wrong with
  it. Verified against the live API: a bad reply `{"ai-agents": "high"}`
  was repaired to `{"ai-agents": 0.95}` in one turn.
- Quarantine: a paper that fails three days in a row is skipped for 30
  days (`data/quarantine.jsonl`) instead of being retried — and billed —
  every morning; it gets one fresh attempt when the window expires, and
  `run --rejudge` gives it a fresh chance immediately. This stops the
  13 papers in the Claude example repo that failed every day on Claude
  response-format errors from burning tokens on retries that never resolve.

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
