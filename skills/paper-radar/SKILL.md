---
name: paper-radar
description: Set up and inspect Paper Radar, a Python paper-triage tool for arXiv and other feeds. Use for research alerts, radar.toml, Claude or Jev backend setup, usage auditing, and checking thresholds against user-labelled papers.
---

# Paper Radar

Read titles and abstracts against atomic research interests; publish a daily
page and RSS feed. Python 3.11+, MIT, no runtime dependencies. This skill guides
the existing CLI; it does not provide credentials or turn a Claude Code login
into API access.

## Start here

1. Read the [Claude quickstart](https://github.com/Eliot5566/JEV-Paper-Radar/blob/main/docs/claude-quickstart.md)
   ([繁體中文](https://github.com/Eliot5566/JEV-Paper-Radar/blob/main/docs/claude-quickstart.zh-TW.md)).
2. Install the published release: `python -m pip install "paper-radar==0.2.0"`.
   Check `paper-radar --version`.
3. Use `paper-radar demo --out paper-radar-demo` before credentials are needed.
   It uses fictional papers and keyword rules, not Claude or Jev; open
   `paper-radar-demo/site/index.html` to inspect the layout.
4. For Claude, copy the repository's `profiles/claude-starter.toml` into a new
   working directory as `radar.toml`. It caps a run at 20 papers and includes
   explicit, dated input/output rate assumptions. Check the applicable rates.
5. Run `paper-radar check -c radar.toml --show-questions` (offline, no key).

Write one idea per interest. Phrase exclusions positively, describing what the
paper is. Do not ask the model to perform date filtering or counting.

## Credentials and first live run

- Claude requires `ANTHROPIC_API_KEY` and `[jev] backend = "claude"`.
  API usage is billed separately from Claude chat subscriptions. The starter
  model is `claude-haiku-5-5`; verify availability for the user's account.
- Jev uses `TYPESAFE_API_KEY`, or `OPENROUTER_API_KEY` with the corresponding
  backend and model. Do not silently switch providers.
- Let the user enter credentials privately via environment variables, a
  git-ignored `.env`, or GitHub Actions secrets. Never request a key in chat,
  print it, inspect unrelated credential files, or commit it.
- Before a live run, explain the selected model, paper limit and pricing
  assumptions. Follow the user's authorization and budget. A paper limit is
  not a dollar budget; retries and repeat runs can add charges.

```sh
paper-radar run -c radar.toml --limit 20 --dry-run
paper-radar run -c radar.toml --limit 20 --no-notify
```

Dry run fetches listings without judging, but constructing a Claude backend
still requires a key. Its estimate is input-only. The second command makes
billed calls. Outputs are relative to the configuration's directory.
Use a new folder for demos so existing demo files are not overwritten.

## Usage and interpretation

Inspect `data/usage.jsonl` for returned input/output/cache usage, repairs and
failed attempts. Missing usage or required prices mean **cost unknown**, not
zero. Optional TL;DR requests are outside the audit scope. See
[accounting limits](https://github.com/Eliot5566/JEV-Paper-Radar/blob/main/docs/usage-and-cost.md).

Claude returns self-reported JSON scores, not calibrated probabilities. The
49-paper first look used assistant-made labels; it is not user validation.
The README's Cochrane screening results used Jev, not Claude. Do not transfer
these results to another model, field or task.

Label stored papers with `paper-radar label <paper-id> yes|no -c radar.toml`,
including unselected papers and near misses. Fit thresholds using
`paper-radar calibrate -c radar.toml --precision 0.9 --recall 0.9`.
Assistant-made labels must be identified as such. Fit on one batch and evaluate
on a separately labelled later batch; fitting scores are not held-out accuracy.
Report insufficient data or unmet targets plainly.

## GitHub and sharing

The [Claude example](https://github.com/Eliot5566/paper-radar-claude-example)
contains a complete `v0.2.0` workflow: repository secret, persisted audit trail
and Pages deployment. The composite action alone does not publish Pages.
The example and upstream weekday schedule are 06:00 UTC; scheduled jobs can
be delayed. Do not claim the demo or public Jev feeds are Claude outputs.

Review workflow permissions and publication scope with the user's instructions
before enabling automation. A public repository may publish its interests and
decision data. The API provider receives paper titles and abstracts.

For setup errors use the [public help form](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=setup-help.yml).
Share only redacted errors and public configuration. Missing keys, rate limits,
quiet source days and API/model availability are separate failure causes;
an offline demo verifies neither credentials nor API access.

## Installation

Copy this directory to `.claude/skills/paper-radar/` in the user's project, or
`~/.claude/skills/paper-radar/` for personal use, after reviewing any existing
destination. Invoke `/paper-radar` or ask Claude Code to help set up a radar.
See [official skills docs](https://code.claude.com/docs/en/skills).
