from __future__ import annotations

from typing import Any

import httpx

from portfolio_chat_agent.config.settings import get_settings


def _build_headers(token: str | None) -> dict[str, str]:
    settings = get_settings()
    token = token or settings.portfolio_api_token
    if token and token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _base_url() -> str:
    settings = get_settings()
    if not settings.portfolio_api_url:
        raise RuntimeError("PORTFOLIO_API_URL is not configured.")
    return settings.portfolio_api_url.rstrip("/")


def fetch_portfolio_allocation(token: str | None = None) -> dict[str, Any]:
    url = f"{_base_url()}/portfolio/allocation"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=_build_headers(token))
    response.raise_for_status()
    return response.json()


def fetch_portfolio_positions(token: str | None = None) -> dict[str, Any]:
    url = f"{_base_url()}/portfolio/positions"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=_build_headers(token))
    response.raise_for_status()
    return response.json()
