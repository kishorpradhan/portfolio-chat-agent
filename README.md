
# Portfolio Chat Agent

A **production-oriented LLM orchestration service** that powers portfolio intelligence for **moniq.chat**.

This project explores how to design **reliable, observable, and cost-efficient agentic AI workflows** using the same engineering principles used to build large-scale data and analytics platforms.

Unlike many LLM demos, this system focuses on:

- Stateful AI workflows
- Intent-aware and cost-aware model routing
- Deterministic-first architecture
- Traceability and debugging
- Real product integration

This service acts as the **reasoning engine behind moniq.chat**, enabling users to ask questions such as:

- “What sectors am I overweight in?”
- “How did my portfolio perform in 2025 compared to the S&P 500?”
- “If I had not sold my Nvidia positions, would I be better or worse off today?”
- “How concentrated is my portfolio?”

---

# Why I Built This

After spending years building **petabyte-scale data platforms**, I became curious about a new problem:

> How do you build **production-grade AI systems**, using the same engineering discipline we apply to distributed systems — not just prompt-based demos?

Most LLM projects focus on prompts.

Real systems require:

- state management
- cost control
- observability
- failure recovery
- deterministic computation where possible
- sandboxed code execution
- reproducible analytics derived from executable code

This project explores how **platform engineering principles apply to AI systems**, while powering the portfolio intelligence capabilities behind **Moniq**.

---

# Product Context: Moniq

This service powers **Moniq**, a portfolio intelligence platform designed to help investors understand their investments using natural language.

Instead of navigating dashboards, users can ask questions directly about their portfolios.

Examples:

- What are my top positions?
- Am I too concentrated?
- What sectors dominate my portfolio?
- How did my portfolio perform compared to NASDAQ in December 2025?
- What drove my returns last month?

The agent converts natural language questions into:

1. Data queries  
2. Portfolio analytics  
3. Interpretable explanations  

The same pattern can also be applied to other domains such as **campaign analytics** used by retail media companies like Walmart, Amazon, and Home Depot.

---

# Design Philosophy

## Deterministic Systems First

Financial insights must be **repeatable and explainable**.

The system prioritizes:

1. Deterministic analytics  
2. Cached computations and reusable code  
3. LLM reasoning only when necessary  

This improves **reliability, trustworthiness, and cost efficiency**.

---

## Observability Over Magic

AI systems are difficult to debug.

This system instruments every step with tracing so we can observe:

- model inputs  
- outputs  
- latency  
- token cost  
- errors  

---

## Cost Is a Product Metric

LLMs are powerful but expensive.

Model routing is used to control cost while maintaining quality.

| Task | Model |
|-----|------|
| Intent classification | Gemini Nano |
| Planning | Gemini Nano |
| Reasoning / synthesis | OpenAI |
| Fallbacks | Deterministic logic |

Goal: keep **per-query cost below $0.01**.

---

# Engineering Tradeoffs

## Tradeoff: Let the LLM Analyze Raw Portfolio Data vs Deterministic Analytics

A simpler architecture would allow the LLM to directly analyze all portfolio trades.

Example architecture:

```
+--------------------+
|    User Question   |
+---------+----------+
          |
          v
+--------------------+
| Upload Portfolio   |
| Data to LLM        |
+---------+----------+
          |
          v
+--------------------+
| LLM Performs       |
| Analysis           |
+---------+----------+
          |
          v
+--------------------+
| Answer Returned    |
+--------------------+
```

Advantages:

- simpler architecture  
- fewer system components  
- faster initial development  

However, this introduces serious risks.

### Risk 1: Hallucinated Financial Calculations

LLMs are probabilistic systems and may produce **incorrect numerical reasoning**.

Possible issues include:

- incorrect trade aggregation  
- inconsistent return calculations  
- incorrect benchmark comparisons  

For financial analytics, correctness is critical.

Instead, this system performs **all financial calculations using deterministic Python code executed in a sandbox environment**.

LLMs are used only for:

- understanding the question  
- planning the analytics  
- explaining the results  

---

### Risk 2: Data Privacy

Uploading full trade histories to an LLM increases data exposure.

A portfolio may contain:

- trade history  
- cost basis  
- position sizes  
- personal investment strategies  

