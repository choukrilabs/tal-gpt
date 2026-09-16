# TAL-1.0

## Task-Agent Language Protocol

### Operational Coordination Profile

**Status:** Proposed
**Version:** TAL-1.0
**Purpose:** Compact machine-readable coordination between agents, workers, tools, and orchestration runtimes.

---

## 1. Scope

TAL-1 defines a compact protocol for:

- agent state summaries;
- task dispatch;
- delegated work;
- non-mutating queries;
- successful results;
- failures;
- lifecycle events;
- cancellation;
- correlation and routing.

TAL-1 is a **coordination protocol**, not a replacement for an underlying tool, API, RPC, operating-system interface, or platform-native execution mechanism.

A TAL runtime MAY translate a TAL command into any native platform operation.

```text
TAL frame
    ↓
TAL adapter
    ↓
native platform API/tool
    ↓
native result
    ↓
TAL RET or ERR
```

The native API remains authoritative for actual execution semantics.

---

# 2. Design Goals

TAL-1 has six primary goals:

1. **Compactness** — common coordination messages should remain short.
2. **Determinism** — messages should have unambiguous parsing and routing.
3. **Observability** — an external observer should reconstruct task state.
4. **Composability** — multiple agents and delegated tasks should operate concurrently.
5. **Recoverability** — failures, cancellation, retries, and timeouts should be machine-actionable.
6. **Tool neutrality** — TAL must not depend on any particular tool platform.

---

# 3. Core Message Model

Every TAL-1 frame has this structure:

```text
<OP>:<SRC>><DST>:<ACT>:<PAYLOAD>:<FLAGS>:<ID>;
```

The payload MAY be empty.

Minimal form:

```text
OP:SRC>DST:ACT::FLAGS:ID;
```

Example:

```text
CMD:c0>r1:find/vec:q='auth':!:a7;
```

A frame ends with exactly one `;`.

Frames MUST escape reserved delimiters inside payload values. The reference parser uses the escape sequences defined in Section 18.

---

# 4. Fields

## 4.1 OP — Opcode

Core opcodes:

```text
THK   reasoning/state summary
CMD   delegated operation
QRY   non-mutating request
RET   successful result
ERR   failure result
EVT   lifecycle/event notification
```

The reference package also retains `SYN` and `ACK` as compatibility/session extensions inherited from TAL-0. They are not part of the TAL-1 core profile.

Future TAL versions MAY introduce additional opcodes.

Unknown opcodes MUST NOT be silently reinterpreted.

## 4.2 SRC — Source

`SRC` identifies the sender.

Examples:

```text
c0
r1
worker-7
self
system
```

A source identifier MUST be stable for the lifetime of the active coordination session.

## 4.3 DST — Destination

`DST` identifies the intended recipient.

Examples:

```text
self
c0
r1
broadcast
```

`self` means the originating agent or runtime itself.

`broadcast` means all participants authorized for the current coordination scope.

Implementations MAY restrict broadcast.

## 4.4 ACT — Action

`ACT` identifies the operation or event.

Examples:

```text
plan
delegate
find/vec
read
write
exec
halt
state
```

Action names are extensible.

Action namespaces SHOULD use `/`:

```text
find/vec
find/text
file/read
file/write
agent/delegate
```

## 4.5 PAYLOAD

The payload carries structured key/value data.

Canonical representation:

```text
key=value
```

Multiple fields are comma-separated:

```text
q='authentication',limit=10,scope='repo'
```

Values MAY be strings, numbers, booleans, lists, maps, or null.

Canonical booleans:

```text
T
F
```

Canonical null:

```text
N
```

Strings SHOULD use single quotes.

Example:

```text
q='hello world',limit=5,recursive=T
```

---

# 5. Flags

Flags express execution or delivery modifiers.

Core flags:

```text
!   strict/atomic intent
?   dry-run / non-mutating intent
^   high priority
```

The reference runtime also accepts `$` as a terminal/final-result marker for compatibility with TAL-0 examples.

Example:

```text
CMD:c0>r1:file/write:path='x',data='y':!?^:a7;
```

## 5.1 Flag Semantics

### `!` — Strict

Requests atomic or strict execution semantics.

The underlying tool MAY reject the operation when strict semantics cannot be guaranteed.

