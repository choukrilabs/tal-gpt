# TAL-GPT

### TAL-1.0 · Task-Agent Language Protocol

[![Status](https://img.shields.io/badge/status-proposed-blue)](tal_language_specification.md)
[![Protocol](https://img.shields.io/badge/protocol-TAL--1.0-111827)](tal_language_specification.md)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/runtime-dependency--free-success)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**TAL-GPT** is a compact, deterministic coordination protocol and reference Python runtime for LLM agents, workers, tools, and orchestration systems.

TAL-1 defines a tiny wire format for **state summaries, task dispatch, non-mutating queries, results, errors, lifecycle events, cancellation, correlation, retries, idempotency, capabilities, and version negotiation**.

It is designed to sit **above** a platform's real tool/API mechanism rather than replace it.

```text
┌───────────────┐
│    LLM Agent  │
└───────┬───────┘
        │ TAL-1
        ▼
┌────────────────────┐
│ Coordinator / DAG  │
│ IDs · state · retry│
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ TAL Adapter        │
└────────┬───────────┘
         │ native API/tool
         ▼
┌────────────────────┐
│ Actual execution   │
│ shell · DB · web   │
│ code · filesystem  │
└────────┬───────────┘
         │
         ▼
   RET / ERR / EVT
```

> **Core idea:** TAL-1 describes what agents coordinate, not how the underlying platform executes it.

---

## Why TAL-GPT exists

Agent systems repeatedly communicate the same orchestration facts:

- who is acting;
- who should receive work;
- which operation should run;
- which arguments belong to it;
- what task a result belongs to;
- whether work is running, finished, failed, or cancelled;
- whether a retry is appropriate.

Natural language is flexible but verbose. Large structured envelopes can also repeat field names and wrapper syntax.

TAL-GPT compresses the **coordination layer** into a fixed positional frame while retaining explicit semantics and correlation.

The goal is not to make an LLM magically "think in fewer tokens." The practical goal is to reduce avoidable verbosity in messages that an agent runtime must exchange, parse, log, replay, and route.

---

# TAL-1 at a glance

## The frame

Every frame follows:

```text
<OP>:<SRC>><DST>:<ACT>:<PAYLOAD>:<FLAGS>:<ID>;
```

Example:

```text
CMD:c0>r1:find/vec:q='authentication',limit=5:!:a7;
```

The fields are positional:

| Field | Meaning | Example |
|---|---|---|
| `OP` | semantic class | `CMD` |
| `SRC` | sender | `c0` |
| `DST` | recipient | `r1` |
| `ACT` | operation/event | `find/vec` |
| `PAYLOAD` | compact arguments/result | `q='authentication',limit=5` |
| `FLAGS` | modifiers | `!` |
| `ID` | correlation ID | `a7` |

Frames terminate with `;`.

Reserved payload delimiters are escaped with backslash sequences.

---

# Core opcodes

| Opcode | Purpose |
|---|---|
| `THK` | Explicit state/decision summary |
| `CMD` | Delegated operation |
| `QRY` | Non-mutating request |
| `RET` | Successful result |
| `ERR` | Failure result |
| `EVT` | Lifecycle/event notification |

The reference package also retains `SYN` and `ACK` as TAL-0 compatibility/session extensions.

---

# THK: observable state, not hidden chain-of-thought

TAL-1 intentionally defines `THK` as an **explicit coordination summary**.

```text
THK:c0>self:plan:goal='audit',state='starting'::p1;
THK:c0>self:eval:state='tests_pending',decision='run_tests'::p2;
```

Recommended semantic categories are:

```text
goal
state
decision
evidence
```

TAL-1 does not expose or require access to private model chain-of-thought. A production integration should treat THK as a compact state/decision record.

---

# Correlation IDs make multi-agent work composable

Every task should have a unique identifier:

```text
CMD:c0>r1:read:path='README.md':!:a1;
```

The corresponding result uses the same ID:

```text
RET:r1>c0:read:stat='ok',out='...':$:a1;
```

Child tasks can carry a parent ID:

```text
CMD:r1>r2:read:path='spec.md',parent=a1:!:b3;
```

This gives a task graph:

```text
                 a1
              /  |  \
            b3  b4  b5
```

Because results are correlated by ID, they can arrive in any order.

---

# Lifecycle semantics

TAL-1 models task progress explicitly:

```text
new
 ↓
dispatched
 ↓
running
 ├──→ succeeded
 ├──→ failed
 └──→ cancelled
```

Terminal states do not transition again.

A worker can emit:

```text
EVT:r1>c0:state:s='running'::a1;
```

followed by:

```text
RET:r1>c0:read:stat='ok',out='...':$:a1;
```

Intermediate lifecycle events are optional when a synchronous environment does not expose them.

---

# Errors are structured

Reserved codes:

```text
INVALID
DENIED
TIMEOUT
UNAVAILABLE
CONFLICT
CANCELLED
FAILED
NOT_FOUND
UNSUPPORTED
```

Example:

```text
ERR:r1>c0:exec:code='TIMEOUT',retry=T,after=2s:$:a7;
```

This tells the coordinator:

- what failed;
- whether retry is plausible;
- an optional delay recommendation;
- which operation failed.

The protocol does **not** imply that the native platform guarantees retry safety.

---

# Cancellation

Cancellation is just another coordinated command:

```text
CMD:c0>r1:halt:id='a7'::c9;
```

Here:

```text
c9 = cancellation request ID
a7 = task being cancelled
```

The affected task can then terminate as:

```text
EVT:r1>c0:state:s='cancelled':$:a7;
```

or the cancellation request can return a conflict such as:

```text
ERR:r1>c0:halt:code='CONFLICT',cause='already_completed':$:c9;
```

Cancellation is best-effort unless the native environment guarantees stronger semantics.

---

# Idempotency and deduplication

Mutating operations can declare:

```text
idem=T
```

Example:

```text
CMD:c0>r1:file/write:path='x',data='y',idem=T:!:a7;
```

A receiver can remember terminal results for `(source,id)` and replay them instead of executing the same operation twice.

Example replay:

```text
RET:r1>c0:file/write:stat='ok',replayed=T:$:a7;
```

This is useful when a transport failure leaves the sender uncertain whether a request completed.

> Never assume an unspecified mutating operation is safe to replay.

---

# Capability discovery

Workers can expose supported actions:

```text
QRY:c0>r1:capabilities:::q1;
```

Response:

```text
RET:r1>c0:capabilities:stat='ok',out=['read','find/vec','exec']:$:q1;
```

Discovery tells the coordinator what a worker supports. It does **not** grant authorization.

---

# Native execution boundary

TAL-1 is intentionally not an execution API.

A host may translate:

```text
CMD:c0>r1:file/read:path='README.md'::a7;
```

into:

```text
filesystem.read("README.md")
```

The native result remains authoritative:

```text
native result
     ↓
TAL RET / ERR / EVT
```

This means TAL-GPT can sit above very different agent environments:

```text
Antigravity
Claude Code
Cursor
Aider
Gemini CLI
custom Python agent
local model
hosted API agent
```

without trying to redefine their native tool systems.

---

# Reference implementation

The repository keeps the Python package import path `tal_0` for compatibility, but its active protocol semantics are TAL-1.

```text
src/tal_0/
├── core.py       # frame model + parser
├── client.py     # Gemini transport + fallback
├── agents.py     # coordinator + workers + task state
├── tools.py      # explicit safe tool registry
├── benchmark.py  # token measurement helpers
└── cli.py        # runtime CLI
```

`tal_agent_runtime.py` remains the repository-level executable entry point.

---

# Repository structure

```text
tal-gpt/
├── .gitignore
├── LICENSE
├── README.md
├── AGENT_PROMPT.md
├── PROJECT_OVERVIEW.md
├── tal_language_specification.md
├── pyproject.toml
├── tal_agent_runtime.py
├── src/
│   └── tal_0/
│       ├── __init__.py
│       ├── core.py
│       ├── client.py
│       ├── agents.py
│       ├── tools.py
│       ├── benchmark.py
│       └── cli.py
├── docs/
│   └── superpowers/
│       └── plans/
│           └── 2026-09-16-tal-1.md
└── tests/
    ├── __init__.py
    ├── test_parser.py
    └── test_runtime.py
```

---

# Installation

## Requirements

- Python 3.9 or newer
- no runtime third-party dependencies

Optional development dependency:

```bash
pytest
```

## Install in editable mode

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The package name is `tal-gpt`.

---

# Run the demo

No API key is required for the deterministic demo:

```bash
python3 tal_agent_runtime.py
```

Or through the installed entry point:

```bash
tal-agent-runtime
```

The demo produces a TAL-1 trace including plan, command, lifecycle, results, evaluation, and benchmark information.

---

# Test suite

Required verification command:

```bash
python3 -m unittest discover tests/
```

Also useful:

```bash
python3 -m compileall -q src tal_agent_runtime.py
```

The reference suite covers parser correctness, escapes, correlation, lifecycle, cancellation, retries, idempotency, capabilities, tools, fallback behavior, and benchmark labels.

---

# Gemini integration

`GeminiLLMClient` is an optional transport layer using Python's standard library.

It supports:

- configurable model name;
- API key from an argument or `GEMINI_API_KEY`;
- HTTP request handling;
- exponential retry/backoff for transient errors;
- deterministic fallback when no API key is configured.

Example:

```python
from tal_0.client import GeminiLLMClient

client = GeminiLLMClient(api_key="...")
response = client.generate("Return a TAL-1 state summary")
print(response)
```

The model provider remains replaceable because the protocol core does not depend on Gemini.

---

# Safe tool boundary

The reference `ToolRegistry` explicitly registers tools.

Built-ins include:

```text
find_vector
exec_python
assert_equal
```

The Python tool uses a restricted AST evaluator with a small allowlist of operations and functions.

Arbitrary shell execution is **not** enabled automatically.

For production systems, tool adapters should add the platform's own:

- authorization checks;
- authentication;
- sandboxing;
- timeouts;
- memory/CPU limits;
- audit logging;
- cancellation semantics.

---

# Benchmarking and token economics

TAL-GPT includes a dependency-free benchmark helper.

It can compare a natural-language trace, structured trace, and TAL trace:

```python
from tal_0.benchmark import TokenBenchmark

results = TokenBenchmark.compare(natural, structured, tal)
print(TokenBenchmark.render_table(results))
```

The built-in fallback tokenizer is intentionally simple. It is useful for local relative measurements, not as a substitute for a model's real tokenizer.

For meaningful production measurements, compare the exact model/tokenizer and exact host wrapper you plan to deploy.

### Do not read this as a universal guarantee

Token savings depend on:

- model family;
- tokenizer;
- prompt packaging;
- escaping;
- payload size;
- tool wrapper overhead;
- number of messages;
- host platform protocol.

The repository therefore treats benchmark results as **measured characteristics of specific traces**, not a universal promise such as "70% fewer tokens everywhere."

---

# Coding-agent integration

TAL-1 works best as an explicit coordination layer above a coding agent's native tool system.

For Antigravity, Claude Code, Cursor, Aider, Gemini CLI, or a custom agent, a simple bootstrap is:

```text
Clone https://github.com/choukrilabs/tal-gpt

Read:
- README.md
- tal_language_specification.md
- PROJECT_OVERVIEW.md
- AGENT_PROMPT.md

Use TAL-1 for explicit coordination state, delegated tasks,
queries, results, errors, and lifecycle events.

Use native platform tools for actual execution.

Run:
python3 -m unittest discover tests/
```

The full operational prompt is provided in `AGENT_PROMPT.md`.

---

# AI chat integration

A general AI chat can be prompted to interpret or emit TAL-1.

Example request:

```text
Use TAL-1 to represent your explicit coordination messages.
Do not claim that TAL-1 exposes hidden chain-of-thought.
Use correlation IDs for every delegated task.
Use RET/ERR for terminal results.
```

Example:

```text
THK:c0>self:plan:goal='inspect_repo',state='starting'::p1;
CMD:c0>r1:read:path='README.md':!:a1;
RET:r1>c0:read:stat='ok',out='...':$:a1;
THK:c0>self:eval:state='read_complete'::p2;
RET:c0>usr:report:stat='ok',out='ready':$:f1;
```

The exact integration still depends on the host application's actual tool/function-calling interface.

---

# TAL-0 → TAL-1 migration

The vocabulary remains familiar:

```text
THK  → retained
CMD  → retained
QRY  → retained
RET  → retained
ERR  → retained
```

TAL-1 adds protocol infrastructure around those primitives:

```text
EVT              lifecycle observability
ID               correlation
parent           hierarchical task graphs
code/retry       actionable failures
halt/id          cancellation
ttl              timeout metadata
idem             replay safety declaration
capabilities     capability discovery
version          interoperability negotiation
```

The Python import package remains `tal_0` so existing imports do not need to change immediately.

---

# Conformance levels

TAL-1 defines three practical profiles.

### Level 1 · Core

```text
THK
CMD
QRY
RET
ERR
correlation IDs
strict parsing
```

### Level 2 · Operational

Adds:

```text
EVT
lifecycle
timeouts
cancellation
retry semantics
```

### Level 3 · Distributed

Adds:

```text
parent correlation
capabilities
streaming
deduplication
idempotency
version negotiation
```

A higher-level implementation should remain able to consume the Level 1 core message model.

---

# Security model

TAL-1 is not an authorization protocol.

These do **not** grant permission:

```text
CMD
!
^
```

Authorization belongs to the receiver and native tool boundary.

Receivers should validate:

- source identity;
- destination;
- action capability;
- permissions;
- payload;
- resource limits;
- correlation IDs;
- replay policy.

Never execute payload strings merely because they appear inside a TAL frame.

---

# Design invariants

The implementation preserves these principles:

```text
I1  Every frame has one opcode.
I2  Every frame has explicit source and destination.
I3  CMD/QRY operations are correlatable.
I4  RET/ERR refer to the operation they complete or fail.
I5  Terminal task states do not transition again.
I6  TAL does not replace native execution APIs.
I7  Authorization is outside TAL syntax.
I8  Unknown extensions cannot silently change core semantics.
I9  Correlation IDs distinguish concurrent operations.
I10 THK communicates summaries, not executable work.
```

---

# Roadmap

The current repository focuses on a compact, testable core. Natural extensions include:

1. streaming incremental parsing and dispatch;
2. first-class adapters for coding-agent runtimes;
3. `/git`, `/docker`, `/web`, and other domain modifiers;
4. stronger schema/version negotiation;
5. authenticated transport envelopes;
6. signed task/result messages for hostile multi-tenant environments;
7. persistent resumable task graphs;
8. conformance test vectors for independent implementations;
9. provider-specific tokenizer benchmarks;
10. distilled small-model coordinators.

---

# Why TAL-GPT is a protocol project rather than an agent framework

An agent framework owns a workflow implementation.

A protocol owns the language used to communicate workflow state.

That distinction lets TAL-1 sit above different runtimes:

```text
             TAL-1
        ┌──────┼──────┐
        ▼      ▼      ▼
    Runtime A Runtime B Runtime C
        │      │      │
     native  native  native
     tools   tools   tools
```

This is the intended interoperability layer.

---

# Repository documentation

| File | Purpose |
|---|---|
| `README.md` | Project introduction and practical usage |
| `tal_language_specification.md` | Formal TAL-1 protocol specification |
| `PROJECT_OVERVIEW.md` | Architecture and implementation boundaries |
| `AGENT_PROMPT.md` | Drop-in operational prompt for agents |
| `src/tal_0/core.py` | Frame model and parser |
| `src/tal_0/agents.py` | Coordination and lifecycle runtime |
| `src/tal_0/tools.py` | Explicit tool boundary |
| `src/tal_0/client.py` | Optional Gemini transport |
| `src/tal_0/benchmark.py` | Token/trace measurements |
| `tests/` | Conformance and runtime tests |

---

# License

MIT. See `LICENSE`.

---

# Status

**TAL-1.0 Proposed Standard**

TAL-GPT is an experimental open-source reference implementation intended to make agent coordination more compact, deterministic, inspectable, and recoverable without tying the protocol to a single model vendor or tool platform.
