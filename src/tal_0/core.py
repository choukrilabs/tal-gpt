"""TAL-1 frame model and strict six-field parser."""
from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

class TALParseError(ValueError):
    """Raised when a TAL-1 frame or stream is invalid."""

class Opcode(str, Enum):
    THK="THK"; CMD="CMD"; QRY="QRY"; RET="RET"; ERR="ERR"; EVT="EVT"; SYN="SYN"; ACK="ACK"

_ID_RE=re.compile(r"[A-Za-z0-9_.-]+")
_ACTION_RE=re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
_ALLOWED_FLAGS="!?^$"
_ESCAPE_MAP={";":";",",":",","=":"=",":":":","\\":"\\","'":"'"}

def escape(value:str)->str:
    out=[]
    for ch in value:
        if ch in _ESCAPE_MAP: out.append("\\")
        out.append(ch)
    return "".join(out)

def escape_payload(value:str)->str:
    out=[]; escaped=False; quote=None
    for ch in value:
        if escaped:
            out.append(ch); escaped=False; continue
        if ch=="\\": out.append("\\"); escaped=True; continue
        if quote:
            if ch==quote: quote=None
            out.append("\\;" if ch==";" else ch); continue
        if ch in ("'",'"'):
            quote=ch; out.append(ch); continue
        out.append("\\;" if ch==";" else ch)
    if escaped or quote: raise ValueError("invalid payload escaping")
    return "".join(out)

def unescape(value:str)->str:
    out=[]; i=0
    while i<len(value):
        if value[i]!="\\": out.append(value[i]); i+=1; continue
        if i+1>=len(value): raise TALParseError("dangling escape at end of field")
        nxt=value[i+1]
        if nxt not in _ESCAPE_MAP: raise TALParseError(f"unsupported escape: \\{nxt}")
        out.append(_ESCAPE_MAP[nxt]); i+=2
    return "".join(out)

def _split(text:str, delimiter:str, maxsplit:Optional[int]=None, bracket_depth:bool=True)->List[str]:
    parts=[]; start=0; escaped=False; quote=None; stack=[]; splits=0; pairs={')':'(',']':'[','}':'{'}
    for i,ch in enumerate(text):
        if escaped: escaped=False; continue
        if ch=="\\": escaped=True; continue
        if quote:
            if ch==quote: quote=None
            continue
        if ch in ("'",'"'): quote=ch; continue
        if bracket_depth:
            if ch in "([{": stack.append(ch); continue
            if ch in ")]}":
                if not stack or stack[-1]!=pairs[ch]: raise TALParseError("unbalanced brackets")
                stack.pop(); continue
        if ch==delimiter and (maxsplit is None or splits<maxsplit) and not stack:
            parts.append(text[start:i]); start=i+1; splits+=1
    if escaped: raise TALParseError("dangling escape in field")
    if quote is not None: raise TALParseError("unterminated quoted value")
    if stack: raise TALParseError("unbalanced brackets")
    parts.append(text[start:]); return parts

@dataclass(frozen=True)
class TALFrame:
    header: Opcode|str
    source:str; target:str; action:str; payload:str=""; flags:str=""; correlation_id:str=""; parent_id:Optional[str]=None
    def __post_init__(self):
        if not isinstance(self.header,Opcode):
            try: object.__setattr__(self,"header",Opcode(self.header))
            except ValueError as exc: raise ValueError("unsupported TAL opcode") from exc
        for name,val in (("source",self.source),("target",self.target)):
            if not _ID_RE.fullmatch(val): raise ValueError(f"{name} must be a valid identifier")
        if not _ACTION_RE.fullmatch(self.action): raise ValueError("action must be a slash-separated identifier")
        if "\n" in self.payload or "\r" in self.payload: raise ValueError("payload cannot contain newlines")
        if any(flag not in _ALLOWED_FLAGS for flag in self.flags): raise ValueError("flags may only contain ! ? ^ $")
        object.__setattr__(self,"flags","".join(f for f in _ALLOWED_FLAGS if f in self.flags))
        if self.correlation_id and not _ID_RE.fullmatch(self.correlation_id): raise ValueError("invalid correlation_id")
        if self.parent_id is not None and not _ID_RE.fullmatch(self.parent_id): raise ValueError("invalid parent_id")
    def serialize(self)->str:
        return f"{self.header.value}:{escape(self.source)}>{escape(self.target)}:{escape(self.action)}:{escape_payload(self.payload)}:{escape(self.flags)}:{escape(self.correlation_id)};"

class TALParser:
    @classmethod
    def serialize(cls,frame:TALFrame)->str: return frame.serialize()
    @classmethod
    def parse(cls,text:str)->TALFrame:
        if not text or not text.endswith(";"): raise TALParseError("frame must terminate with a semicolon")
        parts=_split(text[:-1],":",maxsplit=5,bracket_depth=False)
        if len(parts)!=6: raise TALParseError("invalid TAL-1 field count: expected 6")
        op,route,action,payload_wire,flags_wire,corr_wire=parts
        try: opcode=Opcode(op)
        except ValueError as exc: raise TALParseError("unsupported TAL-1 opcode") from exc
        rp=_split(route,">",maxsplit=1,bracket_depth=False)
        if len(rp)!=2: raise TALParseError("routing must contain source>target")
        payload=unescape(payload_wire); flags=unescape(flags_wire); corr=unescape(corr_wire)
        parent=None
        for field in cls.split_payload(payload):
            try:
                key,value=cls.split_assignment(field)
            except TALParseError: continue
            if key=="parent": parent=value
        try:
            return TALFrame(opcode,unescape(rp[0]),unescape(rp[1]),unescape(action),payload,flags,corr,parent)
        except ValueError as exc: raise TALParseError(str(exc)) from exc
    @classmethod
    def parse_stream(cls,text:str)->List[TALFrame]:
        if not text: return []
        frames=[]; start=0; escaped=False; quote=None
        for i,ch in enumerate(text):
            if escaped: escaped=False; continue
            if ch=="\\": escaped=True; continue
            if quote:
                if ch==quote: quote=None
                continue
            if ch in ("'",'"'): quote=ch; continue
            if ch==";": frames.append(cls.parse(text[start:i+1])); start=i+1
        if escaped or quote is not None: raise TALParseError("invalid stream escaping")
        if start!=len(text): raise TALParseError("stream must end with a semicolon")
        return frames
    @staticmethod
    def split_payload(payload:str)->List[str]: return _split(payload,",") if payload else []
    @staticmethod
    def split_assignment(field:str)->Tuple[str,str]:
        p=_split(field,"=",maxsplit=1)
        if len(p)!=2: raise TALParseError("payload field must be key=value")
        key,value=p
        if not re.fullmatch(r"[a-z][a-z0-9_]*",key): raise TALParseError("payload key must be lowercase ascii")
        if len(value)>=2 and value[0]==value[-1] and value[0] in ("'",'"'): value=value[1:-1]
        return key,value