`!` MUST NOT be interpreted merely as "important."

### `?` — Dry Run

Requests evaluation without mutation.

For a `QRY`, `?` is redundant but MAY be used for clarity.

### `^` — Priority

Marks the operation as high priority within the TAL scheduler.

Priority remains an orchestration concern and MUST NOT imply privileged execution.

### `$` — Terminal Result Marker

Marks a terminal frame in the reference runtime. `$` is an implementation compatibility extension rather than a TAL-1 core flag.

---

# 6. Correlation IDs

The final field is the correlation identifier:

```text
<ID>
```

Example:

```text
CMD:c0>r1:find/vec:q='auth':!:a7;
RET:r1>c0:find/vec:out=[...],stat='ok':$:a7;
```

## 6.1 Requirements

Every `CMD` and `QRY` SHOULD have an ID.

Every `RET`, `ERR`, cancellation response, and terminal lifecycle event associated with that operation MUST carry the same ID.

IDs MUST be unique within the active coordination scope.

IDs SHOULD be short, opaque, and implementation-neutral.

Recommended alphabet:

```text
[a-z0-9]
```

Examples:

```text
a7
f9k2
p1
```

## 6.2 Parent Correlation

Delegated tasks MAY contain a parent ID:

```text
parent=a7
```

Example:

```text
CMD:r1>r2:find/text:q='spec',parent=a7:!:b3;
```

This permits hierarchical task graphs:

```text
a7
 ├── b3
 ├── b4
 └── b5
```

---

# 7. THK — State and Reasoning Summary

`THK` communicates a compact, externally observable summary of the agent's state or decision.

Canonical form:

```text
THK:<SRC>><DST>:<ACT>:<PAYLOAD>:<FLAGS>:<ID>;
```

Examples:

```text
THK:c0>self:plan:goal='audit',state='starting'::p1;
THK:c0>self:eval:state='tests_pending',evidence='source_read'::p2;
THK:r1>c0:decision:action='retry',cause='timeout'::p3;
```

## 7.1 THK Is Not an Execution Command

`THK` records state or decision summaries.

It MUST NOT itself execute an external operation.

## 7.2 Allowed THK Content

TAL-1 standardizes four semantic categories:

```text
goal
state
decision
evidence
```

TAL-1 does not define a requirement to expose private internal reasoning. Implementations SHOULD use THK as explicit state/decision summaries rather than a promise of hidden chain-of-thought exposure.

---

# 8. CMD — Delegated Work

`CMD` requests execution of an operation by another agent, worker, or execution identity.

Example:

```text
CMD:c0>r1:find/vec:q='authentication',limit=5:!:a7;
```

The recipient:

1. accepts or rejects the task;
2. MAY emit lifecycle `EVT` frames;
3. performs the native operation;
4. emits `RET` or `ERR`.

A `CMD` MUST NOT be assumed successful merely because it was transmitted.

---

# 9. QRY — Non-Mutating Request

`QRY` requests information without modifying external state.

Example:

```text
QRY:c0>r1:status:target='job-7'::q3;
```

A `QRY` MUST NOT intentionally mutate external state.

The distinction is semantic, not merely syntactic.

---

# 10. RET — Successful Result

`RET` reports successful completion.

Example:

```text
RET:r1>c0:find/vec:out=[{id='d1',score=0.93}],stat='ok':$:a7;
```

Required semantics:

```text
stat='ok'
```

A `RET` MAY additionally contain `out`, `meta`, `usage`, or `warnings`.

A `RET` with `stat='ok'` represents successful protocol-level completion. It does not guarantee semantic correctness of the underlying result.

---

# 11. ERR — Failure Result

`ERR` reports unsuccessful execution.

Canonical fields:

```text
code
retry
cause
msg
```

Example:

```text
ERR:r1>c0:find/vec:code='TIMEOUT',retry=T,cause='index_unavailable':$:a7;
```

## 11.1 Standard Error Codes

TAL-1 reserves:

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

Implementations MAY define additional codes using namespaced identifiers.

Example:

```text
vendor/acme_RATE_LIMIT
```

## 11.2 Retry

`retry` indicates whether the same logical operation MAY be attempted again.

Canonical values:

```text
T
F
```

Optional delay:

```text
after=2s
```

Example:

