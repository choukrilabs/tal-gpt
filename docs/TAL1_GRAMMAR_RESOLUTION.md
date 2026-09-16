# TAL-1 Grammar Resolution

**Status:** Normative clarification for TAL-1.0

## Decision

TAL-1 uses exactly **six top-level colon-delimited fields**:

```text
<OP>:<SRC>><DST>:<ACT>:<PAYLOAD>:<FLAGS>:<ID>;
```

The six fields are:

1. `OP`
2. `SRC>DST`
3. `ACT`
4. `PAYLOAD`
5. `FLAGS`
6. `ID`

A conforming parser MUST reject a frame that produces any other number of top-level fields.

## Canonical empty-payload and empty-flags forms

```text
CMD:c0>r1:read::!:a1;
QRY:c0>r1:status:target='job-7'::q3;
THK:c0>self:plan:goal='audit'::p1;
```

There is no implicit seventh field.

## Corrected result/error examples

```text
RET:r1>c0:find/vec:out=[{id='d1',score=0.93}],stat='ok':$:a7;
ERR:r1>c0:find/vec:code='TIMEOUT',retry=T,after=2s:$:a7;
```

Examples that contain an additional colon before the flags field are documentation errors and MUST NOT be interpreted as a seven-field wire format.

## Cancellation identifier

The frame correlation identifier and the target task identifier are different values. Cancellation therefore uses `task` inside the payload:

```text
CMD:c0>r1:halt:task='a7'::c9;
```

Here `c9` identifies the cancellation request itself and `a7` identifies the task being cancelled.

The resulting terminal event retains the target task correlation ID:

```text
EVT:r1>c0:state:s='cancelled':$:a7;
```

## Payload splitting

Top-level payload fields are comma-separated, but commas inside quoted strings, lists, or maps are data.

For example:

```text
out=[{id='d1',score=0.93},{id='d2',score=0.88}],msg='a,b',ok=T
```

contains exactly three top-level fields.

Implementations MUST use quote-aware and bracket-depth-aware scanning when splitting payload fields and assignments.

## Escaping

A semicolon inside payload data MUST be escaped as `\\;` because semicolon terminates a frame. Backslash escapes are processed before semantic interpretation.

## Compatibility

This clarification preserves the intended TAL-1 six-field model and is the normative interpretation for the reference implementation.
