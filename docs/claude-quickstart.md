# Paper Radar for Claude users

[繁體中文](claude-quickstart.zh-TW.md) · [Project](../README.md) · [Usage and cost](usage-and-cost.md)

Turn plain-English research interests into a daily paper page and RSS feed.
Paper Radar sends titles and abstracts to a judging backend, then ranks the
results in Python. It does not read full papers or replace a literature review.
The code is MIT licensed, Python 3.11+, with no runtime dependencies.

## Choose a starting point

| Goal | Start here | What is needed |
|---|---|---|
| See the output | Offline demo below | Python; no API key |
| Read an existing feed | [Public radars](https://eliot5566.github.io/JEV-Paper-Radar/public/) | Browser or RSS reader; these feeds use Jev |
| Run Claude on personal interests | Small local run below | Anthropic API access, billed separately |
| Publish automatically | [Claude example repository](https://github.com/Eliot5566/paper-radar-claude-example) | GitHub repository, API secret and Pages |
| Ask Claude Code to help | Optional skill below | Claude Code plus the same API requirements for live judging |

A Claude chat subscription and the Anthropic API are separate products. Paper
Radar uses `ANTHROPIC_API_KEY`; it does not consume a Claude Code login as an API
key. See [Anthropic's plan explanation](https://support.claude.com/en/articles/8325606-what-is-the-pro-plan).

## 1. Try the output without an account or key

```sh
python -m pip install "paper-radar==0.2.0"
paper-radar --version
paper-radar demo --out paper-radar-demo
```

Open `paper-radar-demo/site/index.html` in a browser. This demo uses fictional
papers and a keyword heuristic. It verifies installation and shows the layout;
it does not demonstrate Claude's accuracy or API connectivity.

## 2. Validate a small Claude configuration

Download [`profiles/claude-starter.toml`](../profiles/claude-starter.toml) and save
it as `radar.toml` in a new working directory. Change the interest statement to
one concrete topic. Then run:

```sh
paper-radar check -c radar.toml --show-questions
```

This command needs no key or network. The starter profile has a 20-paper cap,
two concurrent requests and a conservative request rate. Its thresholds are
display bands, not measured precision or recall guarantees.

The configuration contains dated input/output price assumptions. Verify your
model's current rates and prompt-length tier before running. The paper cap
limits papers per run; it is not a dollar budget, and retries or repeated runs
can add charges. A pre-run estimate covers input only.

## 3. Run on real papers

Set `ANTHROPIC_API_KEY` privately in your shell or a local `.env` beside
`radar.toml`. If using Git, add `.env` to `.gitignore` before creating that file.
Do not paste the key into Claude chat, issue reports or configuration files.

```sh
paper-radar run -c radar.toml --limit 20 --dry-run
paper-radar run -c radar.toml --limit 20 --no-notify
```

The first command fetches source listings and estimates input usage without a
judging call; the Claude backend still requires a configured key. The second
command makes billed API requests. Open `site/index.html`; use `site/feed.xml`
after publishing to a stable URL. Relative output paths are resolved beside
the configuration file. Quiet source days can yield no new papers.

Inspect `data/usage.jsonl` and `data/runs.jsonl` after the run. Version 0.2.0
records returned input/output/cache usage, including repair and failed attempts.
Missing usage or rates mean **cost unknown**. These records are not a provider
invoice, and optional TL;DR calls are outside their scope. Details:
[usage and cost accounting](usage-and-cost.md).

## 4. Check whether the ranking helps

Claude's JSON scores are self-reported, not calibrated probabilities. Inspect
both selected papers and near misses, label your own examples, and fit thresholds:

```sh
paper-radar label arxiv:2609.01234 yes -c radar.toml
paper-radar label arxiv:2609.04321 no -c radar.toml
paper-radar calibrate -c radar.toml --precision 0.9 --recall 0.9
```

Replace the example IDs with papers actually stored by your run. Include
unselected papers so missed relevant items can be found. Threshold fitting and
evaluation on the same labels are not independent validation: check the result
on a later, separately labelled batch. If too few labels support a target, collect
more rather than treating the target as achieved.

The [49-paper first look](claude-calibration.md) uses assistant-made labels, not
the maintainer's judgements. Its thresholds do not establish accuracy for a new
field. The Cochrane benchmark in the main README uses Jev and does not apply to
Claude.

## Optional: use the Claude Code skill

Review [`skills/paper-radar/SKILL.md`](../skills/paper-radar/SKILL.md), clone this
repository, then copy that directory into `.claude/skills/paper-radar/` in the
project where it will be used. For personal installation the destination is
`~/.claude/skills/paper-radar/`. See the official [skills documentation](https://code.claude.com/docs/en/skills).

For example, from the cloned repository on macOS/Linux:

```sh
mkdir -p .claude/skills
cp -R skills/paper-radar .claude/skills/paper-radar
```

Or in PowerShell:

```powershell
New-Item -ItemType Directory -Force .claude/skills
Copy-Item -Recurse skills/paper-radar .claude/skills/paper-radar
```

If the destination already exists, review it before copying to avoid overwriting
a custom skill. Start Claude Code in that project and try:

> /paper-radar Help me configure an agent-evaluation radar. First validate the
> config and run the offline demo. Show the request limit and estimated usage
> before a live API run. Keep credentials out of chat and tracked files.

The skill is an optional setup guide; installing it does not add an API key,
enable a GitHub schedule or publish anything automatically.

## Publish or share feedback

Use the [Claude example](https://github.com/Eliot5566/paper-radar-claude-example)
for a complete Pages workflow pinned to `v0.2.0`. Enable workflows in a new fork,
add the repository secret, enable Pages, and use a limit of `20` for the first
manual run. The example runs at 06:00 UTC on weekdays; GitHub schedules can be
delayed and source feeds have their own update schedules.

[Ask for setup help](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=setup-help.yml)
or [share an experience](https://github.com/Eliot5566/JEV-Paper-Radar/discussions).
Useful feedback includes the research field, package version, backend/model,
first-run outcome and a redacted error if needed. Share a small configuration
only if its contents can be public. Do not include API keys, full environment
variables, private abstracts or unpublished research.
