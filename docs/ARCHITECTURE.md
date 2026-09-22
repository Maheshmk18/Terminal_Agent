# Architecture

## The idea

You type a request in plain English. The agent decides which command answers it, classifies how
risky that command is, asks you before running anything destructive, runs it, reads the output, and
decides what to do next. It repeats until the task is done.

## Request flow

```
CLI client
    │  websocket frame {"type": "message", "text": "..."}
    ▼
FastAPI  /ws/{thread_id}
    │
    ▼
AgentRuntime.stream()
    │
    ▼
LangGraph  ──▶ agent ──▶ safety ──▶ approval ──▶ tools ──┐
                 ▲                                       │
                 └───────────────────────────────────────┘
```

## The graph

Four nodes and two conditional edges.

| Node | Job |
| --- | --- |
| `agent` | Calls the LLM with the tool schemas bound, returns either text or tool calls |
| `safety` | Classifies every tool call as safe, caution, dangerous or blocked |
| `approval` | Calls `interrupt()` to pause and wait for a human decision |
| `tools` | Runs approved calls, returns a `ToolMessage` for each |

Routing:

- After `agent`: tool calls present go to `safety`, otherwise the graph ends.
- After `safety`: anything needing approval goes to `approval`, otherwise straight to `tools`.
- `tools` always loops back to `agent` so the model can read the output.

## State

Every node receives and returns the same dictionary.

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    pending_calls: list[PendingCall]
    approved_ids: list[str]
    iterations: int
    working_dir: str
```

`add_messages` is a reducer. A node returning `{"messages": [x]}` appends `x` to the history.
Keys without a reducer are overwritten instead. That difference is the main thing to understand
about LangGraph state.

## How pausing works

`approval_node` calls `interrupt(request)`. LangGraph writes the full graph state to the
checkpointer and returns control to the caller with the request payload. Nothing has run yet.

When you answer, the caller invokes the graph again with `Command(resume=decision)`. LangGraph
loads the saved state and re-runs the approval node from the top, and this time `interrupt()`
returns your decision instead of pausing. Because the node re-runs, it is written to be safe to
execute twice.

The paused state survives a server restart if the checkpointer is backed by a database rather than
memory.

## Threads

`thread_id` is the conversation key. The checkpointer stores state under it, so sending the same
thread id continues the same conversation, including resuming one that is paused waiting for
approval. A new thread id starts fresh.

## Safety

Classification happens on parsed tokens, never on raw strings.

| Tier | Behaviour | Example |
| --- | --- | --- |
| safe | runs immediately | `ls`, `cat`, `git status` |
| caution | asks first | `mkdir`, `pip install`, `git commit` |
| dangerous | asks with a red warning | `rm -rf build`, `chmod 777`, `git push` |
| blocked | never runs | `rm -rf /`, `mkfs`, fork bombs |

Three details that matter:

- `shlex.split` means `rm  -rf  /` with extra spaces parses the same as `rm -rf /`.
- `/usr/bin/rm` reduces to `rm`, so an absolute path cannot hide a dangerous command.
- A chain such as `ls && rm -rf data` splits into parts and takes the worst verdict.

Blocked and denied calls return a `ToolMessage` explaining what happened rather than raising. The
model reads that as an observation and adapts instead of the run crashing.

## Execution

`run_command` wraps `asyncio.create_subprocess_exec` with three guards:

- A timeout, then `terminate`, then `kill` for processes that ignore the first signal.
- Output truncation so a large result cannot exhaust the context window.
- A scrubbed environment, so API keys are not visible to the commands being run.

File tools resolve paths and verify the result is still inside the working directory, which stops
`../../etc/passwd` traversal.

## Layers

| Layer | Depends on | Knows about |
| --- | --- | --- |
| `cli/` | websockets, rich | the wire protocol only |
| `app/api/` | `app/graph` | HTTP and websocket concerns |
| `app/graph/` | `app/llm`, `app/tools`, `app/safety` | orchestration |
| `app/tools/` | `app/execution` | what the model can call |
| `app/safety/` | nothing | risk rules, pure functions |
| `app/execution/` | `app/config` | running processes safely |

`app/safety/` has no dependencies on anything else in the project, which is why it is the easiest
part to test and the part with the most tests.

## Testing

The graph is built with an injected model, so the whole system runs against a fake LLM with
scripted responses. No API key and no network are needed to test routing, interrupts, approvals,
denials, blocking or the iteration limit.
