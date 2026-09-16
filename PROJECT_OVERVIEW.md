# TAL-GPT / TAL-1 Architecture Overview

## 1. Project identity

TAL-GPT is the reference implementation repository for **TAL-1.0, Task-Agent Language Protocol**.

TAL-1 is a compact, machine-readable coordination protocol for autonomous agents, workers, tools, and orchestration runtimes.

It defines coordination semantics while deliberately leaving actual execution to native platform APIs and tools.

## 2. Architectural boundary

```text
┌─────────────────────────────────────┐
│              LLM Agent              │
│                                     │
│  THK state summaries                │
│  task planning                      │
│  delegation intent                  │
└──────────────────┬──────────────────┘
                   │ TAL-1
                   ▼
┌─────────────────────────────────────┐
│           TAL Coordinator            │
│                                     │
│ correlation                         │
│ lifecycle                           │
│ routing                             │
│ cancellation                        │
│ retries / idempotency               │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│            TAL Adapter              │
│                                     │
│ protocol ↔ host-native tool calls  │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│       Native runtime / API          │
│                                     │
│ filesystem, shell, DB, web, code   │
│ sandbox, platform permissions       │
└──────────────────┬──────────────────┘
                   │
                   ▼
             RET / ERR / EVT
```

The native tool boundary is authoritative. TAL-1 does not create permissions or redefine execution semantics.

## 3. Reference implementation

The Python implementation keeps the stable `tal_0` module import path for compatibility while implementing TAL-1 semantics.

```text
src/tal_0/
├── core.py
├── client.py
├── agents.py
├── tools.py
├── benchmark.py
└── cli.py
```

### `core.py`

Contains:

- `Opcode`
- `TALFrame`
- `TALParseError`
- `TALParser`
- escaping/unescaping
- field splitting
- canonical flag normalization

### `agents.py`

Contains:

- `TaskState`
- `ErrorCode`
- `TaskRecord`
- `SubAgent`
- `CoordinatorAgent`

The coordinator tracks task state and correlated results, routes work to registered workers, supports cancellation, handles capability discovery, and implements idempotent replay.

### `tools.py`

Contains an explicit `ToolRegistry` and safe built-in tools. Python execution is restricted to an AST allowlist. Arbitrary shell execution is not implicitly enabled.

### `client.py`

Contains the optional Gemini transport using the Python standard library, retry/backoff logic, and a deterministic local fallback when no API key is configured.

### `benchmark.py`

Contains dependency-free token-count approximation and comparison utilities. Benchmark results are measurements of specific traces, not universal token-savings guarantees.

## 4. Frame model

```text
<OP>:<SRC>><DST>:<ACT>:<PAYLOAD>:<FLAGS>:<ID>;
```

The core semantic fields are positional:

```text
OP       semantic class
SRC      sender
DST      recipient
ACT      action or event
PAYLOAD  structured arguments/result
FLAGS    execution/delivery modifiers
ID       correlation identifier
```

Reserved payload delimiters use backslash escaping.

## 5. Execution state machine

```text
                 ┌─────────────┐
                 │     new     │
                 └──────┬──────┘
                        │
                        ▼
                 ┌─────────────┐
                 │ dispatched  │
                 └──────┬──────┘
                        │
                        ▼
                 ┌─────────────┐
                 │   running   │
                 └───┬────┬────┘
                     │    │
          ┌──────────┘    └──────────────┐
          ▼                             ▼
     ┌───────────┐                 ┌────────────┐
     │ succeeded │                 │   failed   │
     └───────────┘                 └────────────┘

                     └──────────────┐
                                    ▼
                              ┌────────────┐
                              │ cancelled  │
                              └────────────┘
```

Terminal states are immutable.

## 6. Correlation and task graphs

A root task can create child tasks:

```text
root a7
 ├── b1 research
 ├── b2 execution
 └── b3 verification
```

Child tasks use:

```text
parent=a7
```

Correlation IDs are the authority for associating results with operations, not message order.

## 7. Cancellation

Cancellation is a normal command that references the affected task:

```text
CMD:c0>r1:halt:id='a7'::c9;
```

The cancellation request is `c9`; the task being cancelled is `a7`.

The reference coordinator returns a terminal lifecycle event for the affected task or a conflict/not-found error for the cancellation request.

## 8. Retry and recovery

A native error can be translated into:

```text
ERR:r1>c0:exec:code='TIMEOUT',retry=T,after=2s:$:a7;
```

This allows the coordinator to make a retry decision without pretending the native platform guarantees that retry.

## 9. Idempotency and deduplication

Operations can declare:

```text
idem=T
```

The reference runtime stores terminal results for idempotent operations by `(source, id)` and returns a replay marker on duplicates.

This is intentionally separate from authorization and transport reliability.

## 10. Capability negotiation

A coordinator can query a worker:

```text
QRY:c0>r1:capabilities:::q1;
```

The worker reports supported protocol actions. Discovery does not grant authorization.

## 11. THK semantics

TAL-1 defines THK as an explicit, observable summary layer.

Recommended categories:

```text
goal
state
decision
evidence
```

The protocol does not claim access to private model chain-of-thought.

## 12. Provider integration

The protocol is provider-neutral:

```text
OpenAI / Gemini / Claude / local model / coding agent
                         │
                         ▼
                     TAL-1
                         │
                         ▼
                  host tool APIs
```

A provider adapter may translate native tool calls/results to and from TAL frames.

## 13. Coding-agent integration

TAL-1 is suitable as a compact coordination layer above tools in systems such as Antigravity, Claude Code, Cursor, Aider, Gemini CLI, or custom agent runtimes.

A host should keep its native tool-call mechanism. TAL-1 should represent the coordination intent and observable result around those calls.

## 14. Security model

TAL-1 itself provides syntax and protocol semantics, not authorization.

The receiver must independently validate:

- agent identity;
- destination;
- action capability;
- authorization;
- payload validity;
- resource limits;
- replay policy.

A `CMD` frame is not a permission token.

## 15. Compatibility strategy

The Python import package remains `tal_0` to avoid breaking existing consumers.

Protocol semantics are now TAL-1.0.

Legacy `SYN` and `ACK` values remain recognized as compatibility/session extensions.

## 16. Verification strategy

The repository tests cover:

- single-frame parsing;
- stream parsing;
- malformed input rejection;
- escaping and round trips;
- flags and canonicalization;
- correlation IDs;
- parent IDs;
- lifecycle transitions;
- concurrency independence;
- cancellation;
- timeout classification;
- idempotent replay;
- capability discovery;
- tool execution;
- deterministic fallback;
- package/benchmark labels.

Run:

```bash
python3 -m unittest discover tests/
python3 -m compileall -q src tal_agent_runtime.py
python3 tal_agent_runtime.py
```

## 17. Repository map

```text
tal-gpt/
├── README.md
├── AGENT_PROMPT.md
├── PROJECT_OVERVIEW.md
├── tal_language_specification.md
├── pyproject.toml
├── tal_agent_runtime.py
├── src/tal_0/
└── tests/
```

## 18. Design principle

> TAL-1 coordinates agents. Native platforms execute actions.

That boundary is the most important architectural invariant in TAL-GPT.