```text
ERR:r1>c0:exec:code='TIMEOUT',retry=T,after=2s:$:a7;
```

---

# 12. EVT — Lifecycle Events

`EVT` communicates task state transitions and other asynchronous events.

Example:

```text
EVT:r1>c0:state:s='running'::a7;
```

Standard lifecycle states:

```text
new
dispatched
running
succeeded
failed
cancelled
```

State progression:

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

Terminal states are:

```text
succeeded
failed
cancelled
```

A task MUST NOT transition out of a terminal state.

---

# 13. Cancellation

Cancellation is represented as a command.

Example:

```text
CMD:c0>r1:halt:id='a7'::c9;
```

The cancellation request itself has correlation ID `c9`.

The task being cancelled is identified by:

```text
id='a7'
```

The target task then reports:

```text
EVT:r1>c0:state:s='cancelled':$:a7;
```

or, when already terminal:

```text
ERR:r1>c0:halt:code='CONFLICT',cause='already_completed':$:c9;
```

Cancellation is best-effort unless the underlying execution environment guarantees stronger semantics.

---

# 14. State Machine

A compliant TAL-1 coordinator SHOULD maintain task state equivalent to:

```text
Task {
    id
    parent
    src
    dst
    action
    state
    created
    started
    completed
}
```

Valid transitions:

```text
new → dispatched
dispatched → running
running → succeeded
running → failed
running → cancelled
```

An implementation MAY collapse states when its execution model is synchronous.

For example:

```text
CMD → RET
```

is valid shorthand for a task whose intermediate lifecycle is not observable.

---

# 15. Concurrency

TAL-1 MUST support concurrent tasks through correlation IDs.

Example:

```text
CMD:c0>r1:read:path='a':!:a1;
CMD:c0>r1:read:path='b':!:a2;
CMD:c0>r1:read:path='c':!:a3;
```

Results MAY arrive in any order:

```text
RET:r1>c0:read:out='B':$:a2;
RET:r1>c0:read:out='A':$:a1;
RET:r1>c0:read:out='C':$:a3;
```

Order MUST NOT be inferred from message arrival.

---

# 16. Timeouts

A command MAY specify a timeout:

```text
ttl=30s
```

Example:

```text
CMD:c0>r1:exec:job='build',ttl=30s:!:a7;
```

After expiry, the coordinator MAY cancel the operation or report:

```text
ERR:r1>c0:exec:code='TIMEOUT',retry=T:$:a7;
```

A timeout does not prove that the native operation stopped unless the underlying platform confirms cancellation.

---

# 17. Streaming and Partial Results

An implementation MAY emit non-terminal results using:

```text
stat='partial'
```

Example:

```text
RET:r1>c0:find/vec:stat='partial',out=[...],seq=1::a7;
RET:r1>c0:find/vec:stat='partial',out=[...],seq=2::a7;
RET:r1>c0:find/vec:stat='ok',seq=3,out=[...]:$:a7;
```

Sequence numbers SHOULD begin at `1`.

An implementation MUST NOT infer successful completion from a partial result.

---

# 18. Payload Encoding

TAL-1 reserves these escaping rules:

```text
\;   literal semicolon
\,   literal comma
\=   literal equals sign
\:   literal colon
\\   literal backslash
\'   literal quote
```

A parser MUST process escapes before semantic interpretation.

Strings containing whitespace SHOULD remain quoted.

Example:

```text
msg='build failed\: missing file'
```

The reference implementation escapes reserved delimiters at the frame serializer boundary and preserves payload data after a parse/serialize round trip.

---

# 19. Canonicalization

Two semantically equivalent TAL messages SHOULD serialize identically where practical.

Canonicalization rules:

1. opcode is uppercase;
2. identifiers are case-sensitive;
3. standard booleans are `T` and `F`;
4. standard null is `N`;
5. keys use lowercase ASCII;
6. fields are separated by commas;
7. flags are emitted in canonical order `!?^$`;
8. frames terminate in `;`.

Example canonical frame:

```text
CMD:c0>r1:file/read:path='README.md':!:a7;
```

---

# 20. Native Tool Boundary

TAL-1 MUST NOT redefine native platform APIs.

For example, if a platform exposes:

```text
filesystem.read(path)
```

a TAL adapter MAY translate:

