from fastapi import FastAPI, Request
from pydantic import BaseModel

from portfolio_chat_agent.graph.chat_graph import load_chat_history, run_chat_graph_with_conversation
from portfolio_chat_agent.planner.planner import run_planner

app = FastAPI()


class PlanRequest(BaseModel):
    question: str


class ChatRunRequest(BaseModel):
    question: str
    conversation_id: str | None = None
    user_id: str | None = None


class ChatHistoryRequest(BaseModel):
    conversation_id: str
    user_id: str | None = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/plan")
def plan(request: PlanRequest):
    plan_output = run_planner(request.question)
    return plan_output.model_dump()


@app.post("/chat/run")
def chat_run(request: Request, payload: ChatRunRequest):
    auth_header = request.headers.get("authorization") or ""
    auth_token = auth_header
    if auth_header.lower().startswith("bearer "):
        auth_token = auth_header.split(" ", 1)[1].strip()
    result = run_chat_graph_with_conversation(
        question=payload.question,
        conversation_id=payload.conversation_id,
        user_id=payload.user_id,
        auth_token=auth_token or None,
    )
    return result.model_dump()


@app.post("/chat/history")
def chat_history(payload: ChatHistoryRequest):
    messages = load_chat_history(payload.conversation_id, user_id=payload.user_id)
    return {"conversation_id": payload.conversation_id, "messages": messages}
