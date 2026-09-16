# TAL-1 Agent Operational Prompt

Use TAL-1 as the explicit coordination protocol for this agent workflow.

## Core rule

TAL-1 is a coordination language. It is **not** the underlying tool API, shell, database protocol, RPC layer, or operating-system interface.

Do not claim that emitting a TAL frame executes an operation. Translate TAL into the host platform's real tool call, execute that call through the platform's authorization boundary, then translate the authoritative result back into TAL.

## Wire format

```text
<OP>:<SRC>><DST>:<ACT>:<PAYLOAD>:<FLAGS>:<ID>;
```

Use these core opcodes:

```text
THK  state/decision summary
CMD  delegated operation
QRY  non-mutating request
RET  successful result
ERR  failure result
EVT  lifecycle/event notification
```

`SYN` and `ACK` may appear only as compatibility/session extensions.

## Correlation

Every `CMD` and `QRY` should carry a unique correlation ID.

`RET`, `ERR`, and terminal lifecycle events must preserve the corresponding task ID.

Use `parent=<id>` in delegated task payloads when a child task belongs to a parent operation.

Never infer task ordering from arrival order. Correlation IDs are authoritative for concurrent work.

## Lifecycle

Use the task state model:

```text
new → dispatched → running → succeeded
                         ├→ failed
                         └→ cancelled
```

Terminal states do not transition again.

Emit `EVT` state frames when the host environment makes intermediate lifecycle observable.

## THK

Use `THK` for concise external state/decision summaries such as:

```text
THK:c0>self:plan:goal='audit',state='starting'::p1;
THK:c0>self:eval:state='tests_pending',decision='run_tests'::p2;
```

TAL-1 does not require exposing private internal chain-of-thought. Do not claim that THK provides access to hidden reasoning.

## Errors

Use these reserved error codes:

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

Include `retry=T/F` when retryability is known. Use `after=...` for a recommended retry delay.

## Cancellation

Cancellation is a command:

```text
CMD:c0>r1:halt:id='a7'::c9;
```

The cancellation request ID is `c9`; the affected task ID is `a7`.

## Idempotency and replay

For mutating operations, declare `idem=T` only when repeated execution is safe.

A receiver may replay a stored result for a duplicate `(source, id)` pair rather than executing the operation again.

Never assume an unspecified operation is idempotent.

## Capability discovery

Use:

```text
QRY:c0>r1:capabilities:::q1;
```

Capability discovery does not grant permission.

## Native tool boundary

The host platform remains authoritative for:

- authorization;
- filesystem access;
- shell execution;
- database writes;
- network requests;
- external APIs;
- sandbox policy;
- resource limits.

TAL payload text is data unless the receiver explicitly maps it to an authorized tool operation.

## Parsing discipline

Escape reserved delimiters inside payload values:

```text
\; \ , \= \: \\ \'
```

Canonical booleans are `T` and `F`; canonical null is `N`.

Canonical flags are emitted in `!?^$` order.

## Agent workflow

1. Establish participants and protocol version when interoperability matters.
2. Create a correlation ID for the root operation.
3. Emit a concise `THK` plan summary.
4. Dispatch `CMD` or `QRY` frames.
5. Observe lifecycle events where supported.
6. Execute through native tools.
7. Emit `RET` or `ERR` using the same correlation ID.
8. Update `THK` state after meaningful evidence.
9. Dispatch dependent child tasks with `parent=<id>`.
10. Stop only when the root task reaches a terminal state.

## Coding-agent bootstrap

When joining an existing TAL-GPT repository, read:

```text
README.md
tal_language_specification.md
PROJECT_OVERVIEW.md
AGENT_PROMPT.md
```

Run the test suite before making protocol changes:

```bash
python3 -m unittest discover tests/
```

Protocol changes must update the specification and conformance tests together.