```text
CMD:c0>r1:file/read:path='README.md'::a7;
```

into that native call.

The native return value remains authoritative:

```text
filesystem.read(...)
        ↓
   native result
        ↓
RET:r1>c0:file/read:out='...':$:a7;
```

TAL fields MUST NOT imply capabilities that the underlying tool does not possess.

---

# 21. Security

TAL-1 is not an authorization system.

The presence of `CMD`, `!`, or `^` does not grant permission.

Authorization MUST occur at the receiving runtime or native platform boundary.

Receivers MUST validate:

- source identity;
- destination;
- action;
- payload;
- permissions;
- resource limits;
- correlation ID;
- replay policy.

Untrusted payloads MUST NOT be interpreted as executable instructions merely because they occur inside a TAL frame.

---

# 22. Idempotency

Mutating commands SHOULD declare whether repeated execution is safe.

Optional field:

```text
idem=T
```

Example:

```text
CMD:c0>r1:file/write:path='x',data='y',idem=T:!:a7;
```

When `idem=F` or unspecified, a coordinator MUST NOT assume replay is safe.

This is especially important for retries after ambiguous transport failures.

---

# 23. Deduplication

A receiver MAY retain completed correlation IDs.

If the same `(source, id)` pair is received again, the receiver MAY return the previously recorded result instead of executing the operation again.

Example:

```text
RET:r1>c0:file/write:stat='ok',replayed=T:$:a7;
```

This behavior is recommended for idempotent operations.

---

# 24. Capabilities

Agents MAY advertise supported actions through a `QRY`.

Example:

```text
QRY:c0>r1:capabilities:::q1;
```

Result:

```text
RET:r1>c0:capabilities:out=['read','find/vec','exec']:$:q1;
```

Capability discovery MUST NOT itself grant permission.

---

# 25. Protocol Version

A runtime SHOULD identify the protocol version during session initialization.

Example:

```text
QRY:c0>r1:protocol:version='TAL-1.0'::v1;
```

Response:

```text
RET:r1>c0:protocol:version='TAL-1.0',features=['corr','lifecycle','cancel']:$:v1;
```

A runtime MUST NOT assume extension support without negotiation when interoperability matters.

---

# 26. Unknown Extensions

Unknown payload keys MAY be ignored unless the action defines them as required.

Unknown flags MUST NOT be treated as valid silently.

Unknown lifecycle states MUST be handled as non-standard extensions.

For forward compatibility, implementations SHOULD expose unsupported functionality using:

```text
ERR:...:code='UNSUPPORTED'...
```

---

# 27. Error Handling Rules

A coordinator SHOULD distinguish four situations:

### Transport failure

No valid TAL response was received.

### Protocol failure

A malformed or invalid TAL message was received.

### Execution failure

The underlying operation failed.

### Semantic failure

The operation completed but its result does not satisfy the requested condition.

Only execution failure necessarily becomes an `ERR` from the target tool.

A coordinator MAY generate its own protocol-level `ERR`.

---

# 28. Recommended Agent Loop

A TAL-1 coordinator SHOULD conceptually:

```text
1. establish participants
2. create task ID
3. dispatch CMD/QRY
4. observe EVT
5. invoke native tool
6. emit RET or ERR
7. update THK state
8. dispatch dependent tasks
9. terminate when root task reaches terminal state
```

Example:

```text
THK:c0>self:plan:goal='audit',state='starting'::p1;
CMD:c0>r1:read:path='README.md':!:a1;
CMD:c0>r1:read:path='SPEC.md':!:a2;
EVT:r1>c0:state:s='running'::a1;
RET:r1>c0:read:stat='ok',out='...':$:a1;
EVT:r1>c0:state:s='running'::a2;
RET:r1>c0:read:stat='ok',out='...':$:a2;
THK:c0>self:eval:state='inputs_complete',decision='run_tests'::p2;
CMD:c0>r1:exec:cmd='tests':!:a3;
RET:r1>c0:exec:stat='ok':$:a3;
```

---

# 29. Compliance Levels

TAL-1 defines three conformance levels.

## Level 1 — Core

Required:

```text
THK
CMD
QRY
RET
ERR
correlation IDs
basic parsing
```

## Level 2 — Operational

Adds:

```text
EVT
lifecycle state
timeouts
cancellation
retry semantics
```

