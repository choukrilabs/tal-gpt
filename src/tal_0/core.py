"""Core TAL-0 frame model and parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List


class TALParseError(ValueError):
    """Raised when a TAL-0 frame or stream is invalid."""


class Opcode(str, Enum):
    THK = "THK"
    CMD = "CMD"
    QRY = "QRY"
    RET = "RET"
    ERR = "ERR"
    EVT = "EVT"
    SYN = "SYN"
    ACK = "ACK"


@dataclass(frozen=True)
class TALFrame:
    header: Opcode
    source: str
    target: str
    action: str
    payload: str = ""
    flags: str = ""

    def __post_init__(self) -> None:
        if not self.source or not re.fullmatch(r"[A-Za-z0-9_.-]+", self.source):
            raise ValueError("source must be a non-empty agent identifier")
        if not self.target or not re.fullmatch(r"[A-Za-z0-9_.-]+", self.target):
            raise ValueError("target must be a non-empty agent identifier")
        if not self.action or any(ch in self.action for ch in ":;\n\r"):
            raise ValueError("action must be non-empty and frame-safe")
        if any(ch in self.flags for ch in ":;\n\r"):
            raise ValueError("flags must be frame-safe")
        if any(ch in self.payload for ch in ";\n\r"):
            raise ValueError("payload cannot contain frame terminators/newlines")

    def serialize(self) -> str:
        return f"{self.header.value}:{self.source}>{self.target}:{self.action}:{self.payload}:{self.flags};"


class TALParser:
    """Strict parser for one TAL-0 frame or a semicolon-terminated stream."""

    _FRAME_RE = re.compile(
        r"^(?P<header>[A-Z]{3}):(?P<source>[A-Za-z0-9_.-]+)>(?P<target>[A-Za-z0-9_.-]+):"
        r"(?P<action>[^:;\r\n]+):(?P<payload>[^;\r\n]*):(?P<flags>[^:;\r\n]*);$"
    )

    @classmethod
    def parse(cls, frame_text: str) -> TALFrame:
        match = cls._FRAME_RE.fullmatch(frame_text)
        if not match:
            raise TALParseError("invalid TAL-0 frame syntax")
        try:
            header = Opcode(match.group("header"))
        except ValueError as exc:
            raise TALParseError("unsupported TAL-0 opcode") from exc
        try:
            return TALFrame(
                header=header,
                source=match.group("source"),
                target=match.group("target"),
                action=match.group("action"),
                payload=match.group("payload"),
                flags=match.group("flags"),
            )
        except ValueError as exc:
            raise TALParseError(str(exc)) from exc

    @classmethod
    def parse_stream(cls, stream_text: str) -> List[TALFrame]:
        if not stream_text:
            return []
        parts = stream_text.split(";")
        if parts[-1] != "":
            raise TALParseError("stream must end with a semicolon")
        frames = []
        for body in parts[:-1]:
            if not body:
                raise TALParseError("empty frame in stream")
            frames.append(cls.parse(body + ";"))
        return frames
