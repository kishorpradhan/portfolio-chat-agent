import json

from portfolio_chat_agent import graph


def test_run_code_executes_with_portfolio_helpers(monkeypatch):
    sample = {
        "tickers": [
            {"ticker": "AAPL", "marketValue": 100.0, "weight": 0.4},
            {"ticker": "MSFT", "marketValue": 80.0, "weight": 0.32},
            {"ticker": "NVDA", "marketValue": 60.0, "weight": 0.24},
        ]
    }

    monkeypatch.setattr(
        "portfolio_chat_agent.graph.chat_graph.fetch_portfolio_allocation",
        lambda _token=None: sample,
    )

    code = """
data = get_portfolio_allocation()
result = data["tickers"][:2]
print(json.dumps(result))
"""
    output = graph.chat_graph._run_code(code, auth_token=None)
    parsed = json.loads(output)
    assert len(parsed) == 2
    assert parsed[0]["ticker"] == "AAPL"
