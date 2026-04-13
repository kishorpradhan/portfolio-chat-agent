from __future__ import annotations

import re
from typing import Any

from portfolio_chat_agent.compute.portfolio_api import fetch_portfolio_allocation


_TOP_N_PATTERN = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)


def _parse_top_n(question: str, default: int = 5) -> int:
    match = _TOP_N_PATTERN.search(question)
    if not match:
        return default
    try:
        value = int(match.group(1))
    except ValueError:
        return default
    return max(1, min(value, 50))


def compute_top_holdings(question: str) -> list[dict[str, Any]]:
    allocation = fetch_portfolio_allocation()
    rows = allocation.get("tickers", [])
    top_n = _parse_top_n(question)

    payload: list[dict[str, Any]] = []
    for row in rows:
        payload.append(
            {
                "ticker": row.get("ticker"),
                "marketValue": row.get("marketValue"),
                "weight": row.get("weight"),
            }
        )

    return payload[:top_n]
