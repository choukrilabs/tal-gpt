# TAL-0 Language Specification

## 1. Status

TAL-0 is a compact textual protocol for machine-oriented agent coordination. A transmission is a sequence of atomic frames. Every frame terminates with `;`.

## 2. Frame grammar

```ebnf
stream        = { frame } ;
frame         = opcode, ":", source, ">", target, ":", action, ":", payload, ":", flags, ";" ;
opcode        = "THK" | "CMD" | "QRY" | "RET" | "ERR" | "EVT" | "SYN" | "ACK" ;
source        = agent-id ;
target        = agent-id ;
action        = nonempty-frame-text ;
payload       = { payload-char } ;
flags         = { flag-char } ;
agent-id      = (letter | digit | "_" | "." | "-") , { letter | digit | "_" | "." | "-" } ;
```

The reference parser treats `:` as a field delimiter and `;` as a frame terminator. Therefore payloads and actions must be frame-safe. Applications that need arbitrary binary/text values should encode them outside the base grammar.

## 3. Positional semantics

| Slot | Meaning | Example |
|---|---|---|
| 0 | Header/opcode | `CMD` |
| 1 | Source → target | `c0>r1` |
| 2 | Action | `find/vec` |
| 3 | Payload | `q='auth_cve',limit=1` |
| 4 | Flags | `!` |

Keeping the fields positional lets a parser reject malformed structure before a tool is invoked.

## 4. Opcodes

### THK
Structured internal decision record. Recommended phases are `plan`, `hyp`, `dedu`, `eval`, and `crit`. TAL-0 does not require exposing private chain-of-thought. A production implementation should prefer concise decision summaries, assumptions, and verification state.

### CMD
Imperative request to a worker or execution target.

### QRY
Non-mutating request for information.

### RET
Successful result frame.

### ERR
Failure frame carrying machine-readable error metadata.

### EVT
Asynchronous notification.

### SYN / ACK
Session and state synchronization handshake.

## 5. Action vocabulary

The reference implementation recognizes these examples:

```text
read
writ
exec
find
eval
call
pipe
sync
halt
tok
```

Common modifiers are expressed as a suffix, for example:

```text
exec/py
find/vec
read/mem
call/api
```

These strings are protocol-level conventions. Whether a string maps to a single BPE token depends on the model tokenizer and must be measured rather than assumed.

## 6. Flags

The reference examples use:

```text
!  atomic/strict intent
?  dry-run intent
^  urgent intent
$  final lifecycle marker
```

Flags are advisory metadata unless a runtime explicitly gives them enforcement semantics.

## 7. Payload conventions

Payloads use compact `key=value` fragments and simple arrays where practical:

```text
q='auth_cve',limit=1
out=50,stat='ok'
sub=[r1 e1]
```

The base protocol does not mandate a full payload data language. A deployment should define and version payload conventions separately from the frame envelope.

## 8. Stream parsing

A valid stream is simply concatenated frames:

```text
SYN:c0>r1:sync:ver='1'::;ACK:r1>c0:sync:ok=T::;
```

The reference parser rejects a stream that does not end in `;` and rejects empty frames between terminators.

## 9. Error handling

Workers should return `ERR` rather than throwing errors through the transport boundary:

```text
ERR:e1>c0:exec/py:code='dispatch_error',step='execute',retry=0,error='...':$;
```

Retry policy belongs to the orchestrator. Error fields such as `code`, `step`, and `retry` are recommended for deterministic recovery.

## 10. Tokenization claims

TAL-0 is designed to reduce redundant natural-language envelope overhead, but token count is tokenizer-dependent. A valid benchmark should report:

1. target model/tokenizer,
2. exact compared traces,
3. raw token counts,
4. methodology,
5. whether reasoning content was included.

Claims such as “70% savings” are benchmark results for a specific comparison, not an invariant of the language.
