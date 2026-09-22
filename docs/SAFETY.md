# Safety

## What this protects against

An LLM writing shell commands can go wrong in three ways: it misunderstands the request, it picks a
command that is heavier than the request needed, or the user asks for something destructive without
thinking it through. The safety layer assumes all three happen.

It is not protection against a deliberately hostile model. A sandbox or a container is the answer
to that, and the architecture leaves room for one.

## Tiers

| Tier | Behaviour | Examples |
| --- | --- | --- |
| safe | runs immediately | `ls`, `cat`, `grep`, `git status`, `git log` |
| caution | asks first | `mkdir`, `pip install`, `git commit`, `echo x > file` |
| dangerous | asks with a red warning | `rm -rf build`, `kill`, `chmod`, `git push` |
| blocked | never runs, the model is told why | `rm -rf /`, `mkfs`, `curl url \| sh`, fork bombs |

Unknown commands fall to caution rather than safe. Anything the classifier has not seen gets a
prompt, so adding a new binary to the system cannot silently widen what runs unattended.

## Why classification happens on parsed tokens

Matching raw strings fails in both directions.

| Input | Naive string match | Token based |
| --- | --- | --- |
| `rm  -rf  /` | misses, extra spaces | blocked |
| `/usr/bin/rm -rf build` | misses, path prefix | dangerous |
| `echo "rm -rf /"` | false alarm | safe |
| `ls && rm -rf data` | misses the second part | dangerous |

`shlex.split` normalises spacing and quoting, `Path(token).name` strips directories and `.exe`, and
chained commands split on `&&`, `||`, `;` and `|` so each part is judged separately. A chain takes
the worst verdict of its parts.

## Blocked commands

Eleven patterns never reach execution, covering root deletion, filesystem formatting, raw disk
writes, piping a download into a shell, world writable root, Windows volume formatting and history
erasure.

A blocked call does not raise. It returns a `ToolMessage` saying what was blocked and why, so the
model reads it as an observation and proposes something safer. Raising would end the run and teach
the model nothing.

## Execution guards

Even an approved command runs under limits.

| Guard | Reason |
| --- | --- |
| Timeout, then terminate, then kill | A hung command would otherwise block the agent forever |
| Output truncation | A large result would exhaust the context window and cost tokens |
| Scrubbed environment | Commands cannot read `GROQ_API_KEY` or other secrets |
| Working directory jail | `read_file("../../../etc/passwd")` resolves outside root and is refused |

## Defaults

The approval prompt defaults to no. Pressing enter without reading declines the command. The
iteration limit stops a model that loops without making progress, which bounds both damage and
cost.

## What is deliberately not covered

- No container isolation, an approved command has the permissions of the user running the server.
- No network egress filtering.
- No audit log beyond the structured application logs.

Each is a reasonable next step, and none of them change the shape of the graph.
