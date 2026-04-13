from __future__ import annotations

import json
from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.constants import Send
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from portfolio_chat_agent.config.llm import get_llm
from portfolio_chat_agent.config.settings import get_settings
from portfolio_chat_agent.planner.planner import ApiCall, PlannerOutput, run_planner
from portfolio_chat_agent.prompts.loader import render_prompt
from portfolio_chat_agent.compute.portfolio_api import (
    fetch_portfolio_allocation,
    fetch_portfolio_positions,
)
from portfolio_chat_agent.compute.search import search_web
from portfolio_chat_agent.checkpoint import get_checkpointer
from portfolio_chat_agent.observability.langfuse import (
    clear_trace,
    end_span,
    end_trace,
    start_span,
    start_trace,
)


IntentLabel = Literal["finance", "non_finance", "unknown"]
DataSource = Literal["portfolio_api", "market_data", "search", "derived"]


class SubQuestion(BaseModel):
    id: str
    question: str
    depends_on: list[str]
    data_source: DataSource


class DecomposedPlan(BaseModel):
    sub_questions: list[SubQuestion]
    join_strategy: str


class IntentResult(BaseModel):
    label: IntentLabel
    confidence: float
    rationale: str


class ClassificationDecision(BaseModel):
    needs_classification: bool
    dimension: str | None = None
    use_portfolio_field: bool = False
    portfolio_field: str | None = None
    need_search: bool = False
    rationale: str | None = None


class ClassificationMapping(BaseModel):
    dimension: str
    mapping: list[dict[str, str]] = []
    source: str = "llm"


class FollowupDecision(BaseModel):
    is_followup: bool
    rationale: str | None = None


class PortfolioNeedDecision(BaseModel):
    needs_portfolio: bool
    rationale: str | None = None


class ChatRunResult(BaseModel):
    run_id: str
    conversation_id: str
    status: str
    intent: IntentResult
    plan: PlannerOutput
    response: str | None = None
    followup_needed: bool = False
    debug: dict | None = None


class GraphState(TypedDict, total=False):
    run_id: str
    conversation_id: str
    question: str
    combined_question: str
    previous_question: str
    intent: IntentResult
    plan: PlannerOutput
    response: str
    status: str
    followup_needed: bool
    compute_mode: Literal["local", "sandbox", "none"]
    code: str
    execution_output: str
    execution_error: str
    error_history: list[str]
    attempts: int
    auth_token: str
    user_id: str
    search_results: list[dict[str, str]]
    history: list[dict[str, str]]
    parallel_mode: bool
    decomposed_plan: DecomposedPlan
    portfolio_fields: list[str]
    portfolio_tickers: list[str]
    classification_decision: ClassificationDecision
    classification_mapping: ClassificationMapping
    synth_needs_more: bool
    synth_missing: list[str]
    synth_attempts: int
    followup_decision: FollowupDecision


def _empty_plan(question: str) -> PlannerOutput:
    return PlannerOutput(
        technical_question=question,
        required_files=[],
        api_calls=[],
        tickers=[],
    )


def classify_intent_llm(question: str, history: list[dict[str, str]] | None = None) -> IntentResult:
    settings = get_settings()
    llm = get_llm(model=settings.intent_model, provider_override=settings.intent_provider)
    prompt = render_prompt("intent_prompt.j2", user_question=question, history=history or [])
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    payload = _parse_json_from_text(content)
    if payload:
        try:
            return IntentResult.model_validate(payload)
        except Exception:
            pass
    q = question.lower()
    if any(token in q for token in ["portfolio", "holdings", "sectors", "overweight", "allocation", "positions"]):
        return IntentResult(
            label="finance",
            confidence=0.6,
            rationale="Fallback: portfolio-related terms detected.",
        )
    return IntentResult(
        label="unknown",
        confidence=0.2,
        rationale="Failed to parse classifier output.",
    )


