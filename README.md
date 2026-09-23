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


## Run

```bash
uvicorn app.main:app --reload
```



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

