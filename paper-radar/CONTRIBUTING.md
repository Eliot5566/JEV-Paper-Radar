# Contributing

Thanks for helping. The easiest and most useful contributions are small:

- **A profile for your field** in `profiles/<field>.toml`. Keep interests to one idea each, phrase exclusions positively, and run `paper-radar check -c profiles/<field>.toml` so the linter is happy.
- **A new source** in `paper_radar/sources/`. Return a list of `Paper` objects with a stable, globally unique `id` (`<source>:<native id>`), and add a parser test with a small fixture.
- **A new notifier** in `paper_radar/notify.py`, switched on only by environment variables.

Ground rules:

1. Zero runtime dependencies. The standard library only, so the GitHub Action installs in seconds.
2. Keep the model's job small. Jev answers atomic questions; any logic, counting or date handling lives in Python.
3. Tests: `pip install -e ".[dev]" && pytest`. Network calls in tests go to fixtures or a local fake server.
4. The audit trail format in `data/` is a public contract. If you change it, keep reading old files.
