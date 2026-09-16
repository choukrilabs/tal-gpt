"""TAL-1 coordinator, worker agents, task lifecycle, and correlation handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from .core import Opcode, TALFrame, TALParseError, TALParser
from .tools import ToolRegistry


class TaskState(str, Enum):
    NEW = "new"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorCode(str, Enum):
    INVALID = "INVALID"
    DENIED = "DENIED"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICT = "CONFLICT"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    NOT_FOUND = "NOT_FOUND"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class TaskRecord:
    id: str
    parent: Optional[str]
    src: str
    dst: str
    action: str
    state: TaskState = TaskState.NEW
    created: str = ""
    started: Optional[str] = None
    completed: Optional[str] = None

    def transition(self, state: TaskState) -> None:
        terminal = {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED}
        if self.state in terminal:
            raise ValueError(f"terminal task cannot transition: {self.state.value}")
        valid = {
            TaskState.NEW: {TaskState.DISPATCHED, TaskState.CANCELLED},
            TaskState.DISPATCHED: {TaskState.RUNNING, TaskState.CANCELLED},
            TaskState.RUNNING: {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED},
        }
        if state not in valid.get(self.state, set()):
            raise ValueError(f"invalid task transition: {self.state.value}->{state.value}")
        self.state = state
        now = datetime.now(timezone.utc).isoformat()
        if state == TaskState.RUNNING:
            self.started = now
        if state in terminal:
            self.completed = now


def _quote(value: object) -> str:
    return repr(value)


def _payload_dict(payload: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for field in TALParser.split_payload(payload):
        try:
            key, value = TALParser.split_assignment(field)
        except TALParseError:
            continue
        result[key] = value
    return result


def _bool_field(fields: Dict[str, str], key: str) -> bool:
    return fields.get(key, "F").upper() == "T"


class SubAgent:
    def __init__(self, agent_id: str, role: str, tools: ToolRegistry) -> None:
        self.agent_id = agent_id
        self.role = role
        self.tools = tools

    def capabilities(self) -> List[str]:
        return ["find/vec", "exec/py", "assert/equal", "status"]

    def handle(self, frame: TALFrame) -> TALFrame:
        if frame.header not in (Opcode.CMD, Opcode.QRY):
            return TALFrame(Opcode.ERR, self.agent_id, frame.source, "error", "code='INVALID',retry=F,cause='unsupported_opcode'", "$", frame.correlation_id)
        fields = _payload_dict(frame.payload)
        if frame.action == "status":
            out = f"state='unknown',target={_quote(fields.get('target', ''))}"
            return TALFrame(Opcode.RET, self.agent_id, frame.source, frame.action, f"stat='ok',out={_quote(out)}", "$", frame.correlation_id)
        if frame.action == "capabilities":
            return TALFrame(Opcode.RET, self.agent_id, frame.source, frame.action, f"stat='ok',out={self.capabilities()!r}", "$", frame.correlation_id)
        try:
            tool_name, kwargs = self._resolve(frame.action, fields)
            result = self.tools.execute(tool_name, **kwargs)
            if result.status != "ok":
                error = result.error or "tool failure"
                if "TimeoutError" in str(error) or str(error).startswith("timeout:"):
                    return self._err(frame, ErrorCode.TIMEOUT, retry=True, cause=error, extra="after=2s")
                return self._err(frame, ErrorCode.FAILED, retry=False, cause=error)
            payload = f"stat='ok',out={_quote(result.output)}"
            return TALFrame(Opcode.RET, self.agent_id, frame.source, frame.action, payload, "$", frame.correlation_id)
        except ValueError as exc:
            return self._err(frame, ErrorCode.UNSUPPORTED, retry=False, cause=str(exc))
        except Exception as exc:
            return self._err(frame, ErrorCode.FAILED, retry=False, cause=str(exc))

    def _err(self, frame: TALFrame, code: ErrorCode, *, retry: bool, cause: str, extra: str = "") -> TALFrame:
        suffix = f",{extra}" if extra else ""
        payload = f"code='{code.value}',retry={'T' if retry else 'F'},cause={_quote(cause)}{suffix}"
        return TALFrame(Opcode.ERR, self.agent_id, frame.source, frame.action, payload, "$", frame.correlation_id)

    @staticmethod
    def _resolve(action: str, fields: Dict[str, str]):
        if action == "find/vec":
            return "find_vector", {"q": fields.get("q", ""), "limit": int(fields.get("limit", "5"))}
        if action in ("exec/py", "exec"):
            return "exec_python", {"code": fields.get("code", "")}
        if action in ("assert", "assert/equal"):
            return "assert_equal", {"expected": fields.get("expected"), "actual": fields.get("actual")}
        raise ValueError(f"unsupported action:{action}")


class CoordinatorAgent:
    def __init__(self, agent_id: str = "c0", tools: Optional[ToolRegistry] = None) -> None:
        self.agent_id = agent_id
        self.tools = tools or ToolRegistry.default()
        self.workers = {
            "r1": SubAgent("r1", "research", self.tools),
            "e1": SubAgent("e1", "sandbox", self.tools),
            "v1": SubAgent("v1", "verify", self.tools),
        }
        self.trace: List[TALFrame] = []
        self.tasks: Dict[str, TaskRecord] = {}
        self.completed: Dict[tuple[str, str], TALFrame] = {}

    def register(self, frame: TALFrame) -> TaskRecord:
        if not frame.correlation_id:
            raise ValueError("CMD/QRY requires a correlation ID")
        if frame.correlation_id in self.tasks:
            return self.tasks[frame.correlation_id]
        record = TaskRecord(frame.correlation_id, frame.parent_id, frame.source, frame.target, frame.action, created=datetime.now(timezone.utc).isoformat())
        self.tasks[record.id] = record
        return record

    def state_for(self, task_id: str) -> TaskRecord:
        return self.tasks[task_id]

    def submit(self, frame: TALFrame) -> List[TALFrame]:
        if frame.header not in (Opcode.CMD, Opcode.QRY):
            raise ValueError("submit accepts only CMD or QRY")
        record = self.tasks.get(frame.correlation_id) or self.register(frame)
        local_trace: List[TALFrame] = [frame]
        if record.state == TaskState.NEW:
            record.transition(TaskState.DISPATCHED)
            local_trace.append(self._event(frame, "dispatched"))
        if record.state == TaskState.DISPATCHED:
            record.transition(TaskState.RUNNING)
            local_trace.append(self._event(frame, "running"))
        result = self.route(frame, _record=False)
        local_trace.append(result)
        self.trace.extend(local_trace)
        return local_trace

    def route(self, frame: TALFrame, _record: bool = True) -> TALFrame:
        if frame.header not in (Opcode.CMD, Opcode.QRY):
            return self._err_to(frame, ErrorCode.INVALID, "expected CMD or QRY")
        if not frame.correlation_id:
            return self._err_to(frame, ErrorCode.INVALID, "missing_correlation_id", correlation_id="")
        key = (frame.source, frame.correlation_id)
        fields = _payload_dict(frame.payload)
        if frame.header == Opcode.QRY and frame.action not in {"status", "capabilities", "find/vec"}:
            return self._err_to(frame, ErrorCode.UNSUPPORTED, "QRY_cannot_mutate")
        if _bool_field(fields, "idem") and key in self.completed:
            prior = self.completed[key]
            return TALFrame(prior.header, prior.source, prior.target, prior.action, prior.payload + ",replayed=T", prior.flags, prior.correlation_id, prior.parent_id)
        if frame.action == "halt" and frame.header == Opcode.CMD:
            return self.cancel(frame)
        target = self.workers.get(frame.target)
        if target is None:
            result = self._err_to(frame, ErrorCode.NOT_FOUND, "agent_not_found")
        else:
            if frame.correlation_id not in self.tasks and _record:
                record = self.register(frame)
                record.transition(TaskState.DISPATCHED)
                record.transition(TaskState.RUNNING)
            result = target.handle(frame)
        if frame.correlation_id in self.tasks:
            record = self.tasks[frame.correlation_id]
            if result.header == Opcode.RET:
                if record.state == TaskState.NEW:
                    record.transition(TaskState.DISPATCHED); record.transition(TaskState.RUNNING)
                if record.state == TaskState.DISPATCHED:
                    record.transition(TaskState.RUNNING)
                record.transition(TaskState.SUCCEEDED)
            elif result.header == Opcode.ERR:
                record.state = TaskState.FAILED
                record.completed = datetime.now(timezone.utc).isoformat()
        if _bool_field(fields, "idem") and result.header in (Opcode.RET, Opcode.ERR):
            self.completed[key] = result
        return result

    def run(self, objective: str) -> List[TALFrame]:
        self.trace = [TALFrame(Opcode.THK, self.agent_id, "self", "plan", f"goal='audit',objective={_quote(objective)}", "", "p1")]
        self.trace += self.submit(TALFrame(Opcode.CMD, self.agent_id, "r1", "find/vec", "q='auth_cve',limit=1", "!", "a7"))
        self.trace.append(TALFrame(Opcode.THK, self.agent_id, "self", "dedu", "decision='execute_boundary_check'", "", "p2"))
        self.trace += self.submit(TALFrame(Opcode.CMD, self.agent_id, "e1", "exec/py", "code='min(100,50)'", "!", "a8"))
        self.trace.append(TALFrame(Opcode.THK, self.agent_id, "self", "eval", "state='verified',decision='complete'", "", "p3"))
        self.trace.append(TALFrame(Opcode.RET, self.agent_id, "usr", "report", "stat='ok',out='verification_complete'", "$", "root"))
        return self.trace

    def cancel(self, cancellation: TALFrame) -> TALFrame:
        fields = _payload_dict(cancellation.payload)
        target_id = fields.get("id", "")
        if not target_id or target_id not in self.tasks:
            return self._err_to(cancellation, ErrorCode.NOT_FOUND, "task_not_found", correlation_id=cancellation.correlation_id)
        record = self.tasks[target_id]
        if record.state in {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED}:
            return self._err_to(cancellation, ErrorCode.CONFLICT, "already_completed", correlation_id=cancellation.correlation_id)
        record.transition(TaskState.CANCELLED)
        return TALFrame(Opcode.EVT, record.dst, record.src, "state", "s='cancelled'", "$", record.id)

    def _event(self, frame: TALFrame, state: str) -> TALFrame:
        return TALFrame(Opcode.EVT, frame.target, frame.source, "state", f"s='{state}'", "", frame.correlation_id)

    def _err_to(self, frame: TALFrame, code: ErrorCode, cause: str, *, correlation_id: Optional[str] = None) -> TALFrame:
        return TALFrame(Opcode.ERR, self.agent_id, frame.source, frame.action, f"code='{code.value}',retry=F,cause='{cause}'", "$", frame.correlation_id if correlation_id is None else correlation_id)
