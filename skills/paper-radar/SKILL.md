---
name: paper-radar
description: Runs Paper Radar, a daily arXiv/bioRxiv triage tool that judges new papers against plain-English interests. Use to track papers, screen for a systematic review, or calibrate Jev/Claude thresholds.
---

# Paper Radar

Paper Radar reads every new paper on arXiv and bioRxiv each morning and
surfaces the few worth reading. It asks a judgement model (Jev or Claude)
one yes/no question per interest and returns a probability. No server is
needed: it runs locally or as a GitHub Action and publishes a page plus an
RSS feed.

## When to use this skill

- The user wants to follow new papers in a field ("track agent evaluation
  papers", "watch arXiv cs.CL daily")
- The user wants systematic-review screening (title/abstract screening
  against inclusion criteria)
- The user wants to calibrate thresholds, label papers, or check whether
  Jev/Claude probabilities can be trusted
- The user asks about `paper-radar`, `radar.toml`, or the JEV-Paper-Radar repo

## Setup

1. Install: `pip install paper-radar` (Python 3.11+, zero runtime
   dependencies).
2. Check the install: `paper-radar --version` (0.1.4 or later).
3. Create `radar.toml` in a working directory (minimal example below) and
   validate it: `paper-radar check -c radar.toml`
4. Add an API key as an environment variable:
   - Jev (default): `TYPESAFE_API_KEY` from console.typesafe.ai, or
     `OPENROUTER_API_KEY` with `backend = "openrouter"` (no waitlist)
   - Claude: `ANTHROPIC_API_KEY`, `backend = "claude"` (default model
     `claude-haiku-5-5`)
   Never print a key, never write one into a file that gets committed, and
   never paste a key into chat. Keys go in `.env` (git-ignored) or GitHub
   Actions secrets.

Minimal `radar.toml`:

```toml
[radar]
title = "My Paper Radar"

[jev]
backend = "claude"   # or "typesafe" (default) / "openrouter" / "mock"
# model = "claude-haiku-5-5"  # the default; set explicitly to pin a version

[[sources]]
type = "arxiv"
categories = ["cs.AI", "cs.CL", "cs.LG"]

[[interests]]
id = "agent_eval"
label = "Agent evaluation"
text = "Benchmarks or methods for evaluating LLM agents on multi-step tool-use tasks"
```

Interest-writing rules (the model reads words literally): one idea per
interest; put negatives in `[[exclude]]` phrased positively; describe the
paper, do not ask for counts or dates. Run
`paper-radar check --show-questions` to see the exact questions that will
be asked.

## Running it

- Cheap first test (no model call, cost estimate only):
  `paper-radar run --dry-run -c radar.toml`
- First real run, 50 papers: `paper-radar run --limit 50 -c radar.toml`
- Full daily run: `paper-radar run -c radar.toml` — writes the page to
  `site/` and the audit trail to `data/`
- Re-judge after changing criteria: add `--rejudge`
- Offline demo (no key): `paper-radar demo` — writes
  `./paper-radar-demo/site/index.html`

## Calibration — read this before trusting any probability

- Jev returns a calibrated `noul`; its default thresholds are must_read
  0.80 / maybe 0.50.
- Claude returns a self-reported number written in JSON — NOT calibrated.
  A first-look calibration (49 papers, one day, 2026-11-11) suggested
  must_read 0.65 / maybe 0.35, Brier 0.040, ECE 0.081 (above the 0.05 bar,
  so not "calibrated"). Never present Claude as calibrated.
- The Cochrane screening numbers (96.9% recall, 78% work saved on 19,447
  records) were measured with Jev and do NOT apply to Claude.
- To fit thresholds to the user's own judgement:
  `paper-radar label <arxiv-id> yes|no` on about 30 papers (include
  near-misses), then `paper-radar calibrate --precision 0.9 --recall 0.9`,
  then write the suggested thresholds into `radar.toml`. Labels made by an
  assistant are not the user's labels — say so if that is the case.

## Systematic-review screening

- `paper-radar screen` runs title/abstract screening against inclusion
  criteria (see `profiles/systematic-review.toml` and
  `docs/screening.md` in the repo).
- Report the benchmark honestly: 4 held-out Cochrane reviews, 19,447
  records, 127 eligible, 96.9% recall, 78.0% pooled work saved, $0.60,
  jev-1.13.0, 2026-09-24 — out of 12 reviews in the benchmark set (dev 8:
  8,442 records, 279 eligible). Never write "12 Cochrane reviews, 19,447
  records".

## GitHub Action (no fork needed)

Any repo with a `radar.toml` can run it as one step:

```yaml
- uses: Eliot5566/JEV-Paper-Radar@v0.1.4
  with:
    config: radar.toml
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

Pin to a release tag. Keys are passed as secrets and are never printed in
the log. A one-minute example lives at
github.com/Eliot5566/paper-radar-claude-example.

## Troubleshooting

- `temperature is deprecated for this model` (Claude Haiku 5.5): the
  request must omit `temperature`. If this comes from the installed
  package, upgrade: `pip install -U paper-radar` (fixed in 0.1.1).
- Claude HTTP 401 `invalid x-api-key`: the key never reached the API. In
  GitHub Actions, check the workflow passes the secret reference
  `${{ secrets.ANTHROPIC_API_KEY }}`, not a literal value — a literal
  `<redacted>` in the workflow file is a real bug, not display masking.
- Empty or stale feed: `paper-radar check` validates the config; arXiv RSS
  can be quiet on weekends and holidays.

## Repo and docs

- Repo: https://github.com/Eliot5566/JEV-Paper-Radar (MIT, Python 3.11+,
  stdlib only — do not add dependencies)
- Full docs: README.md, README.zh-TW.md, docs/claude-calibration.md,
  docs/screening.md
- Issues: one profile field per `good first issue`; a new profile should
  pass `paper-radar check` before it is proposed.

## Installing this skill

Copy this folder to `~/.claude/skills/paper-radar/` (personal, Claude Code)
or `.claude/skills/paper-radar/` (project), or install it from the repo:
`git clone https://github.com/Eliot5566/JEV-Paper-Radar` and copy
`skills/paper-radar/` to one of those locations. Invoke with
`/paper-radar` or let Claude pick it up when the request matches the
description above.
