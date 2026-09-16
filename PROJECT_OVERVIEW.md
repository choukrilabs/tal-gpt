# TAL-GPT Project Overview

## Objective

TAL-GPT is the reference implementation of TAL-0, a compact protocol for routing, executing, and recording multi-agent work.

## Design goals

- deterministic parsing,
- explicit routing,
- low formatting overhead,
- inspectable frame traces,
- small interfaces,
- zero runtime dependencies,
- safe default tooling,
- model transport decoupled from orchestration.

## Component model

### `core.py`

Defines `Opcode`, `TALFrame`, `TALParseError`, and `TALParser`. This is the protocol boundary and contains no agent/business logic.

### `tools.py`

Defines `ToolRegistry` and `ToolResult`. Built-ins are explicit registry entries. The Python evaluator is AST-restricted rather than an unrestricted `eval()` or shell.

### `agents.py`

Defines `SubAgent` and `CoordinatorAgent`. Workers convert commands into tool calls. The coordinator builds a deterministic trace with planning, delegation, result collection, and verification.

### `client.py`

Defines `GeminiLLMClient`. It uses standard-library HTTP primitives and exposes a small `generate()` interface. Missing credentials produce an explicit deterministic fallback. The client targets Gemini's `generateContent` REST pattern for the configured model.

### `benchmark.py`

Counts tokens using a deterministic approximation so the project stays dependency-free. The module is intentionally structured so an exact tokenizer can be substituted later.

### `tal_agent_runtime.py`

The root CLI, suitable for a direct checkout. It prints serialized frames and a benchmark summary.

## Execution lifecycle

```text
User objective
    ↓
Coordinator THK plan
    ↓
CMD to worker
    ↓
Worker resolves action
    ↓
ToolRegistry execution
    ↓
RET / ERR
    ↓
Coordinator THK eval
    ↓
Final RET / ERR
```

## Error lifecycle

Failures are data, not control-flow leaks:

```text
tool failure
   ↓
ToolResult(status='error')
   ↓
SubAgent
   ↓
ERR:<worker>><coordinator>:...
   ↓
Coordinator retry/recovery policy
```

A production coordinator can add bounded retries, alternate workers, circuit breakers, deadlines, and audit persistence without changing the base frame model.

## Extensibility

Future additions should be implemented behind clear interfaces rather than by expanding the frame grammar unnecessarily. Useful directions include:

- streaming parser/dispatcher,
- `/git`, `/docker`, and domain-specific action adapters,
- persistent trace storage,
- exact tokenizer benchmark adapters,
- model adapters for other LLM providers,
- distributed transports that retain the same `TALFrame` contract.

## Production limitations

TAL-GPT 1.0 is a reference runtime, not a complete hostile-environment sandbox. The included Python tool is intentionally restricted, but production deployments should isolate arbitrary user code in an OS/container sandbox with resource limits. Network, filesystem, process, and credential access should be granted explicitly per tool.

Likewise, the frame protocol is not cryptographic authentication. Message integrity, identity, authorization, and transport encryption belong to the deployment layer.
