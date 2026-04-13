from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

from langfuse import Langfuse

from portfolio_chat_agent.config.settings import get_settings

_client: Optional[Langfuse] = None
_trace_ctx: ContextVar[Any] = ContextVar("langfuse_trace", default=None)


def get_langfuse_client() -> Optional[Langfuse]:
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    global _client
    if _client is None:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _client


def start_trace(
    *,
    name: str,
    input: dict[str, Any],
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    client = get_langfuse_client()
    if not client:
        return None
    trace = client.trace(
        name=name,
        input=input,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata,
    )
    _trace_ctx.set(trace)
    return trace


def get_trace() -> Any | None:
    return _trace_ctx.get()


def clear_trace() -> None:
    _trace_ctx.set(None)


def end_trace(trace: Any | None, *, output: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> None:
    if not trace:
        return
    if hasattr(trace, "update"):
        trace.update(output=output, metadata=metadata)


def start_span(
    *,
    name: str,
    input: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    trace = get_trace()
    if not trace:
        return None
    if hasattr(trace, "span"):
        return trace.span(name=name, input=input, metadata=metadata)
    if hasattr(trace, "event"):
        return trace.event(name=name, input=input, metadata=metadata)
    return None


def end_span(
    span: Any | None,
    *,
    output: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if not span:
        return
    payload: dict[str, Any] | None = output
    if error:
        payload = {"error": error, **(output or {})}
    if hasattr(span, "end"):
        span.end(output=payload, metadata=metadata)
        return
    if hasattr(span, "update"):
        span.update(output=payload, metadata=metadata)