This architecture follows **data minimization principles**:

- LLMs receive **only metadata or computed outputs**  
- raw trade data stays within the **Moniq platform**  
- computations run inside a **sandbox execution environment**  

---

## Final Architecture

```
+--------------------+
|   User Question    |
+---------+----------+
          |
          v
+--------------------+
| LLM Intent + Plan  |
+---------+----------+
          |
          v
+--------------------+
| Deterministic      |
| Python Analytics   |
+---------+----------+
          |
          v
+--------------------+
| Sandbox Execution  |
+---------+----------+
          |
          v
+--------------------+
| LLM Explanation    |
+--------------------+
```

Benefits:

- deterministic financial calculations  
- reduced hallucination risk  
- minimal exposure of sensitive portfolio data  
- improved reliability  

---

# System Architecture

```
+-----------------------+
|      User Question    |
+-----------+-----------+
            |
            v
+-----------------------+
| Load Conversation     |
| Context (PostgreSQL)  |
+-----------+-----------+
            |
            v
+-----------------------+
|   Intent Classifier   |
+-----------+-----------+
            |
            v
+-----------------------+
|        Planner        |
+-----------+-----------+
            |
            v
+-----------------------+
|     Code Generator    |
+-----------+-----------+
            |
            v
+-----------------------+
|   Sandbox Executor    |
+-----------+-----------+
            |
            v
+-----------------------+
|   Result Synthesizer  |
+-----------+-----------+
            |
            v
+-----------------------+
| Response + History    |
+-----------------------+
```

### Component Responsibilities

| Component | Responsibility |
|----------|---------------|
| Intent classifier | Determines if the query is portfolio-related. Stops execution if the user asks unrelated questions |
| Planner | Identifies required data and computations |
| Code generator | Generates Python analytics code |
| Executor | Executes calculations in a sandbox |
| Synthesizer | Converts results into natural explanations |

---

# Future Roadmap

The current version focuses on building a **reliable and observable agent architecture**.

Future iterations will focus on improving **latency, reasoning quality, and deterministic reuse**.

## 1. Latency Optimization

Future work will focus on:

- collapsing steps for simple queries  
- caching results  
- optimizing model routing  
- parallel execution where possible  

Goal:

**Sub-second responses for common queries.**

---

## 2. Handling Ambiguous Questions

Users often ask ambiguous questions such as:

- “What are the trading mistakes I made in 2025?”
- “How does my US portfolio perform compared to my India portfolio?”
- “Is my portfolio risky?”

Future improvements:

- automatic context inference  
- clarification prompts  
- better benchmark selection  

---

## 3. Deterministic Knowledge Reuse

Many users ask similar questions.

Examples:

- “What sectors am I overweight in?”
- “What are my largest holdings?”
- “How concentrated is my portfolio?”

The **analytics logic is identical**, even though portfolios differ.

Future architecture:

```
+--------------------+
|   User Question    |
+---------+----------+
          |
          v
+--------------------+
| Vector Similarity  |
| Search             |
+----+---------+-----+
     |         |
     v         v
 Match       No Match
 Found        |
     |         v
     v     Full Agent
Reuse Code   Workflow
```

Benefits:

- lower LLM cost  
- faster responses  
- consistent analytics  

---

# Tech Stack

| Layer | Technology |
|------|-----------|
| Orchestration | LangGraph |
| LLM routing | LiteLLM |
| State storage | PostgreSQL |
| Observability | Langfuse |
| Server | FastAPI |
| Execution | Python sandbox |
| Vector search | Planned |

The service is deployed on **GCP** and leverages managed services including:

- managed PostgreSQL
- Gemini models
- serverless infrastructure

---

# Running Locally

### Prerequisites

- Python 3.10+
- PostgreSQL
- API keys for LLM providers

### Setup

```bash
git clone <repo>
cd portfolio-chat-agent

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Run server

```bash
uvicorn portfolio_chat_agent.app:app --reload
```

---

# Author

**Kishor Pradhan**

Engineering leader with experience building large-scale data platforms across:

- Advertising
- Streaming
- Commerce
- Financial systems

Exploring how **platform engineering principles apply to modern AI systems**.
