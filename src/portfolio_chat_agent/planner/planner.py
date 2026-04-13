from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from portfolio_chat_agent.config.llm import get_llm
from portfolio_chat_agent.config.settings import get_settings
from portfolio_chat_agent.prompts.loader import render_prompt


class ApiCall(BaseModel):
    tool: str
    tickers: list[str] = Field(default_factory=list)
    date_range: dict[str, Any] | None = None
    query: str | None = None
    params: dict[str, Any] | None = None


class PlannerOutput(BaseModel):
    technical_question: str
    portfolio_endpoints: list[str] = Field(default_factory=list)
    api_calls: list[ApiCall] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    compute_mode: str = "none"




def _load_dataset_metadata() -> dict:
    metadata_path = Path(__file__).resolve().parents[1] / "config" / "file_metadata.yaml"
    if not metadata_path.exists():
        return {"datasets": {}}
    with metadata_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"datasets": {}}


def _render_planner_prompt(question: str) -> str:
    metadata = _load_dataset_metadata()
    dataset_metadata = json.dumps(metadata.get("datasets", {}), indent=2)
    api_contracts = _load_api_contracts()
    api_contracts_text = json.dumps(api_contracts, indent=2)
    return render_prompt(
        "planner_prompt.j2",
        user_question=question,
        dataset_metadata=dataset_metadata,
        api_contracts=api_contracts_text,
    )


def _load_api_contracts() -> dict:
    path = Path(__file__).resolve().parents[1] / "config" / "api_contracts.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def run_planner(question: str) -> PlannerOutput:
    prompt = _render_planner_prompt(question)
    settings = get_settings()
    llm = get_llm(model=settings.planner_model, provider_override=settings.planner_provider)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    try:
        payload = json.loads(content)
        return PlannerOutput.model_validate(payload)
    except Exception:
        return PlannerOutput(
            technical_question=question,
            portfolio_endpoints=[],
            api_calls=[],
            tickers=[],
            compute_mode="none",
        )
