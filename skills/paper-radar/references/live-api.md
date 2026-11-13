# Live feeds and scheduled API judging

The chat-native supplied-abstract mode needs no separate API key. To fetch
external listings and judge through an API, use the CLI in a local environment
or GitHub Actions. Claude chat may restrict network access and does not provide
a persistent daily scheduler or a private credential-entry mechanism for this tool.
Never ask the user to paste a key into chat or upload it as a conversation file.

Python 3.11+ is required. The complete skill bundle includes the CLI in vendor/:

```sh
python scripts/run.py check -c references/claude-starter.toml --show-questions
```

For a source-folder Claude Code installation without vendor/, install the
published paper-radar==0.2.0 in the project's virtual environment and use the
paper-radar CLI instead. Do not install globally without the user's instruction.
Copy the starter configuration into the user's working directory as radar.toml
before a live run, so generated files are not written into the installed skill.

Claude uses ANTHROPIC_API_KEY with backend="claude". Jev uses TYPESAFE_API_KEY,
or OPENROUTER_API_KEY with the corresponding backend/model. Let the user configure
credentials privately via environment variables, a git-ignored .env or Actions
secrets. Do not inspect unrelated credentials, print keys, or silently switch
providers. A Claude Code login is not an API key; API usage is separately billed.

The starter configuration caps a run at 20 papers, two concurrent requests and
30 requests/minute. Its dated input/output prices must be verified for the model
and prompt-length tier. A paper cap is not a dollar budget; retries and repeated
runs can add charges. Follow the user's authorization and budget before running.

```sh
paper-radar check -c radar.toml --show-questions
paper-radar run -c radar.toml --limit 20 --dry-run
paper-radar run -c radar.toml --limit 20 --no-notify
```

Dry-run fetches listings without model calls but the selected Claude backend
still needs a configured key. Estimates cover input only. The final command
makes billed API calls. The regular CLI writes provider-returned input/output/
cache usage, repairs and failed attempts to data/usage.jsonl. Missing usage or
required rates mean cost unknown. Optional TL;DR calls are outside that audit.

Full guide: https://github.com/Eliot5566/JEV-Paper-Radar/blob/main/docs/claude-quickstart.md
Accounting: https://github.com/Eliot5566/JEV-Paper-Radar/blob/main/docs/usage-and-cost.md
Complete scheduled Pages workflow: https://github.com/Eliot5566/paper-radar-claude-example

Weekday scheduling is 06:00 UTC; GitHub may delay jobs. A composite action alone
does not deploy Pages. Review publication scope according to the user's request:
public repositories expose their configuration and committed decision data.
