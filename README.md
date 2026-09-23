# Terminal Agent

Ask for what you want in plain English. The agent works out which shell command does it, decides
how risky that command is, asks you before running anything destructive, reads the output, and
decides what to do next.

Built with LangGraph and FastAPI, running open-source models through Groq.

```
you> what is taking up space in this project

agent> The .venv folder is 340 MB. Everything else is under 2 MB.


you> delete the build folder

       ┌─ approval needed ──────────────────────────────────────────┐
       │ risk       command             why                         │
       │ DANGEROUS  rm -rf build        rm can destroy data          │
       └────────────────────────────────────────────────────────────┘
       run it? [y/N]
```

Type `delete everything on my computer` and no prompt appears at all. The command is blocked before
it can reach you, so you cannot approve it by mistake.

---

## Contents

- [What problem this solves](#what-problem-this-solves)
- [How it works](#how-it-works)
- [The safety model](#the-safety-model)
- [Setup](#setup)
- [Running it](#running-it)
- [Things to try](#things-to-try)
- [Project layout](#project-layout)
- [How the code fits together](#how-the-code-fits-together)
- [API](#api)
- [Configuration](#configuration)
- [Testing](#testing)
- [What is deliberately not built](#what-is-deliberately-not-built)
- [Troubleshooting](#troubleshooting)

---

## What problem this solves

You know what you want the terminal to do. You do not always remember the exact command, the flags
differ between Windows and Linux, and a mistyped `rm` is unforgiving.

An LLM can write the command for you. The risk is that it can also write a command that destroys
your work, and it will do so with complete confidence. So the interesting problem is not generating
commands, it is deciding which ones a human should see first.

This project is an answer to that. Every command the model proposes is classified before it runs,
and anything that changes your machine stops and waits for you.

---

## How it works

```
you type a request
        │
        ▼
   Rich CLI client
        │  websocket
        ▼
   FastAPI server
        │
        ▼
  LangGraph state machine
        │
        ├── agent node      ask the model what to do
        ├── safety node     classify the risk of each tool call
        ├── approval node   pause and wait for a human
        └── tool node       run what was approved
        │
        └── loop back to the agent with the output
```

The graph is four nodes and two decision points.

| Node | What it does |
| --- | --- |
| `agent` | Calls the LLM with the tool schemas attached. Returns plain text, or a request to call a tool |
| `safety` | Classifies every requested call as safe, caution, dangerous or blocked |
| `approval` | Pauses the graph and asks the human. Skipped entirely when everything is safe |
| `tools` | Runs the approved calls and returns their output as messages the model can read |

Routing between them:

- After `agent`, a tool call goes to `safety`, and plain text ends the run.
- After `safety`, anything needing approval goes to `approval`, everything else goes straight to
  `tools`.
- `tools` always returns to `agent`, so the model reads what happened before deciding the next step.

That loop is what makes it an agent rather than a command translator. Ask it why a service is down
and it will check whether the process is running, read the error log, then check the database,
choosing each step based on what the previous one returned.

### How the pause actually works

This is the part worth understanding, because it is not a blocking wait.

`approval_node` calls LangGraph's `interrupt()`. LangGraph writes the entire graph state to a
checkpointer and returns control to the caller, carrying the approval request. Nothing has run.

When you answer, the caller invokes the graph again with `Command(resume=decision)`. LangGraph loads
the saved state and re-runs the approval node from the top, and this time `interrupt()` returns your
decision instead of pausing. Because the node re-runs, it is written to be safe to execute twice.

The conversation is keyed by a `thread_id`. Send the same id and you continue the same conversation,
including resuming one that is paused waiting for you. With a database-backed checkpointer, a paused
approval would survive a server restart.

---

## The safety model

Every command is classified before it runs.

| Tier | What happens | Examples |
| --- | --- | --- |
| **safe** | Runs immediately, no prompt | `ls`, `cat`, `Get-Process`, `git status` |
| **caution** | Shows the command and asks | `mkdir`, `pip install`, `git commit` |
| **dangerous** | Asks, with a red warning | `rm -rf build`, `chmod 777`, `git push` |
| **blocked** | Never runs, and you are never asked | `rm -rf /`, `mkfs`, `curl url \| sh` |

Blocked is a separate tier from dangerous on purpose. Dangerous asks you. Blocked refuses, so a
catastrophic command cannot be approved by a tired yes.

### Why it parses instead of matching strings

Classification runs on tokens from `shlex.split`, never on the raw string. Matching text fails in
both directions.

| Input | Naive string match | What this does |
| --- | --- | --- |
| `rm  -rf  /` | misses it, extra spaces | blocked |
| `/usr/bin/rm -rf build` | misses it, path prefix | dangerous |
| `echo "rm -rf /"` | false alarm | safe |
| `ls && rm -rf data` | misses the second half | dangerous |
| `bash -c "rm -rf /"` | misses it, wrapped | blocked |

Four details make that work:

- `shlex.split` normalises spacing and quoting.
- `Path(token).name` strips directories and `.exe`, so a full path cannot disguise a command.
- Chains split on `&&`, `||` and `;`, and the whole command takes the worst verdict of its parts.
- Shell wrappers are unwrapped, so `bash -c` and `powershell -Command` are judged by what is inside
  them rather than by the wrapper.

That last one was a real hole found during development. Before it was fixed, any dangerous command
could slip past the blocklist by being wrapped in `bash -c`.

A pipeline is treated differently from a chain, because a pipe passes data between commands while
`&&` runs separate ones. `Get-Process | Format-Table` is safe. `Get-Process | Stop-Process` is not.

### When it is not sure

Unknown commands are classified as caution, never safe. Installing a new tool cannot silently widen
what runs without asking. The approval prompt also defaults to no, so pressing enter without reading
declines.

### Guards on execution

Even an approved command runs under limits.

| Guard | Why |
| --- | --- |
| Timeout, then terminate, then kill | A hung command would otherwise block the agent forever |
| Output truncation | A huge result would exhaust the context window and cost tokens |
| Scrubbed environment | Commands cannot read `GROQ_API_KEY` or other secrets |
| Working directory jail | `read_file("../../../etc/passwd")` resolves outside the root and is refused |
| Iteration limit | A model that loops without progress is stopped and reports what it tried |

---

## Setup

You need Python 3.11 or newer and a free Groq API key.

```bash
git clone https://github.com/Maheshmk18/Terminal_Agent.git
cd Terminal_Agent

python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS or Linux

pip install -r requirements.txt
```

## Run

Copy the example config and add your key:

```bash
copy .env.example .env          # Windows
cp .env.example .env            # macOS or Linux
```

Get a free key at [console.groq.com](https://console.groq.com) and put it in `.env`:

```
GROQ_API_KEY=gsk_your_key_here
```

---

## Running it

Two terminals. The server holds the agent, the client talks to it.

**Terminal 1, the server:**

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app
```

Wait for `Application startup complete`. The line above it confirms your configuration:

```json
{"model": "openai/gpt-oss-120b", "max_iterations": 10, "recursion_limit": 40, "event": "starting"}
```

**Terminal 2, the client:**

```bash
.venv\Scripts\python.exe -m cli.main chat
```

Check the server is healthy at any time:

```
http://127.0.0.1:8000/ready
```

It returns `ready: true`, or names exactly what is wrong.

---

## Things to try

Work down the list to see each tier of the safety model.

**Safe, runs immediately:**

```
what files are in this project
show me what is in the docs folder
what is the git status
show me the last 5 commits
```

**Caution, stops and asks:**

```
create a folder called scratch
write a file called notes.txt that says hello
```

Answer `n` the first time and watch it acknowledge rather than retry.

**Dangerous, red warning:**

```
delete the scratch folder
```

**Blocked, never asks you:**

```
delete everything on my computer
```

No prompt appears. The agent explains that it cannot do that.

**Multi-step, where the loop shows:**

```
find the largest file in this project
run the tests and tell me if they pass
read app/safety/classifier.py and tell me if you see any bugs
```

Each of these needs several commands, with the model reading each result before choosing the next.

Ask in plain English rather than in commands. Saying `what is using disk space` is the point.
Typing `run du -sh` is just a slower terminal.

---

## Project layout

```
Terminal_Agent/
│
├── app/
│   ├── main.py                    FastAPI app, startup, error handling
│   ├── config.py                  Typed settings read and validated from .env
│   │
│   ├── api/
│   │   ├── deps.py                Shared dependencies for routes
│   │   ├── schemas.py             Request and response models
│   │   ├── websocket.py           Streaming endpoint and approval round trip
│   │   └── routes/
│   │       ├── chat.py            POST /api/chat and /api/approve
│   │       ├── session.py         Conversation history
│   │       └── health.py          Liveness and readiness
│   │
│   ├── graph/
│   │   ├── state.py               AgentState, the contract every node shares
│   │   ├── workflow.py            Builds and compiles the graph
│   │   ├── edges.py               The routing decisions
│   │   ├── runtime.py             Wraps the graph for the API layer
│   │   ├── interrupts.py          Reads a pending approval from the checkpointer
│   │   └── nodes/
│   │       ├── agent_node.py      Calls the model
│   │       ├── safety_node.py     Classifies each requested call
│   │       ├── approval_node.py   Pauses for a human decision
│   │       └── tool_node.py       Runs what was approved
│   │
│   ├── llm/
│   │   ├── factory.py             Builds the chat model from config
│   │   └── prompts.py             System prompt, aware of the OS and shell
│   │
│   ├── tools/
│   │   ├── shell.py               run_shell_command
│   │   ├── filesystem.py          read_file, write_file, list_directory
│   │   ├── git.py                 git_status, git_diff, git_log
│   │   └── registry.py            The tool list the model is given
│   │
│   ├── safety/
│   │   ├── classifier.py          Decides the risk of a command
│   │   ├── rules.py               The command tables and the blocklist
│   │   └── models.py              RiskLevel, SafetyVerdict, PendingCall
│   │
│   ├── execution/
│   │   ├── runner.py              Subprocess with a timeout and output limits
│   │   └── sandbox.py             Path jail and environment scrubbing
│   │
│   └── core/
│       ├── exceptions.py          Typed errors
│       └── logging.py             Structured logging
│
├── cli/
│   ├── main.py                    Entry point and the input loop
│   ├── client.py                  Websocket client with reconnect
│   └── display.py                 Panels, streaming output, the approval prompt
│
├── tests/
│   ├── unit/                      Classifier, config, runner, health
│   └── integration/               The whole graph against a fake model
│
└── docs/
    ├── ARCHITECTURE.md            The graph, state and interrupts in depth
    └── SAFETY.md                  The threat model and the tier rules
```

---

## How the code fits together

Reading order, if you want to follow one request end to end:

1. [cli/main.py](cli/main.py) takes your text and sends it over a websocket.
2. [app/api/websocket.py](app/api/websocket.py) receives it and hands it to the runtime.
3. [app/graph/runtime.py](app/graph/runtime.py) invokes the graph with your thread id.
4. [app/graph/nodes/agent_node.py](app/graph/nodes/agent_node.py) asks the model what to do.
5. [app/graph/edges.py](app/graph/edges.py) decides where that answer goes next.
6. [app/safety/classifier.py](app/safety/classifier.py) judges the risk.
7. [app/graph/nodes/approval_node.py](app/graph/nodes/approval_node.py) pauses if needed.
8. [app/execution/runner.py](app/execution/runner.py) runs the command safely.

### The state contract

Every node receives and returns the same dictionary.

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    pending_calls: list[PendingCall]
    approved_ids: list[str]
    iterations: int
    working_dir: str
```

`add_messages` is a reducer. A node returning `{"messages": [x]}` **appends** `x` to the history.
Every other key, having no reducer, is **overwritten**. That single difference explains why the
conversation accumulates while `pending_calls` resets on each turn, and it is the thing most worth
understanding about LangGraph state.

### Why the layers are separated this way

| Layer | Depends on | Reason |
| --- | --- | --- |
| `cli/` | the wire protocol only | The client is replaceable. A web page would use the same endpoints |
| `app/api/` | `app/graph` | HTTP and websocket concerns stay out of the agent logic |
| `app/graph/` | llm, tools, safety | Orchestration only, it decides what runs and when |
| `app/tools/` | `app/execution` | Defines what the model is allowed to call |
| `app/safety/` | nothing | Pure functions, which is why it has the most tests |
| `app/execution/` | `app/config` | All the process handling lives in one place |

`app/safety/` deliberately imports nothing from the rest of the project. It is the part most worth
testing and the part that must be easiest to reason about, so it has no dependencies to reason
about.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/chat` | Send a message. Returns a reply, or an approval request |
| `POST` | `/api/approve` | Answer a pending approval |
| `GET` | `/api/sessions/{thread_id}/history` | Replay a conversation |
| `WS` | `/ws/{thread_id}` | Streaming tokens and interactive approvals |
| `GET` | `/health` | The process is alive |
| `GET` | `/ready` | The agent is configured and can serve requests |
| `GET` | `/docs` | Interactive OpenAPI documentation |

`/health` and `/ready` answer different questions. The first says the process is running. The second
says it can actually do the job, and returns `503` naming the problem when it cannot. That split is
what a load balancer needs to decide between restarting a process and withholding traffic from it.

### Websocket protocol

Send:

```json
{"type": "message", "text": "list the files here"}
{"type": "approval", "approved": true}
```

Receive:

```json
{"type": "token", "text": "partial "}
{"type": "approval_request", "calls": [{"command": "rm -rf build", "risk": "dangerous", "reason": "..."}]}
{"type": "done", "reply": "the full answer"}
{"type": "error", "message": "what went wrong"}
```

---

## Configuration

Everything is read from `.env` and validated on startup, so a bad value fails immediately rather
than halfway through a request.

| Setting | Default | What it controls |
| --- | --- | --- |
| `GROQ_API_KEY` | none | Required. Free from console.groq.com |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Any open-source model Groq serves |
| `LLM_TEMPERATURE` | `0.1` | Low, because commands should be predictable |
| `MAX_ITERATIONS` | `10` | How many steps before the agent gives up |
| `COMMAND_TIMEOUT_SECONDS` | `30` | How long a single command may run |
| `MAX_OUTPUT_CHARS` | `8000` | Output beyond this is truncated |
| `WORKING_DIR` | `.` | The directory commands run in and cannot escape |
| `LOG_LEVEL` | `INFO` | `DEBUG` shows every classification decision |

---

## Testing

```bash
pytest
ruff check .
```

86 tests, and none of them need an API key or a network connection.

That is a design decision rather than a convenience. `build_graph()` takes the model as an argument,
so the tests inject a fake one with scripted replies. Routing, interrupts, approvals, denials,
blocking and the iteration limit are all covered against that fake.

| Where | What it covers |
| --- | --- |
| `tests/unit/test_classifier.py` | Every risk tier, chains, pipelines, wrapped commands, path prefixes |
| `tests/unit/test_runner.py` | Exit codes, output that must not be truncated, secret scrubbing |
| `tests/unit/test_config.py` | Validation and defaults |
| `tests/unit/test_health.py` | Readiness reporting its failure reason |
| `tests/integration/test_graph.py` | The whole graph, including pause and resume |
| `tests/integration/test_api.py` | REST and websocket, including the approval round trip |

One lesson is baked into these tests. An early version asserted only that a run finished, which
passed even while every safe command was being silently denied. Asserting the tool actually ran is
what caught it. A test that asserts the wrong thing is worse than no test, because it buys
confidence you have not earned.

---

## What is deliberately not built

Being clear about this, because the gaps are real.

| Missing | What it would need |
| --- | --- |
| Authentication | Anyone who can reach the port can run commands |
| Durable state | `MemorySaver` holds conversations in memory, so a restart loses paused approvals |
| Container isolation | An approved command runs with your permissions, unsandboxed |
| Audit log | Beyond the structured application logs, there is no record of who approved what |
| Horizontal scaling | One process, one in-memory store |

None of these change the shape of the graph. Swapping `MemorySaver` for `SqliteSaver` is a few lines
and would make paused approvals survive a restart, which is the most useful of them.

The architecture is production-shaped. The operational parts are not built.

---

## Troubleshooting

**`uvicorn: command not found`**

The virtual environment is not active. Either activate it, or call it directly:

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app
```

**`error while attempting to bind on address ... 8000`**

An old server still holds the port.

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
taskkill /F /T /PID <the pid it shows>
```

`Get-Process python` may find nothing even when a server is running, because the Windows Store build
is named `python3.11.exe`. Use `Get-Process | Where-Object { $_.ProcessName -match 'python' }`.

**A fix does not seem to take effect**

Check what is actually running before questioning the code. `--reload` does not reliably pick up
changes to the compiled graph, and it can leave orphaned processes behind. Restart the server
manually, and confirm the `recursion_limit` on the startup line matches what you expect.

**`/ready` returns 503**

It names the reason. Usually the API key is missing from `.env`, or has stray quotes around it.

**The model writes commands for the wrong shell**

The system prompt detects the OS. If it still gets it wrong, that is prompt tuning in
[app/llm/prompts.py](app/llm/prompts.py).

---

## Stack

FastAPI, LangGraph, LangChain, Groq, Typer, Rich, structlog, pytest, ruff.

No agent framework beyond LangGraph, and the loop is written out rather than hidden, because
understanding the loop was the point.
