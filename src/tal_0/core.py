"""Core TAL-1 frame model, escaping, canonicalization, and parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class TALParseError(ValueError):
    """Raised when a TAL-1 frame or stream is invalid."""


class Opcode(str, Enum):
    THK = "THK"
    CMD = "CMD"
    QRY = "QRY"
    RET = "RET"
    ERR = "ERR"
    EVT = "EVT"
    SYN = "SYN"
    ACK = "ACK"


_ID_RE = re.compile(r"[A-Za-z0-9_.-]+")
_ACTION_RE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
_ALLOWED_FLAGS = "!?^$"
_ESCAPE_MAP = {";": ";", ",": ",", "=": "=", ":": ":", "\\": "\\", "'": "'"}


def escape(value: str) -> str:
    out = []
    for ch in value:
        if ch in (";", ",", "=", ":", "\\", "'"):
            out.append("\\")
        out.append(ch)
    return "".join(out)


def unescape(value: str) -> str:
    out: List[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(value):
            raise TALParseError("dangling escape at end of field")
        nxt = value[i + 1]
        if nxt not in _ESCAPE_MAP:
            raise TALParseError(f"unsupported escape: \\{nxt}")
        out.append(_ESCAPE_MAP[nxt])
        i += 2
    return "".join(out)


def _split_unescaped(text: str, delimiter: str, maxsplit: Optional[int] = None) -> List[str]:
    parts: List[str] = []
    start = 0
    escaped = False
    quote: Optional[str] = None
    splits = 0
    for i, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote is not None:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == delimiter and (maxsplit is None or splits < maxsplit):
            parts.append(text[start:i])
            start = i + 1
            splits += 1
    if escaped:
        raise TALParseError("dangling escape in field")
    if quote is not None:
        raise TALParseError("unterminated quoted value")
    parts.append(text[start:])
    return parts


@dataclass(frozen=True)
class TALFrame:
    header: Opcode
    source: str
    target: str
    action: str
    payload: str = ""
    flags: str = ""
    correlation_id: str = ""
    parent_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.header, Opcode):
            try:
                object.__setattr__(self, "header", Opcode(self.header))
            except ValueError as exc:
                raise ValueError("unsupported TAL opcode") from exc
        if not self.source or not _ID_RE.fullmatch(self.source):
            raise ValueError("source must be a non-empty agent identifier")
        if not self.target or not _ID_RE.fullmatch(self.target):
            raise ValueError("target must be a non-empty agent identifier")
        if not self.action or not _ACTION_RE.fullmatch(self.action):
            raise ValueError("action must be a slash-separated identifier")
        if "\n" in self.payload or "\r" in self.payload:
            raise ValueError("payload cannot contain newlines")
        if any(flag not in _ALLOWED_FLAGS for flag in self.flags):
            raise ValueError("flags may only contain ! ? ^ $")
        canonical_flags = "".join(flag for flag in _ALLOWED_FLAGS if flag in self.flags)
        object.__setattr__(self, "flags", canonical_flags)
        if self.correlation_id and not _ID_RE.fullmatch(self.correlation_id):
            raise ValueError("correlation_id must be an agent-safe identifier")
        if self.parent_id is not None and not _ID_RE.fullmatch(self.parent_id):
            raise ValueError("parent_id must be an agent-safe identifier")

    def serialize(self) -> str:
        payload = escape(self.payload)
        return f"{self.header.value}:{self.source}>{self.target}:{self.action}:{payload}:{self.flags}:{self.correlation_id};"


class TALParser:
    """Strict parser for TAL-1 frames and semicolon-terminated streams."""

    @classmethod
    def serialize(cls, frame: TALFrame) -> str:
        return frame.serialize()

    @classmethod
    def parse(cls, frame_text: str) -> TALFrame:
        if not frame_text or not frame_text.endswith(";"):
            raise TALParseError("frame must terminate with a semicolon")
        body = frame_text[:-1]
        parts = _split_unescaped(body, ":", maxsplit=5)
        if len(parts) != 6:
            raise TALParseError("invalid TAL-1 field count")
        header_text, routing, action, payload_wire, flags_wire, correlation_wire = parts
        try:
            opcode = Opcode(header_text)
        except ValueError as exc:
            raise TALParseError("unsupported TAL-1 opcode") from exc
        routing_parts = _split_unescaped(routing, ">", maxsplit=1)
        if len(routing_parts) != 2:
            raise TALParseError("routing must contain source>target")
        source, target = routing_parts
        try:
            payload = unescape(payload_wire)
            flags = unescape(flags_wire)
            correlation_id = unescape(correlation_wire)
            parent_id = None
            if payload:
                for field in cls.split_payload(payload):
                    try:
                        key, value = cls.split_assignment(field)
                    except TALParseError:
                        continue
                    if key == "parent":
                        parent_id = value
                        break
            return TALFrame(opcode, unescape(source), unescape(target), unescape(action), payload, flags, correlation_id, parent_id)
        except ValueError as exc:
            raise TALParseError(str(exc)) from exc

    @classmethod
    def parse_stream(cls, stream_text: str) -> List[TALFrame]:
        if not stream_text:
            return []
        frames: List[TALFrame] = []
        start = 0
        escaped = False
        for i, ch in enumerate(stream_text):
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == ";":
                body = stream_text[start : i + 1]
                if body == ";":
                    raise TALParseError("empty frame in stream")
                frames.append(cls.parse(body))
                start = i + 1
        if escaped:
            raise TALParseError("dangling escape in stream")
        if start != len(stream_text):
            raise TALParseError("stream must end with a semicolon")
        return frames

    @staticmethod
    def split_payload(payload: str) -> List[str]:
        return _split_unescaped(payload, ",") if payload else []

    @staticmethod
    def split_assignment(field: str) -> Tuple[str, str]:
        parts = _split_unescaped(field, "=", maxsplit=1)
        if len(parts) != 2:
            raise TALParseError("payload field must be key=value")
        key, value = parts
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise TALParseError("payload key must be lowercase ascii")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        return key, value
