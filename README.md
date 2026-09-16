# TAL-GPT

Ultra-dense multi-agent orchestration protocol and token-efficient agent communication runtime.

This repository contains the reference Python implementation of TAL-GPT, a compact positional-frame protocol for coordinating LLM agents, tools, queries, returns, errors, and execution state.

## Status

Version: 1.0.0

Python: 3.9+

Runtime dependencies: Python standard library only

Tests: 13 passing

The benchmark claims in this repository are measured characteristics of specific example traces and tokenization methods, not universal guarantees.

## What TAL-GPT is

TAL-GPT is a protocol layer for agentic systems. It compresses repetitive orchestration language into deterministic frames such as `THK`, `CMD`, `QRY`, `RET`, and `ERR`.

The intended architecture is:

```text
User Objective
      |
      v
 Coordinator
      |
   TAL-GPT
      |
 +----+----------------+
 |    |                |
 v    v                v
Research  Execution   Verification
 Agent      Agent        Agent
 |          |            |
 +----------+------------+
            |
         Tools/APIs
```

TAL-GPT does not replace an LLM's private hidden reasoning, nor does a prompt expose hidden chain-of-thought. It provides an explicit, structured communication grammar that can be emitted by agents, parsed by runtimes, logged, inspected, benchmarked, and transported between agent components.

## Why it exists

Long-running agent workflows repeatedly spend tokens describing orchestration state:

- who is acting
- who should receive a task
- what operation should happen
- what payload is being passed
- whether a request is dry-run, urgent, atomic, or final
- whether a sub-agent returned a result or an error

Natural-language orchestration is expressive but verbose. Large JSON structures are machine-readable but can repeat field names, delimiters, indentation, and wrapper objects.

TAL-GPT attacks that overhead with fixed positional frames and a small action lexicon.

## Core frame

A TAL-GPT frame has this shape:

```text
HEADER:SOURCE>TARGET:ACTION/MOD:PAYLOAD:FLAGS;
```

Example:

```text
CMD:c0>r1:find/vec:q='auth_cve',limit=1:!;
```

The slots are positional:

| Slot | Meaning | Example |
| --- | --- | --- |
| Header | protocol opcode | `CMD` |
| Routing | source and target | `c0>r1` |
| Action | verb and optional modifier | `find/vec` |
| Payload | compact arguments | `q='auth_cve',limit=1` |
| Flags | lifecycle/operational markers | `!` |

Frames terminate with `;`.

## Standard opcodes

| Opcode | Purpose |
| --- | --- |
| `THK` | Explicit reasoning-state record such as plan, hypothesis, deduction, evaluation, or critique |
| `CMD` | Imperative task dispatched to an executor |
| `QRY` | Non-mutating query against memory, vector indexes, databases, or state |
| `RET` | Successful return/result frame |
| `ERR` | Structured failure frame |
| `EVT` | Asynchronous event/broadcast |
| `SYN` | Session synchronization/initialization |
| `ACK` | Acknowledgement/confirmation |

## THK phases

The reference runtime recognizes the following explicit reasoning-state labels:

```text
plan  hyp  dedu  eval  crit
```

Examples:

```text
THK:c0:plan:goal='audit_cve',sub=[r1 e1];
THK:c0:hyp:cause='token_leak',vuln='oauth_jwt';
THK:c0:dedu:root='jwt_expiry_bypass';
THK:c0:eval:stat='passed',safe=T;
THK:c0:crit:retry=2,fail='timeout';
```

In a real production model integration, these should be treated as explicit agent state or reasoning summaries rather than assumptions about inaccessible hidden CoT.

## Action lexicon

The reference implementation uses compact verbs:

```text
read writ exec eval call find pipe sync halt tok
```

and modifiers such as:

```text
/py /sh /sql /vec /raw /mem /api
```

These are ordinary protocol symbols. Their tokenization depends on the tokenizer/model, so the project should benchmark the exact model that will be deployed instead of assuming every symbol is a single BPE token everywhere.

## Flags

The protocol reserves compact lifecycle/constraint markers:

| Flag | Meaning |
| --- | --- |
| `!` | atomic/strict |
| `?` | dry-run/query-only intent |
| `^` | urgent |
| `$` | final |

Example:

