# Portfolio Chat Agent

LangGraph-based chat planner + codegen/execute/synth service for portfolio questions.

## Run (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# required env vars live in .env.local
uvicorn portfolio_chat_agent.app:app --reload --app-dir src
```

## Endpoints

- `GET /health`
- `POST /chat/run`
