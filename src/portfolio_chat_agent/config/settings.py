from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    codegen_provider: str | None
    intent_provider: str | None
    planner_provider: str | None
    synth_provider: str | None
    openai_model: str
    intent_model: str
    planner_model: str
    codegen_model: str
    synth_model: str
    non_finance_nudge: str
    portfolio_api_url: str | None
    portfolio_api_token: str | None
    checkpointer_dsn: str | None
    search_provider: str
    search_api_key: str | None
    search_api_url: str | None
    search_top_k: int
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str | None
    data_dir: Path


_settings: Settings | None = None


def get_settings() -> Settings:
    def _optional(value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    global _settings
    if _settings is None:
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        codegen_provider = _optional(os.getenv("CODEGEN_PROVIDER"))
        intent_provider = _optional(os.getenv("INTENT_PROVIDER"))
        planner_provider = _optional(os.getenv("PLANNER_PROVIDER"))
        synth_provider = _optional(os.getenv("SYNTH_PROVIDER"))
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        intent_model = os.getenv("INTENT_MODEL", openai_model)
        planner_model = os.getenv("PLANNER_MODEL", openai_model)
        codegen_model = os.getenv("CODEGEN_MODEL", openai_model)
        synth_model = os.getenv("SYNTH_MODEL", openai_model)
        non_finance_nudge = os.getenv(
            "NON_FINANCE_NUDGE",
            "What are my top 5 stocks?",
        )
        portfolio_api_url = os.getenv("PORTFOLIO_API_URL")
        portfolio_api_token = os.getenv("PORTFOLIO_API_TOKEN")
        checkpointer_dsn = os.getenv("CHECKPOINTER_DB_DSN")
        search_provider = os.getenv("SEARCH_PROVIDER", "stub")
        search_api_key = _optional(os.getenv("SEARCH_API_KEY"))
        search_api_url = _optional(os.getenv("SEARCH_API_URL"))
        search_top_k = int(os.getenv("SEARCH_TOP_K", "5"))
        langfuse_public_key = _optional(os.getenv("LANGFUSE_PUBLIC_KEY"))
        langfuse_secret_key = _optional(os.getenv("LANGFUSE_SECRET_KEY"))
        langfuse_host = _optional(os.getenv("LANGFUSE_HOST"))
        data_dir = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[3] / "data"))
        _settings = Settings(
            llm_provider=llm_provider,
            codegen_provider=codegen_provider,
            intent_provider=intent_provider,
            planner_provider=planner_provider,
            synth_provider=synth_provider,
            openai_model=openai_model,
            intent_model=intent_model,
            planner_model=planner_model,
            codegen_model=codegen_model,
            synth_model=synth_model,
            non_finance_nudge=non_finance_nudge,
            portfolio_api_url=portfolio_api_url,
            portfolio_api_token=portfolio_api_token,
            checkpointer_dsn=checkpointer_dsn,
            search_provider=search_provider,
            search_api_key=search_api_key,
            search_api_url=search_api_url,
            search_top_k=search_top_k,
            langfuse_public_key=langfuse_public_key,
            langfuse_secret_key=langfuse_secret_key,
            langfuse_host=langfuse_host,
            data_dir=data_dir,
        )
    return _settings
