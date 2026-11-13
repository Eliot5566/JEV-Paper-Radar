"""Provider usage only: no prompts, answers, credentials, or assumed invoices."""

from __future__ import annotations

from typing import Any


TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def response_usage(data: Any) -> dict[str, Any]:
    """Keep a small, JSON-safe record even when the model answer is invalid."""
    data = data if isinstance(data, dict) else {}
    raw = data.get("usage") or {}
    raw = raw if isinstance(raw, dict) else {}
    record: dict[str, Any] = {"model": str(data.get("model") or "")}
    for field in TOKEN_FIELDS:
        value = raw.get(field, 0 if field.startswith("cache_") else None)
        record[field] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    cost = raw.get("cost")
    record["reported_cost_usd"] = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) and 0 <= cost < float("inf") else None
    return record


def summarize_usage(records: list[dict[str, Any]], settings: Any) -> dict[str, Any]:
    """Unknown usage or an unset nonzero-token rate makes the total unknown.

    A configured-rate estimate is never described as the provider's invoice.
    TypeSafe and the offline mock have no generated-output charge; other
    providers require an explicit output rate or a reported request cost.
    """
    rates = {
        "input_tokens": settings.price_per_mtok,
        "output_tokens": settings.output_price_per_mtok,
        "cache_read_input_tokens": settings.cache_read_price_per_mtok,
        "cache_creation_input_tokens": settings.cache_creation_price_per_mtok,
    }
    if rates["output_tokens"] is None and settings.backend in ("typesafe", "mock"):
        rates["output_tokens"] = 0.0
    totals = {key: sum(r.get(key) or 0 for r in records) for key in TOKEN_FIELDS}
    known_cost = 0.0
    complete = True
    estimated = False
    for record in records:
        reported = record.get("reported_cost_usd")
        if reported is not None:
            known_cost += reported
            continue
        estimated = True
        for field, rate in rates.items():
            tokens = record.get(field)
            if (tokens is None and rate != 0) or (tokens and rate is None):
                complete = False
            elif tokens:
                known_cost += tokens * rate / 1_000_000
    return {
        "scope": "judging_requests_only",
        "requests": len(records),
        **totals,
        "usage_complete": all(r.get(k) is not None for r in records for k in TOKEN_FIELDS),
        "cost_usd": round(known_cost, 8) if complete else None,
        "known_cost_usd": round(known_cost, 8),
        "cost_basis": "configured_rate_estimate" if estimated else "provider_reported",
        "rates_per_mtok": rates,
        "pricing_as_of": settings.pricing_as_of,
        "responses": records,
    }