```text
CMD:c0>e1:exec/py:code='min(100,50)':!;
```

## Reference runtime

The runtime is split into focused modules:

```text
src/tal_0/
├── core.py       # TALFrame, enums, parser, serializer
├── client.py     # Gemini HTTP client and deterministic fallback
├── agents.py     # CoordinatorAgent and SubAgent
├── tools.py      # ToolRegistry and safe built-in tools
├── benchmark.py  # token/trace comparison helpers
└── cli.py        # command-line runner
```

`tal_agent_runtime.py` is the repository-level executable entry point.

## Parser

`TALFrame` is the canonical representation. `TALParser` is intentionally strict:

- validates opcodes
- validates frame termination
- validates routing syntax
- validates action/modifier syntax
- validates payload syntax boundaries
- rejects malformed streams rather than silently coercing them
- supports single-frame and multi-frame stream parsing
- supports frame to string to frame round trips

Example:

```python
from tal_0 import TALFrame, TALParser

frame = TALFrame(
    header="CMD",
    source="c0",
    target="r1",
    action="find",
    modifier="vec",
    payload={"q": "auth_cve", "limit": 1},
    flags=["!"],
)

wire = TALParser.serialize(frame)
parsed = TALParser.parse(wire)
assert parsed == frame
```

## Agent orchestration

The reference flow is:

```text
Objective
   |
   v
THK:plan
   |
   +--> CMD --> SubAgent
   |              |
   |              +--> ToolRegistry
   |              |
   |              +--> RET / ERR
   |
   v
THK:dedu
   |
   +--> next CMD/QRY
   |
   v
THK:eval
   |
   v
RET:c0>usr:...$;
```

A `CoordinatorAgent` owns the workflow state. `SubAgent` instances execute registered tool bindings and return structured frames.

## Tool registry and safety boundary

The built-in tool registry deliberately keeps the demo safe and dependency-free.

It provides:

- restricted Python expression evaluation
- in-memory vector-style lookup for demonstration
- assertion/testing helpers

Arbitrary shell execution is not silently enabled. Production integrations should explicitly register their own capability boundaries, authorization checks, timeouts, resource limits, and audit logging.

## Gemini integration

`GeminiLLMClient` is an optional transport layer. It uses Python's standard-library HTTP client and supports retry/backoff plus deterministic fallback when no API key is configured.

The client is isolated from the protocol core so TAL-GPT can also be used with other providers or local models.

Conceptually:

```text
Provider adapter
      |
      v
 LLM response
      |
      v
TAL-GPT parser
      |
      v
Coordinator / tools
```

## Installation

From a clone:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Development tooling is intentionally minimal. Pytest is optional.

## Run the demo

Without any API key:

```bash
python3 tal_agent_runtime.py
```

The reference runner uses deterministic local behavior so the architecture can be exercised without an external model.

## Tests

Run the project's required test command:

```bash
python3 -m unittest discover tests/
```

Expected result:

```text
Ran 13 tests

OK
```

You can also use:

```bash
python3 -m compileall -q src tal_agent_runtime.py
```

## Example complete trace

A compact multi-agent interaction can look like:

```text
THK:c0:plan:goal='cve',sub=[r1 e1];
CMD:c0>r1:find/vec:q='auth_cve',limit=1:!;
RET:r1>c0:find/vec:hits=['CVE-2026-9041'];
THK:c0:dedu:fix='min(exp,now)';
CMD:c0>e1:exec/py:code='min(100,50)';
RET:e1>c0:exec/py:out=50,stat=ok;
THK:c0:eval:audit='passed';
RET:c0>usr:tok:ans='verified'$;
```

This is a protocol example, not evidence that a particular CVE or vulnerability exists in a real target. Production systems must source security findings from authoritative data and verify them independently.

## Using TAL-GPT with coding agents

TAL-GPT can sit above a coding agent's native tool system.

For agents such as Antigravity, Claude Code, Cursor, Aider, or Gemini CLI, place `AGENT_PROMPT.md` in the project's instruction/rules layer and point the agent at the protocol specification.

A generic bootstrap prompt is:

