from __future__ import annotations

from typing import Any

import httpx

from portfolio_chat_agent.config.settings import get_settings


def _stub_results(query: str) -> list[dict[str, str]]:
    return [{"title": "search_stub", "url": "", "snippet": f"stub for: {query}"}]


def search_web(query: str) -> list[dict[str, str]]:
    settings = get_settings()
    provider = (settings.search_provider or "stub").lower()
    if provider == "stub":
        return _stub_results(query)

    if provider == "tavily":
        if not settings.search_api_key:
            return _stub_results(query)
        payload = {
            "api_key": settings.search_api_key,
            "query": query,
            "max_results": settings.search_top_k,
            "include_answer": False,
            "include_raw_content": False,
        }
        url = settings.search_api_url or "https://api.tavily.com/search"
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
            for item in results
        ]

    return _stub_results(query)
