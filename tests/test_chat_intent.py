from fastapi.testclient import TestClient

from portfolio_chat_agent.app import app
from portfolio_chat_agent.graph.chat_graph import IntentResult


def test_non_finance_intent_returns_nudge(monkeypatch):
    def fake_intent(_question: str) -> IntentResult:
        return IntentResult(
            label="non_finance",
            confidence=0.2,
            rationale="The question is related to weather, which is not a finance topic.",
        )

    monkeypatch.setattr(
        "portfolio_chat_agent.graph.chat_graph.classify_intent_llm", fake_intent
    )

    client = TestClient(app)
    response = client.post("/chat/run", json={"question": "How is the weather in NYC"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["followup_needed"] is True
    assert payload["status"] == "completed"
    assert payload["intent"]["label"] == "non_finance"
    assert "What are my top 5 stocks?" in payload["response"]
