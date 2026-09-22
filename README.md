# Terminal Agent

A terminal agent that turns natural language into shell commands, classifies their risk, asks for
approval, and runs them. Built on LangGraph with open-source models served through Groq.

## How it works

```
You ──▶ CLI client ──WebSocket──▶ FastAPI ──▶ LangGraph state machine
                                                      │
                          ┌───────────────────────────┼──────────────────────┐
                          ▼                           ▼                      ▼
                    agent node                  safety node           approval node
                 (LLM + bound tools)          (risk classify)        (interrupt for y/n)
                                                      │
                                                      ▼
                                                 tool node
                                            (sandboxed subprocess)
```

The graph pauses at the approval node using LangGraph's `interrupt()`, persists its state to a
checkpointer, and resumes exactly where it stopped once you answer.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
```

Add your free Groq API key from https://console.groq.com to `.env`.

## Run

```bash
uvicorn app.main:app --reload
```

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process is alive |
| `GET /ready` | Config is valid and the agent can serve requests |
| `GET /docs` | Interactive OpenAPI docs |

## Test

```bash
pytest
ruff check .
```

## Project layout

| Path | Responsibility |
| --- | --- |
| `app/config.py` | Typed settings loaded and validated from `.env` |
| `app/api/` | HTTP routes, WebSocket handler, request/response models |
| `app/graph/` | LangGraph state, nodes, and conditional edges |
| `app/llm/` | Model factory and system prompts |
| `app/tools/` | Tools the agent can call |
| `app/safety/` | Command risk classification and blocklist |
| `app/execution/` | Subprocess runner with timeout and output limits |
| `cli/` | Rich terminal client |

## Build log

| Milestone | Status |
| --- | --- |
| 1. Skeleton, config, health checks | done |
| 2. LLM factory and tools | next |
| 3. Safety classifier and executor | |
| 4. LangGraph workflow | |
| 5. Human-in-the-loop approvals | |
| 6. WebSocket streaming | |
| 7. Rich CLI client | |
