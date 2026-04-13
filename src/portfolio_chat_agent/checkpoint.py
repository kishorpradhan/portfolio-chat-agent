from __future__ import annotations

from typing import Optional

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from portfolio_chat_agent.config.settings import get_settings

_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> Optional[PostgresSaver]:
    settings = get_settings()
    dsn = settings.checkpointer_dsn
    if not dsn:
        return None
    global _checkpointer
    if _checkpointer is None:
        conn = psycopg.connect(dsn, autocommit=True)
        saver = PostgresSaver(conn)
        saver.setup()
        _checkpointer = saver
    return _checkpointer
