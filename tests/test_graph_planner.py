import json

from portfolio_chat_agent.graph import chat_graph
from portfolio_chat_agent.planner.planner import PlannerOutput, ApiCall


class FakeLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        class Response:
            def __init__(self, content: str):
                self.content = content

        return Response(self._content)


def test_plan_node_uses_planner_compute_mode(monkeypatch):
    plan = PlannerOutput(
        technical_question="Test",
        portfolio_endpoints=[],
        api_calls=[],
        tickers=[],
        compute_mode="sandbox",
    )
    monkeypatch.setattr("portfolio_chat_agent.graph.chat_graph.run_planner", lambda _q: plan)

    state = {"question": "test question"}
    result = chat_graph._plan_node(state)
    assert result["compute_mode"] == "sandbox"


def test_decompose_node_uses_llm(monkeypatch):
    payload = {
        "sub_questions": [
            {
                "id": "q1",
                "question": "Fetch portfolio returns",
                "depends_on": [],
                "data_source": "portfolio_api",
            },
            {
                "id": "q2",
                "question": "Fetch S&P 500 returns",
                "depends_on": [],
                "data_source": "market_data",
            },
            {
                "id": "q3",
                "question": "Compare q1 and q2",
                "depends_on": ["q1", "q2"],
                "data_source": "derived",
            },
        ],
        "join_strategy": "compare",
    }

    monkeypatch.setattr(
        "portfolio_chat_agent.graph.chat_graph.get_llm",
        lambda *args, **kwargs: FakeLLM(json.dumps(payload)),
    )

    state = {"question": "Compare my portfolio vs S&P 500"}
    result = chat_graph._decompose_node(state)
    decomposed = result.get("decomposed_plan")
    assert decomposed is not None
    assert len(decomposed.sub_questions) == 3
    assert decomposed.join_strategy == "compare"


def test_codegen_prompt_receives_plan_fields(monkeypatch):
    captured = {}

    def fake_render_prompt(_name: str, **kwargs):
        captured.update(kwargs)
        return "prompt"

    plan = PlannerOutput(
        technical_question="Compute top 5 holdings",
        portfolio_endpoints=["portfolio_allocation"],
        api_calls=[ApiCall(tool="search_tool", query="latest news on AAPL")],
        tickers=["AAPL"],
        compute_mode="local",
    )

    monkeypatch.setattr("portfolio_chat_agent.graph.chat_graph.render_prompt", fake_render_prompt)
    monkeypatch.setattr(
        "portfolio_chat_agent.graph.chat_graph.get_llm",
        lambda *args, **kwargs: FakeLLM("print(json.dumps({}))"),
    )

    state = {
        "question": "Top 5 holdings",
        "plan": plan,
        "execution_error": "",
        "combined_question": "Top 5 holdings",
    }
    chat_graph._codegen_placeholder_node(state)

    assert captured["technical_question"] == "Compute top 5 holdings"
    assert captured["tickers"] == ["AAPL"]
    assert captured["required_endpoints"] == ["portfolio_allocation"]
    assert captured["api_call_specs"] == [plan.api_calls[0].model_dump()]


def test_error_history_accumulates_on_execute_failure(monkeypatch):
    def fake_fetch(_token=None):
        return {"tickers": []}

    monkeypatch.setattr(
        "portfolio_chat_agent.graph.chat_graph.fetch_portfolio_allocation",
        fake_fetch,
    )

    state = {
        "code": "print('not json')",
        "attempts": 0,
    }
    result = chat_graph._execute_placeholder_node(state)
    assert "execution_error" in result
    assert result.get("error_history")