def _parse_json_from_text(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def detect_followup_llm(previous: str, current: str) -> FollowupDecision:
    settings = get_settings()
    llm = get_llm(model=settings.intent_model, provider_override=settings.intent_provider)
    prompt = render_prompt(
        "followup_prompt.j2",
        previous_question=previous,
        current_question=current,
    )
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    payload = _parse_json_from_text(content)
    if payload:
        try:
            return FollowupDecision.model_validate(payload)
        except Exception:
            pass
    return FollowupDecision(is_followup=False, rationale="Failed to parse follow-up detector output.")


def needs_portfolio_llm(question: str) -> PortfolioNeedDecision:
    settings = get_settings()
    llm = get_llm(model=settings.planner_model, provider_override=settings.planner_provider)
    prompt = render_prompt("portfolio_need_prompt.j2", user_question=question)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    payload = _parse_json_from_text(content)
    if payload:
        try:
            return PortfolioNeedDecision.model_validate(payload)
        except Exception:
            pass
    return PortfolioNeedDecision(needs_portfolio=False, rationale="Failed to parse portfolio-need output.")


def _intent_node(state: GraphState) -> GraphState:
    # Clear stale run-specific fields to avoid leakage across turns.
    state = {
        **state,
        "plan": None,
        "search_results": [],
        "code": "",
        "execution_output": "",
        "execution_error": "",
        "attempts": 0,
        "error_history": [],
        "classification_decision": None,
        "classification_mapping": None,
        "synth_needs_more": None,
        "synth_missing": None,
        "synth_attempts": 0,
    }
    question = state["question"]
    combined_question = question
    previous = state.get("previous_question")
    if previous:
        followup = detect_followup_llm(previous, question)
        if followup.is_followup:
            combined_question = f"Previous question: {previous}\nFollow-up: {question}"
        state = {**state, "followup_decision": followup}
    settings = get_settings()
    span = start_span(
        name="intent",
        input={"question": combined_question},
        metadata={"model": settings.intent_model, "provider": settings.intent_provider or settings.llm_provider},
    )
    intent = classify_intent_llm(combined_question, state.get("history"))
    end_span(span, output=intent.model_dump())
    return {
        **state,
        "intent": intent,
        "combined_question": combined_question,
        "previous_question": question,
    }


def _decompose_node(state: GraphState) -> GraphState:
    question = state.get("combined_question") or state["question"]
    settings = get_settings()
    span = start_span(
        name="decompose",
        input={"question": question},
        metadata={"model": settings.planner_model, "provider": settings.planner_provider or settings.llm_provider},
    )
    llm = get_llm(
        model=settings.planner_model,
        temperature=0.2,
        provider_override=settings.planner_provider,
    )
    prompt = render_prompt("decompose_prompt.j2", user_question=question)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    try:
        payload = json.loads(content)
        decomposed = DecomposedPlan.model_validate(payload)
    except Exception:
        decomposed = DecomposedPlan(
            sub_questions=[
                SubQuestion(
                    id="q1",
                    question=question,
                    depends_on=[],
                    data_source="derived",
                )
            ],
            join_strategy="none",
        )
    end_span(span, output=decomposed.model_dump())
    return {**state, "decomposed_plan": decomposed}


def _plan_node(state: GraphState) -> GraphState:
    question = state.get("combined_question") or state["question"]
    missing = state.get("synth_missing")
    if missing:
        question = f"{question}\nMissing data signals: {missing}"
    decomposed = state.get("decomposed_plan")
    if decomposed and len(decomposed.sub_questions) > 1:
        sub_qs = "\n".join(
            f"{sq.id}: {sq.question} (source={sq.data_source}, depends_on={sq.depends_on})"
            for sq in decomposed.sub_questions
        )
        question = (
            f"Decomposed sub-questions:\n{sub_qs}\nJoin strategy: {decomposed.join_strategy}\n"
            f"Original question: {question}"
        )
    settings = get_settings()
    span = start_span(
        name="planner",
        input={"question": question},
        metadata={"model": settings.planner_model, "provider": settings.planner_provider or settings.llm_provider},
    )
    plan = run_planner(question)
    intent = state.get("intent")
    if intent and intent.label == "finance":
        if any(call.tool == "classification_tool" for call in plan.api_calls):
            if "portfolio_positions" not in plan.portfolio_endpoints:
                plan.portfolio_endpoints = list(plan.portfolio_endpoints or [])
                plan.portfolio_endpoints.append("portfolio_positions")
        if not plan.portfolio_endpoints:
            need = needs_portfolio_llm(state.get("combined_question") or state.get("question") or "")
            if need.needs_portfolio:
                plan.portfolio_endpoints = ["portfolio_positions"]
                plan.compute_mode = plan.compute_mode or "local"
            elif not plan.api_calls:
                plan.api_calls = plan.api_calls or []
                plan.api_calls.append(ApiCall(tool="search_tool", query=state.get("question")))
                plan.compute_mode = "none"
        # If portfolio data is required but compute_mode is missing/none, default to local.
        if plan.portfolio_endpoints and (plan.compute_mode is None or plan.compute_mode == "none"):
            plan.compute_mode = "local"
    end_span(span, output=plan.model_dump())
    compute_mode = plan.compute_mode or "none"
    return {
        **state,
        "plan": plan,
        "status": "planned",
        "followup_needed": False,
        "compute_mode": compute_mode,
    }


def _reject_node(state: GraphState) -> GraphState:
    settings = get_settings()
    intent = state.get("intent")
    rationale = intent.rationale if intent else ""
    suffix = f" {rationale}".strip()
    example = f'"{settings.non_finance_nudge}"'
    span = start_span(
        name="reject",
        input={"question": state.get("question"), "intent": intent.model_dump() if intent else None},
    )
    response = (
        "Sorry, the answer is not related to your portfolio. "
        f"Please ask a question like {example}."
        + (f" {suffix}" if suffix else "")
    )
    end_span(span, output={"response": response})
    return {
        **state,
        "plan": _empty_plan(state["question"]),
        "status": "completed",
        "followup_needed": True,
        "previous_question": state["question"],
        "response": response,
        "history": _append_history(state, response),
    }


def _route_after_intent(state: GraphState) -> str:
    intent = state.get("intent")
    if intent is None:
        return "reject"
    if intent.label != "finance":
        return "reject"
    if intent.confidence < 0.5:
        return "reject"
    return "plan"


def _sandbox_placeholder_node(state: GraphState) -> GraphState:
    return {**state}


def _parallel_start_node(state: GraphState) -> GraphState:
    return {**state, "parallel_mode": True}


def _join_node(state: GraphState) -> GraphState:
    return {**state, "parallel_mode": False}


def _search_placeholder_node(state: GraphState) -> GraphState:
    plan = state.get("plan")
    queries: list[str] = []
    if plan:
        for call in plan.api_calls:
            if call.tool == "search_tool" and call.query:
                queries.append(call.query)
    if not queries:
        return {**state}
    settings = get_settings()
    span = start_span(
        name="search",
        input={"queries": queries},
        metadata={"provider": settings.search_provider},
    )
    results = [{"query": query, "results": search_web(query)} for query in queries]
    end_span(span, output={"results": results})
    return {**state, "search_results": results}


def _extract_items(payload: dict) -> list[dict]:
    for key in ("open", "tickers", "positions", "holdings", "items"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return [item for item in value if isinstance(item, dict)]
    for value in payload.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    return []


def _profile_portfolio_data(plan: PlannerOutput, auth_token: str | None) -> tuple[list[str], list[str]]:
    payload: dict = {}
    if "portfolio_positions" in plan.portfolio_endpoints:
        payload = fetch_portfolio_positions(auth_token)
    elif "portfolio_allocation" in plan.portfolio_endpoints:
        payload = fetch_portfolio_allocation(auth_token)
    items = _extract_items(payload)
    fields: set[str] = set()
    tickers: list[str] = []
    for item in items[:100]:
        fields.update(item.keys())
        ticker = item.get("ticker")
        if isinstance(ticker, str):
            tickers.append(ticker)
    sectors = payload.get("sectors")
    if isinstance(sectors, list) and sectors and isinstance(sectors[0], dict):
        fields.add("sector")
    return sorted(fields), sorted(set(tickers))


def _classification_node(state: GraphState) -> GraphState:
    plan = state.get("plan")
    if not plan or not plan.portfolio_endpoints:
        return {**state}
    wants_classification = any(call.tool == "classification_tool" for call in plan.api_calls)
    requested_dimension = None
    for call in plan.api_calls:
        if call.tool == "classification_tool":
            if call.params and isinstance(call.params, dict):
                requested_dimension = call.params.get("dimension")
            elif call.query:
                requested_dimension = call.query
            break
    auth_token = state.get("auth_token")
    fields, tickers = _profile_portfolio_data(plan, auth_token)
    question = state.get("combined_question") or state.get("question") or ""
    settings = get_settings()
    span = start_span(
        name="classification",
        input={"question": question, "fields": fields, "tickers": tickers[:20]},
        metadata={"model": settings.planner_model, "provider": settings.planner_provider or settings.llm_provider},
    )
    prompt = render_prompt(
        "classification_prompt.j2",
        user_question=question,
        available_fields=fields,
        tickers=tickers,
        requested_dimension=requested_dimension,
    )
    llm = get_llm(model=settings.planner_model, provider_override=settings.planner_provider)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    payload = _parse_json_from_text(content)
    if payload:
        try:
            decision = ClassificationDecision.model_validate(payload)
        except Exception:
            decision = None
    else:
        decision = None
    if decision is None:
        dimension = requested_dimension or "category"
        use_portfolio_field = bool(dimension and dimension in fields)
        decision = ClassificationDecision(
            needs_classification=True,
            dimension=dimension,
            use_portfolio_field=use_portfolio_field,
            portfolio_field=dimension if use_portfolio_field else None,
            need_search=not use_portfolio_field,
            rationale="Fallback decision after parse failure.",
        )
    if not wants_classification and not decision.needs_classification:
        end_span(span, output={"decision": decision.model_dump(), "mapping": None})
        return {**state}
    mapping: ClassificationMapping | None = None
    if decision.needs_classification and not decision.use_portfolio_field:
        map_llm = get_llm(model=settings.planner_model, provider_override=settings.planner_provider)

        def _run_mapping(subset: list[str], search_payload: list[dict]) -> list[dict[str, str]]:
            if not subset:
                return []
            map_prompt = render_prompt(
                "classification_mapping_prompt.j2",
                user_question=question,
                tickers=subset,
                search_results=json.dumps(search_payload, indent=2),
                dimension=decision.dimension or "category",
            )
            map_resp = map_llm.invoke(map_prompt)
            map_content = map_resp.content if hasattr(map_resp, "content") else str(map_resp)
            map_payload = _parse_json_from_text(map_content)
            if not map_payload:
                return []
            try:
                parsed = ClassificationMapping.model_validate(map_payload)
            except Exception:
                return []
            return parsed.mapping or []

        # Stage 1: attempt mapping without search for all tickers.
        initial_mapping = _run_mapping(tickers, [])
        mapped_tickers = {item.get("ticker") for item in initial_mapping if item.get("ticker")}
        missing = [t for t in tickers if t not in mapped_tickers]

        # Stage 2: for remaining tickers, optionally use search results.
        searched_mapping: list[dict[str, str]] = []
        search_results = []
        if decision.need_search and missing:
            for ticker in missing:
                search_results.append(
                    {"query": f"{ticker} sector industry classification", "results": search_web(f"{ticker} sector")}
                )
            searched_mapping = _run_mapping(missing, search_results)

        merged = initial_mapping + [
            item for item in searched_mapping if item.get("ticker") not in mapped_tickers
        ]
        mapping = ClassificationMapping(
            dimension=decision.dimension or "category",
            mapping=merged,
            source="llm_estimate",
        )
    end_span(
        span,
        output={
            "decision": decision.model_dump(),
            "mapping": mapping.model_dump() if mapping else None,
        },
    )
    return {
        **state,
        "portfolio_fields": fields,
        "portfolio_tickers": tickers,
        "classification_decision": decision,
        "classification_mapping": mapping,
    }


def _codegen_placeholder_node(state: GraphState) -> GraphState:
    question = state.get("combined_question") or state["question"]
    error = state.get("execution_error")
    error_history = state.get("error_history") or []
    plan = state.get("plan")
    required_endpoints = plan.portfolio_endpoints if plan else []
    tickers = state.get("portfolio_tickers") or (plan.tickers if plan else [])
    api_call_specs = [call.model_dump() for call in plan.api_calls] if plan else []
    prompt = render_prompt(
        "codegen_prompt.j2",
        user_question=question,
        technical_question=plan.technical_question if plan else question,
        tickers=tickers,
        required_endpoints=required_endpoints,
        api_call_specs=api_call_specs,
        error=error or "",
        error_history=error_history,
        classification_decision=(
            state.get("classification_decision").model_dump()
            if state.get("classification_decision")
            else None
        ),
        classification_mapping=(
            state.get("classification_mapping").model_dump()
            if state.get("classification_mapping")
            else None
        ),
    )
    settings = get_settings()
    span = start_span(
        name="codegen",
        input={
            "question": question,
            "technical_question": plan.technical_question if plan else question,
            "required_endpoints": required_endpoints,
            "tickers": tickers,
            "api_calls": api_call_specs,
            "error": error,
            "error_history": error_history,
        },
        metadata={"model": settings.codegen_model, "provider": settings.codegen_provider or settings.llm_provider},
    )
    llm = get_llm(
        model=settings.codegen_model,
        temperature=0.2,
        provider_override=settings.codegen_provider,
    )
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    code = _extract_code(content)
    end_span(span, output={"code": code})
    return {**state, "code": code, "execution_error": ""}


def _execute_placeholder_node(state: GraphState) -> GraphState:
    code = state.get("code") or ""
    attempts = int(state.get("attempts") or 0)
    auth_token = state.get("auth_token")
    span = start_span(
        name="execute",
        input={"code": code, "attempts": attempts, "compute_mode": state.get("compute_mode")},
    )
    try:
        _enforce_required_helpers(code, state.get("plan"))
        output = _run_code(code, auth_token)
        end_span(span, output={"output": output})
        return {
            **state,
            "execution_output": output,
            "execution_error": "",
            "status": "completed",
        }
    except Exception as exc:
        error_history = list(state.get("error_history") or [])
        error_history.append(str(exc))
        end_span(span, error=str(exc))
        return {
            **state,
            "execution_error": str(exc),
            "attempts": attempts + 1,
            "execution_output": code,
            "error_history": error_history,
        }


def _synthesizer_placeholder_node(state: GraphState) -> GraphState:
    output = state.get("execution_output")
    error = state.get("execution_error")
    code = state.get("code") or ""
    settings = get_settings()
    synth_attempts = int(state.get("synth_attempts") or 0)
    span = start_span(
        name="synthesizer",
        input={
            "question": state.get("combined_question") or state.get("question") or "",
            "execution_output": output,
            "search_results": state.get("search_results"),
            "has_error": bool(error),
            "synth_attempts": synth_attempts,
        },
        metadata={"model": settings.synth_model, "provider": settings.synth_provider or settings.llm_provider},
    )
    if error:
        response = f"Execution failed after retries: {error}\n\nGenerated code:\n{state.get('execution_output')}"
        end_span(span, output={"response": response, "error": error})
        return {
            **state,
            "response": response,
            "status": "completed",
            "history": _append_history(state, response),
            "synth_needs_more": False,
            "synth_missing": [],
            "synth_attempts": synth_attempts + 1,
        }
    question = state.get("combined_question") or state.get("question") or ""
    search_results = json.dumps(state.get("search_results") or [], indent=2)
    prompt = render_prompt(
        "synthesizer_prompt.j2",
        user_question=question,
        execution_output=output or "No execution output.",
        search_results=search_results,
        history=state.get("history") or [],
    )
    llm = get_llm(
        model=get_settings().synth_model,
        temperature=0.2,
        provider_override=settings.synth_provider,
    )
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    # Check if more data is needed (ReACT-style loop trigger)
    check_prompt = render_prompt(
        "synth_check_prompt.j2",
        user_question=question,
        execution_output=output or "",
        search_results=search_results,
    )
    check_llm = get_llm(
        model=settings.synth_model,
        temperature=0.0,
        provider_override=settings.synth_provider,
    )
    check_resp = check_llm.invoke(check_prompt)
    check_content = check_resp.content if hasattr(check_resp, "content") else str(check_resp)
    needs_more = False
    missing: list[str] = []
    try:
        check_payload = json.loads(check_content)
        needs_more = not bool(check_payload.get("sufficient", True))
        missing = check_payload.get("missing") or []
        if not isinstance(missing, list):
            missing = []
    except Exception:
        needs_more = False
        missing = []

    end_span(
        span,
        output={
            "response": content,
            "needs_more": needs_more,
            "missing": missing,
        },
    )
    return {
        **state,
        "response": content,
        "status": "completed",
        "history": _append_history(state, content),
        "synth_needs_more": needs_more,
        "synth_missing": missing,
        "synth_attempts": synth_attempts + 1,
    }


def _append_history(state: GraphState, response: str) -> list[dict[str, str]]:
    history = list(state.get("history") or [])
    question = state.get("question")
    if question:
        if not history or history[-1].get("content") != question:
            history.append({"role": "user", "content": question})
    if not history or history[-1].get("content") != response:
        history.append({"role": "assistant", "content": response})
    return history


def load_chat_history(conversation_id: str, user_id: str | None = None) -> list[dict[str, str]]:
    if not conversation_id:
        return []
    checkpointer = get_checkpointer()
    if not checkpointer:
        return []
    thread_id = f"{user_id}:{conversation_id}" if user_id else conversation_id
    try:
        checkpoint = checkpointer.get({"configurable": {"thread_id": thread_id}})
    except Exception:
        return []
    if not checkpoint:
        return []
    values = None
    if hasattr(checkpoint, "channel_values"):
        values = checkpoint.channel_values
    elif isinstance(checkpoint, dict):
        values = checkpoint.get("channel_values") or checkpoint.get("values")
    if not isinstance(values, dict):
        return []
    history = values.get("history")
    if not isinstance(history, list):
        return []
    return [
        item
        for item in history
        if isinstance(item, dict) and "role" in item and "content" in item
    ]


def _run_code(code: str, auth_token: str | None) -> str:
    import json as _json
    import io
    import textwrap
    from contextlib import redirect_stdout

    # Strip import lines (json is already provided in globals).
    lines = []
    for line in code.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        lines.append(line)
    code = "\n".join(lines).strip()
    if not code:
        raise ValueError("No executable code after removing import statements.")

    allowed_builtins = {
        "print": print,
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "sorted": sorted,
        "list": list,
        "dict": dict,
        "set": set,
        "float": float,
        "int": int,
        "str": str,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
    }

    def get_portfolio_allocation():
        return fetch_portfolio_allocation(auth_token)

    def get_portfolio_positions():
        return fetch_portfolio_positions(auth_token)

    sandbox_globals = {
        "__builtins__": allowed_builtins,
        "get_portfolio_allocation": get_portfolio_allocation,
        "get_portfolio_positions": get_portfolio_positions,
        "json": _json,
    }
    sandbox_locals: dict = {}

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exec(textwrap.dedent(code), sandbox_globals, sandbox_locals)

    stdout = buffer.getvalue().strip()
    if not stdout:
        raise ValueError("Execution produced no output. Ensure the code prints JSON.")

    try:
        parsed = _json.loads(stdout)
    except Exception as exc:
        raise ValueError(f"Execution output is not valid JSON: {exc}") from exc

    _validate_output_schema(parsed)
    return _json.dumps(parsed, indent=2)


def _enforce_required_helpers(code: str, plan: PlannerOutput | None) -> None:
    if not plan:
        return
    if "portfolio_allocation" in plan.portfolio_endpoints:
        if "get_portfolio_allocation" not in code:
            raise ValueError("Code must call get_portfolio_allocation() for this request.")
    else:
        if "get_portfolio_allocation" in code:
            raise ValueError("Code must not call get_portfolio_allocation() for this request.")
    if "portfolio_positions" in plan.portfolio_endpoints:
        if "get_portfolio_positions" not in code:
            raise ValueError("Code must call get_portfolio_positions() for this request.")


def _validate_output_schema(payload: object) -> None:
    if not isinstance(payload, (dict, list)):
        raise ValueError("Output must be a JSON object or array.")
    if isinstance(payload, dict) and not payload:
        raise ValueError("Output object must not be empty.")


def _extract_code(content: str) -> str:
    text = content.strip()
    if "```" not in text:
        return text
    # Extract first fenced block
    parts = text.split("```")
    if len(parts) >= 2:
        code_block = parts[1]
        # Remove optional language tag
        lines = code_block.splitlines()
        if lines and lines[0].strip().lower() in {"python", "py"}:
            lines = lines[1:]
        return "\n".join(lines).strip()
    return text


def build_chat_graph():
    graph = StateGraph(GraphState)
    graph.add_node("intent_node", _intent_node)
    graph.add_node("decompose_node", _decompose_node)
    graph.add_node("plan_node", _plan_node)
    graph.add_node("classification_node", _classification_node)
    graph.add_node("reject_node", _reject_node)
    graph.add_node("search_node", _search_placeholder_node)
    graph.add_node("parallel_start", _parallel_start_node)
    graph.add_node("join_node", _join_node)
    graph.add_node("sandbox_node", _sandbox_placeholder_node)
    graph.add_node("codegen_node", _codegen_placeholder_node)
    graph.add_node("execute_node", _execute_placeholder_node)
    graph.add_node("synthesizer_node", _synthesizer_placeholder_node)

    graph.set_entry_point("intent_node")
    graph.add_conditional_edges(
        "intent_node",
        _route_after_intent,
        {"plan": "decompose_node", "reject": "reject_node"},
    )
    graph.add_edge("decompose_node", "plan_node")
    graph.add_edge("plan_node", "classification_node")
    def _route_after_plan(state: GraphState) -> str:
        plan = state.get("plan")
        has_search = any(call.tool == "search_tool" for call in plan.api_calls) if plan else False
        mode = state.get("compute_mode", "sandbox")
        if has_search and mode != "none":
            return "parallel"
        if has_search:
            return "search_only"
        if mode == "none":
            return "end"
        return "sandbox_only"

    graph.add_conditional_edges(
        "classification_node",
        _route_after_plan,
        {
            "parallel": "parallel_start",
            "search_only": "search_node",
            "sandbox_only": "sandbox_node",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "search_node",
        lambda state: "join"
        if state.get("parallel_mode")
        else ("synth" if state.get("compute_mode") == "none" else "codegen"),
        {"join": "join_node", "codegen": "codegen_node", "synth": "synthesizer_node"},
    )
    graph.add_conditional_edges(
        "sandbox_node",
        lambda state: "join" if state.get("parallel_mode") else "codegen",
        {"join": "join_node", "codegen": "codegen_node"},
    )
    graph.add_conditional_edges(
        "parallel_start",
        lambda state: [
            Send("search_node", {**state}),
            Send("sandbox_node", {**state}),
        ],
    )
    graph.add_edge("join_node", "codegen_node")
    graph.add_edge("codegen_node", "execute_node")
    graph.add_conditional_edges(
        "execute_node",
        lambda state: "retry" if state.get("execution_error") and (state.get("attempts", 0) < 3) else "done",
        {"retry": "codegen_node", "done": "synthesizer_node"},
    )
    def _route_after_synth(state: GraphState) -> str:
        if state.get("synth_needs_more") and int(state.get("synth_attempts") or 0) < 3:
            return "replan"
        return "end"

    graph.add_conditional_edges(
        "synthesizer_node",
        _route_after_synth,
        {"replan": "plan_node", "end": END},
    )
    graph.add_edge("reject_node", END)
    checkpointer = get_checkpointer()
    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def run_chat_graph(question: str) -> ChatRunResult:
    return run_chat_graph_with_conversation(question=question, conversation_id=None, auth_token=None)


def run_chat_graph_with_conversation(
    question: str, conversation_id: str | None, auth_token: str | None, user_id: str | None = None
) -> ChatRunResult:
    runner = build_chat_graph()
    run_id = str(uuid4())
    conversation = conversation_id or str(uuid4())
    if not auth_token:
        return ChatRunResult(
            run_id=run_id,
            conversation_id=conversation,
            status="error",
            intent=IntentResult(label="unknown", confidence=0.0, rationale=""),
            plan=_empty_plan(question),
            response="Unable to access your portfolio. Please reconnect your account.",
            followup_needed=False,
        )
    thread_id = f"{user_id}:{conversation}" if user_id else conversation
    settings = get_settings()
    trace = start_trace(
        name="chat_run",
        input={"question": question, "conversation_id": conversation, "user_id": user_id},
        user_id=user_id,
        session_id=conversation,
        metadata={
            "intent_model": settings.intent_model,
            "planner_model": settings.planner_model,
            "codegen_model": settings.codegen_model,
            "synth_model": settings.synth_model,
            "llm_provider": settings.llm_provider,
            "codegen_provider": settings.codegen_provider,
            "intent_provider": settings.intent_provider,
            "planner_provider": settings.planner_provider,
            "synth_provider": settings.synth_provider,
        },
    )
    result: dict = {}
    error: str | None = None
    try:
        result = runner.invoke(
            {
                "run_id": run_id,
                "conversation_id": conversation,
                "question": question,
                "status": "started",
                "auth_token": auth_token,
                "user_id": user_id,
            },
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        clear_trace()
        end_trace(
            trace,
            output={"status": result.get("status"), "response": result.get("response"), "error": error},
        )

    intent = result.get("intent") or IntentResult(
        label="unknown",
        confidence=0.0,
        rationale="No intent result.",
    )
    plan = result.get("plan") or _empty_plan(question)
    debug = {
        "intent": (result.get("intent") or intent).model_dump()
        if hasattr(result.get("intent") or intent, "model_dump")
        else result.get("intent"),
        "followup_decision": (
            result.get("followup_decision").model_dump()
            if hasattr(result.get("followup_decision"), "model_dump")
            else result.get("followup_decision")
        ),
        "plan": plan.model_dump() if hasattr(plan, "model_dump") else plan,
        "classification_decision": (
            result.get("classification_decision").model_dump()
            if hasattr(result.get("classification_decision"), "model_dump")
            else result.get("classification_decision")
        ),
        "classification_mapping": (
            result.get("classification_mapping").model_dump()
            if hasattr(result.get("classification_mapping"), "model_dump")
            else result.get("classification_mapping")
        ),
        "synth_needs_more": result.get("synth_needs_more"),
        "synth_missing": result.get("synth_missing"),
        "synth_attempts": result.get("synth_attempts"),
        "search_results": result.get("search_results"),
        "code": result.get("code"),
        "execution_output": result.get("execution_output"),
        "execution_error": result.get("execution_error"),
        "status": result.get("status", "completed"),
    }
    return ChatRunResult(
        run_id=run_id,
        conversation_id=conversation,
        status=result.get("status", "completed"),
        intent=intent,
        plan=plan,
        response=result.get("response"),
        followup_needed=bool(result.get("followup_needed")),
        debug=debug,
    )
