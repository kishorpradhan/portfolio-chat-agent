from __future__ import annotations

from typing import Any

import httpx

from portfolio_chat_agent.config.settings import get_settings


class PortfolioApiContext:
    def __init__(
        self,
        token: str | None = None,
        demo_session_id: str | None = None,
        profile_id: str | None = None,
    ):
        self.token = token
        self.demo_session_id = demo_session_id
        self.profile_id = profile_id


def _build_headers(token: str | None) -> dict[str, str]:
    settings = get_settings()
    token = token or settings.portfolio_api_token
    if token and token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _build_context_headers(context: PortfolioApiContext | None) -> dict[str, str]:
    headers = _build_headers(context.token if context else None)
    if context and context.demo_session_id:
        headers.pop("Authorization", None)
        headers["X-Moniq-Demo-Session"] = context.demo_session_id
    if context and context.profile_id:
        headers["X-Moniq-Profile-Id"] = context.profile_id
    return headers


def _params(context: PortfolioApiContext | None) -> dict[str, str]:
    if context and context.profile_id:
        return {"profile_id": context.profile_id}
    return {}


def _base_url() -> str:
    settings = get_settings()
    if not settings.portfolio_api_url:
        raise RuntimeError("PORTFOLIO_API_URL is not configured.")
    return settings.portfolio_api_url.rstrip("/")


def fetch_portfolio_allocation(
    token: str | None = None, context: PortfolioApiContext | None = None
) -> dict[str, Any]:
    url = f"{_base_url()}/portfolio/allocation"
    context = context or PortfolioApiContext(token=token)
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=_build_context_headers(context), params=_params(context))
    response.raise_for_status()
    return response.json()


def fetch_portfolio_positions(
    token: str | None = None, context: PortfolioApiContext | None = None
) -> dict[str, Any]:
    url = f"{_base_url()}/portfolio/positions"
    context = context or PortfolioApiContext(token=token)
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=_build_context_headers(context), params=_params(context))
    response.raise_for_status()
    return response.json()
