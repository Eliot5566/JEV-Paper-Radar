# Request usage and cost accounting

This describes Paper Radar 0.2.0 and later. Earlier releases do not include this audit.

## What is recorded

Each run or screening batch appends to `data/usage.jsonl`. The record contains one entry per judging attempt, the provider/model, input and output tokens, cache read/write tokens, the configured rates and their stated date. It contains no prompts, paper text, generated answers, API keys or raw error bodies.

A malformed answer that needs repair contributes both responses. A failed judgement still contributes its returned usage. A fatal error writes the usage audit before it propagates. A transport or HTTP failure without usage is recorded as unknown; the tool does not assume it was charged or free.

The scope is **judging requests only**. Optional TL;DR generation and any other services are not included. This is an audit of provider-reported usage, not a substitute for the provider's bill.

## Configure your rates explicitly

For Claude Haiku 5.5 prompts up to 100K tokens, the official page checked on 2026-11-13 lists $0.10 per million input tokens and $0.50 per million output tokens:

```toml
[jev]
backend = "claude"
model = "claude-haiku-5-5"
price_per_mtok = 0.10
output_price_per_mtok = 0.50
pricing_as_of = "2026-11-13"
```

Source: https://www.anthropic.com/claude/haiku

These are editable assumptions, not an automatic pricing feed. Other models, prompt-length tiers, providers, caching, batches and discounts can have different rates. Check your provider and configure the rates that apply to your requests. The tool does not automatically select a long-context tier.

If cached tokens are returned, configure `cache_read_price_per_mtok` and/or `cache_creation_price_per_mtok` using that provider's pricing. Do not set them to zero unless the applicable charge really is zero.

## Unknown is different from zero

`cost_usd` is null when a request's usage or a required rate is missing. `known_cost_usd` is only the subtotal of known components; it is not a total bill. A provider-reported request cost takes precedence over the configured-rate estimate. `cost_basis` records whether configured estimates were used.

The command output, day page, archive and directory show **cost unknown** when a total cannot be established. Historical decision-only estimates cannot recover missing output, repair or failed-request usage. Rebuilding old pages therefore does not relabel those amounts as full costs.

`data/runs.jsonl` records the batch's billing summary. Multiple runs on the same day count all their judging requests, even when a rejudge replaces the visible decisions. The request audit also survives fatal runs that do not produce a normal run record. Subsequent page rebuilds include those aborted attempts from `usage.jsonl`, without counting normal run summaries twice.

Per-paper `cost` in decision files is retained for compatibility and remains a legacy decision estimate. Use the request audit and run-level billing fields for accounting. `paper-radar check` and the pre-run estimate are explicitly input-only; they cannot know the future output and retry count.