## Level 3 — Distributed

Adds:

```text
parent correlation
capability negotiation
streaming
deduplication
idempotency
version negotiation
```

A Level 3 implementation MUST remain backward-compatible with Level 1 message forms.

---

# 30. Reference ABNF

Conceptual grammar:

```text
frame      = opcode ":" source ">" target ":" action ":" payload ":" flags ":" id ";"

opcode     = "THK" / "CMD" / "QRY" / "RET" / "ERR" / "EVT"

source     = identifier
target     = identifier

action     = identifier *( "/" identifier )

payload    = "" / field *( "," field )
field      = key "=" value

key        = identifier

value      = string / number / boolean / list / map / null

boolean    = "T" / "F"
null       = "N"

flags      = "" / *( "!" / "?" / "^" / "$" )

id         = identifier

identifier = 1*( ALPHA / DIGIT / "_" / "-" / "." )
```

The reference parser additionally enforces escaped-delimiter and quoted-value rules. It retains compatibility opcodes `SYN` and `ACK` outside the TAL-1 core profile.

---

# 31. Canonical Examples

## Dispatch

```text
CMD:c0>r1:find/vec:q='TAL-1',limit=10:!:a1;
```

## Query

```text
QRY:c0>r1:status:target='a1'::q1;
```

## State event

```text
EVT:r1>c0:state:s='running'::a1;
```

## Result

```text
RET:r1>c0:find/vec:stat='ok',out=[{id='d1',score=0.94}]:$:a1;
```

## Error

```text
ERR:r1>c0:find/vec:code='TIMEOUT',retry=T,after=2s:$:a1;
```

## State summary

```text
THK:c0>self:eval:state='search_complete',decision='inspect_results'::p2;
```

## Cancellation

```text
CMD:c0>r1:halt:id='a1'::c1;
```

## Delegated child task

```text
CMD:r1>r2:read:path='spec.md',parent=a1:!:b1;
```

---

# 32. Core Invariants

A conforming TAL-1 implementation MUST preserve these invariants:

```text
I1  Every frame has one opcode.
I2  Every frame has explicit source and destination.
I3  CMD/QRY operations are correlatable.
I4  RET/ERR refer to the operation they complete or fail.
I5  Terminal task states do not transition again.
I6  TAL does not replace native execution APIs.
I7  Authorization is outside the meaning of TAL syntax.
I8  Unknown extensions cannot silently change core semantics.
I9  Correlation IDs distinguish concurrent operations.
I10 THK communicates summaries, not executable work.
```

---

# 33. Migration from TAL-0

TAL-1 preserves the TAL-0 conceptual vocabulary:

```text
THK  → retained
CMD  → retained
QRY  → retained
RET  → retained
ERR  → retained
```

TAL-1 adds:

```text
EVT              lifecycle observability
ID               correlation
parent           task hierarchy
code/retry       actionable errors
halt/id          cancellation
ttl              timeout
idem             idempotency
capabilities     capability discovery
version          protocol negotiation
```

The migration model is:

```text
TAL-0 coordination
        +
correlation
+
lifecycle
+
operational errors
+
recovery semantics
        =
TAL-1
```

---

# 34. Reference Mental Model

The protocol should be understood as four layers:

```text
                ┌─────────────────────┐
                │       THK           │
                │ state / decisions   │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │     CMD / QRY       │
                │ coordination intent│
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │ native tool/runtime │
                │ actual execution    │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │ RET / ERR / EVT     │
                │ observable outcome  │
                └─────────────────────┘
```

The key principle is:

> **TAL-1 describes what agents coordinate, not how the underlying platform executes it.**

That separation is the defining architectural boundary of TAL-1.

---

# 35. Reference Implementation Notes

The `choukrilabs/tal-gpt` reference implementation intentionally keeps the protocol core dependency-free. It provides:

- strict frame parsing and canonical serialization;
- correlation and parent ID support;
- lifecycle state tracking;
- cancellation handling;
- timeout/retry classification;
- idempotent result replay;
- capability discovery;
- deterministic local tools;
- optional Gemini transport;
- protocol and runtime tests.

The reference implementation should be treated as one interoperable implementation, not as the definition of native tool behavior.

---

# 36. End of Specification

**TAL-1.0 Proposed Standard**
