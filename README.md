# Terminal Agent

A terminal agent that turns plain English into shell commands, classifies how risky each one is,
asks before running anything destructive, and reads the output to decide what to do next.

Built with LangGraph and FastAPI, running open-source models through Groq.

```
you> what is taking up space in this project

agent> I will check the directory sizes.
       [ran: du -sh * | sort -h]
       The .venv folder is 340 MB, everything else is under 2 MB.

you> delete the build folder

       ┌─ approval needed ───────────────────────────────┐
       │ risk       command          why                 │
       │ DANGEROUS  rm -rf build     rm can destroy data  │
       └─────────────────────────────────────────────────┘
       run it? [y/N]
```

## How it works

```
CLI client ──websocket──▶ FastAPI ──▶ LangGraph
                                          │
        ┌─────────────────────────────────┼──────────────────────────┐
        ▼                                 ▼                          ▼
    agent node                      safety node               approval node
  LLM + bound tools               classify the risk        interrupt() and wait
                                          │
                                          ▼
                                      tool node
                                 sandboxed subprocess
```

The graph pauses at the approval node using LangGraph's `interrupt()`, which saves the full state
to a checkpointer. Answering resumes it from exactly that point. Read
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how that works.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
```

Get a free key at [console.groq.com](https://console.groq.com) and put it in `.env`.

## Run

Start the server:

```bash
uvicorn app.main:app --reload
```

Then the client, in a second terminal:

```bash
python -m cli.main chat
```

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /api/chat` | Send a message, get a reply or an approval request |
| `POST /api/approve` | Answer a pending approval |
| `GET /api/sessions/{id}/history` | Replay a conversation |
| `WS /ws/{thread_id}` | Streaming tokens and interactive approvals |
| `GET /health` `GET /ready` | Liveness and readiness |
| `GET /docs` | Interactive OpenAPI docs |

## Safety

| Tier | Behaviour | Examples |
| --- | --- | --- |
| safe | runs immediately | `ls`, `cat`, `git status` |
| caution | asks first | `mkdir`, `pip install`, `git commit` |
| dangerous | asks with a warning | `rm -rf build`, `chmod 777`, `git push` |
| blocked | never runs | `rm -rf /`, `mkfs`, `curl url \| sh` |

Commands are classified on parsed tokens, so `rm  -rf  /` with extra spaces and
`/usr/bin/rm -rf /` are both caught, while `echo "rm -rf /"` is not a false alarm. Details in
[docs/SAFETY.md](docs/SAFETY.md).

## Test

```bash
pytest
ruff check .
```

The graph takes an injected model, so the full suite runs against a fake LLM. No API key and no
network needed to test routing, interrupts, approvals, denials, blocking and the iteration limit.

## Layout

| Path | Responsibility |
| --- | --- |
| `app/config.py` | Typed settings validated from `.env` |
| `app/api/` | HTTP routes, websocket handler, schemas |
| `app/graph/` | LangGraph state, nodes, edges, runtime |
| `app/llm/` | Model factory and system prompt |
| `app/tools/` | Shell, filesystem and git tools |
| `app/safety/` | Risk classification and the blocklist |
| `app/execution/` | Subprocess runner and path jail |
| `cli/` | Rich terminal client |

## Stack

FastAPI, LangGraph, LangChain, Groq, Typer, Rich, structlog, pytest, ruff.
