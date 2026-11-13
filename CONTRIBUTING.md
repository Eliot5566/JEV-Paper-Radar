# Contributing

Thanks for helping. The easiest and most useful contributions are small:

- **First-run feedback** via the [setup form](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=setup-help.yml). Report your version, backend, environment and redacted error. The [Claude guide](docs/claude-quickstart.md) and [繁體中文教學](docs/claude-quickstart.zh-TW.md) include an offline demo requiring no key. Never share credentials, full environment variables or private research.
- **Experience reports** in [Discussions](https://github.com/Eliot5566/JEV-Paper-Radar/discussions): describe the field and setup, what worked, and a concrete limitation. Distinguish personal labels from assistant-generated ones and threshold fitting from evaluation on a later batch. Maintainer examples are not independent adoption or endorsements.

- **A profile for your field** in `profiles/<field>.toml`. Keep interests to one idea each, phrase exclusions positively, and run `paper-radar check -c profiles/<field>.toml` so the linter is happy.
- **A new source** in `paper_radar/sources/`. Return a list of `Paper` objects with a stable, globally unique `id` (`<source>:<native id>`), and add a parser test with a small fixture.
- **A new notifier** in `paper_radar/notify.py`, switched on only by environment variables.

Ground rules:

1. Zero runtime dependencies. The standard library only, so the GitHub Action installs in seconds.
2. Keep the model's job small. Jev answers atomic questions; any logic, counting or date handling lives in Python.
3. Tests: `pip install -e ".[dev]" && pytest`. Network calls in tests go to fixtures or a local fake server.
4. The audit trail format in `data/` is a public contract. If you change it, keep reading old files.