```text
Clone https://github.com/choukrilabs/tal-gpt

Read:
- README.md
- tal_language_specification.md
- AGENT_PROMPT.md
- PROJECT_OVERVIEW.md

Use TAL-GPT as the compact communication protocol for agent state,
task dispatch, queries, results, and errors.

Use THK for explicit reasoning state summaries.
Use CMD for delegated work.
Use QRY for non-mutating requests.
Use RET for successful results.
Use ERR for failures.

Keep native platform tool calls intact. TAL-GPT is the coordination
layer, not a replacement for the platform's underlying tool API.
Run the tests before completing work.
```

## Using TAL-GPT with AI chat

A general chat model can interpret and emit TAL-GPT when prompted. The most reliable approach is to use TAL-GPT for explicit protocol messages, not as a claim that you can inspect or control hidden model reasoning.

Example:

```text
TASK → audit parser

THK:c0:plan:goal='audit_parser';
CMD:c0>e1:read/raw:path='src/tal_0/core.py';
RET:e1>c0:read/raw:stat=ok;
THK:c0:eval:stat='ready';
RET:c0>usr:tok:ans='parser audit complete'$;
```

## Benchmarking

The benchmark module compares trace sizes and reports measurements such as:

```text
baseline tokens
TAL-GPT tokens
absolute reduction
percentage reduction
```

Do not treat a single toy trace as a universal efficiency guarantee. Results vary with:

- model family
- tokenizer
- prompt packaging
- escaping rules
- payload contents
- tool-call wrapper imposed by the host platform
- number and size of messages

The original protocol concept targets substantial reduction in orchestration overhead, but the repository's benchmark is the authority for measured examples.

## Design principles

### Determinism

Identical frame strings should parse to the same semantic representation.

### Compactness

Use short positional symbols where the meaning is unambiguous.

### Explicit boundaries

Parsing and execution are separate layers.

### Capability isolation

Tools are explicitly registered rather than inferred from arbitrary text.

### Provider neutrality

The core protocol does not depend on a particular LLM vendor.

### Observable orchestration

Explicit frames make agent coordination easier to log, replay, inspect, and test.

## Production considerations

TAL-GPT is a protocol foundation, not a complete secure agent operating system. A production deployment should add:

- authentication and agent identity
- authorization for tool capabilities
- signed or authenticated transport where required
- replay protection for state-changing commands
- unique request/correlation identifiers
- deadlines and cancellation
- structured audit logs
- resource quotas
- sandboxing appropriate to the tools being exposed
- schema/version negotiation
- protocol compatibility testing
- tokenizer/model-specific benchmarks
- observability around tool latency and failures

A future version may add these without changing the compact core grammar.

## Versioning

The language specification and runtime should be versioned together when syntax or semantics change.

Recommended compatibility policy:

```text
MAJOR = incompatible protocol grammar/semantic changes
MINOR = backwards-compatible protocol additions
PATCH = implementation fixes and documentation corrections
```

## Repository map

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

## License

TAL-GPT is released under the MIT License. See `LICENSE`.

## Roadmap

Planned directions include:

1. Streaming incremental parser and dispatcher.
2. Provider adapters for major coding-agent runtimes.
3. Domain-specific modifiers such as `/git` and `/docker`.
4. Persistent agent-session correlation and resumability.
5. Stronger schema/version negotiation.
6. Model-specific tokenizer benchmarks.
7. Distilled small-model coordinators.
8. Conformance test vectors for independent implementations.

## Contributing

Keep protocol changes small and testable. Add or update conformance tests for grammar changes, update the formal specification, and document compatibility impact.

For runtime changes, keep tool capabilities explicit, avoid hidden side effects, and preserve deterministic behavior where possible.

## Authoring a new adapter

An adapter should translate between TAL-GPT frames and a host agent's native messages/tools:

```text
TAL-GPT CMD
    |
    v
 adapter.decode()
    |
    v
 native tool call
    |
    v
 adapter.encode()
    |
    v
TAL-GPT RET / ERR
```

The adapter should not duplicate the core parser or redefine protocol semantics.

## Summary

TAL-GPT is deliberately small:

```text
compact grammar
      +
strict parser
      +
agent coordinator
      +
explicit tools
      +
provider adapters
      =
portable agent communication layer
```

It is designed to be understandable by humans, compact for LLM-generated traces, and practical to test and evolve as an open-source protocol.
