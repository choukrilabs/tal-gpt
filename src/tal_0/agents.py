"""TAL-1 coordinator, workers, task lifecycle, and correlation handling."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from .core import Opcode, TALFrame, TALParseError, TALParser
from .tools import ToolRegistry

class TaskState(str, Enum):
    NEW='new'; DISPATCHED='dispatched'; RUNNING='running'; SUCCEEDED='succeeded'; FAILED='failed'; CANCELLED='cancelled'
class ErrorCode(str, Enum):
    INVALID='INVALID'; DENIED='DENIED'; TIMEOUT='TIMEOUT'; UNAVAILABLE='UNAVAILABLE'; CONFLICT='CONFLICT'; CANCELLED='CANCELLED'; FAILED='FAILED'; NOT_FOUND='NOT_FOUND'; UNSUPPORTED='UNSUPPORTED'

@dataclass
class TaskRecord:
    id:str; parent:Optional[str]; src:str; dst:str; action:str; state:TaskState=TaskState.NEW; created:str=''; started:Optional[str]=None; completed:Optional[str]=None
    def transition(self,state:TaskState)->None:
        terminal={TaskState.SUCCEEDED,TaskState.FAILED,TaskState.CANCELLED}
        if self.state in terminal: raise ValueError(f'terminal task cannot transition: {self.state.value}')
        valid={TaskState.NEW:{TaskState.DISPATCHED,TaskState.CANCELLED},TaskState.DISPATCHED:{TaskState.RUNNING,TaskState.CANCELLED},TaskState.RUNNING:{TaskState.SUCCEEDED,TaskState.FAILED,TaskState.CANCELLED}}
        if state not in valid.get(self.state,set()): raise ValueError(f'invalid task transition: {self.state.value}->{state.value}')
        self.state=state; now=datetime.now(timezone.utc).isoformat()
        if state==TaskState.RUNNING: self.started=now
        if state in terminal: self.completed=now

def _fields(payload:str)->Dict[str,str]:
    out={}
    for field in TALParser.split_payload(payload):
        try: key,value=TALParser.split_assignment(field); out[key]=value
        except TALParseError: pass
    return out

def _bool(value:str)->bool: return value.upper()=='T'

class SubAgent:
    def __init__(self,agent_id:str,role:str,tools:ToolRegistry): self.agent_id=agent_id; self.role=role; self.tools=tools
    def capabilities(self)->List[str]: return ['find/vec','exec/py','assert/equal','status']
    def handle(self,frame:TALFrame)->TALFrame:
        if frame.header not in (Opcode.CMD,Opcode.QRY): return self._err(frame,ErrorCode.INVALID,False,'unsupported_opcode')
        fields=_fields(frame.payload)
        if frame.action=='status': return TALFrame(Opcode.RET,self.agent_id,frame.source,'status',"stat='ok',out='unknown'",'$',frame.correlation_id)
        if frame.action=='capabilities': return TALFrame(Opcode.RET,self.agent_id,frame.source,'capabilities',f"stat='ok',out={self.capabilities()!r}",'$',frame.correlation_id)
        if frame.header==Opcode.QRY and frame.action not in {'find/vec','status','capabilities'}: return self._err(frame,ErrorCode.UNSUPPORTED,False,'QRY_cannot_mutate')
        try:
            if frame.action=='find/vec': result=self.tools.execute('find_vector',q=fields.get('q',''),limit=int(fields.get('limit','5')))
            elif frame.action in {'exec','exec/py'}: result=self.tools.execute('exec_python',code=fields.get('code',''))
            elif frame.action in {'assert','assert/equal'}: result=self.tools.execute('assert_equal',expected=fields.get('expected'),actual=fields.get('actual'))
            else: raise ValueError('unsupported action:'+frame.action)
            if result.status!='ok':
                err=str(result.error or 'tool failure'); timeout=err.startswith('timeout:'); return self._err(frame,ErrorCode.TIMEOUT if timeout else ErrorCode.FAILED,timeout,err,'after=2s' if timeout else '')
            return TALFrame(Opcode.RET,self.agent_id,frame.source,frame.action,f"stat='ok',out={result.output!r}",'$',frame.correlation_id)
        except ValueError as exc: return self._err(frame,ErrorCode.UNSUPPORTED,False,str(exc))
    def _err(self,frame,code,retry,cause,extra=''):
        suffix=','+extra if extra else ''
        return TALFrame(Opcode.ERR,self.agent_id,frame.source,frame.action,f"code='{code.value}',retry={'T' if retry else 'F'},cause={cause!r}{suffix}",'$',frame.correlation_id)

class CoordinatorAgent:
    def __init__(self,agent_id='c0',tools=None):
        self.agent_id=agent_id; self.tools=tools or ToolRegistry.default(); self.workers={k:SubAgent(k,k,self.tools) for k in ('r1','e1','v1')}; self.trace=[]; self.tasks={}; self.completed={}
    def register(self,frame):
        if frame.header in (Opcode.CMD,Opcode.QRY) and not frame.correlation_id: raise ValueError('CMD/QRY requires correlation ID')
        if frame.correlation_id in self.tasks: return self.tasks[frame.correlation_id]
        rec=TaskRecord(frame.correlation_id,frame.parent_id,frame.source,frame.target,frame.action,created=datetime.now(timezone.utc).isoformat()); self.tasks[rec.id]=rec; return rec
    def state_for(self,task_id): return self.tasks[task_id]
    def _event(self,frame,state): return TALFrame(Opcode.EVT,frame.target,frame.source,'state',f"s='{state}'",'',frame.correlation_id)
    def submit(self,frame):
        rec=self.register(frame); out=[frame]
        if rec.state==TaskState.NEW: rec.transition(TaskState.DISPATCHED); out.append(self._event(frame,'dispatched'))
        if rec.state==TaskState.DISPATCHED: rec.transition(TaskState.RUNNING); out.append(self._event(frame,'running'))
        result=self.route(frame,_record=False); out.append(result)
        rec.transition(TaskState.SUCCEEDED if result.header==Opcode.RET else TaskState.FAILED)
        self.trace.extend(out); return out
    def route(self,frame,_record=True):
        if frame.header not in (Opcode.CMD,Opcode.QRY): return self._err_to(frame,ErrorCode.INVALID,'expected CMD or QRY')
        fields=_fields(frame.payload); key=(frame.source,frame.correlation_id)
        if frame.header==Opcode.QRY and frame.action not in {'find/vec','status','capabilities'}: return self._err_to(frame,ErrorCode.UNSUPPORTED,'QRY_cannot_mutate')
        if _bool(fields.get('idem','F')) and key in self.completed:
            prior=self.completed[key]; return TALFrame(prior.header,prior.source,prior.target,prior.action,prior.payload+',replayed=T',prior.flags,prior.correlation_id,prior.parent_id)
        if frame.action=='halt' and frame.header==Opcode.CMD: return self.cancel(frame)
        target=self.workers.get(frame.target)
        result=self._err_to(frame,ErrorCode.NOT_FOUND,'agent_not_found') if target is None else target.handle(frame)
        if _bool(fields.get('idem','F')): self.completed[key]=result
        return result
    def cancel(self,cancellation):
        fields=_fields(cancellation.payload); task_id=fields.get('task','')
        if not task_id or task_id not in self.tasks: return self._err_to(cancellation,ErrorCode.NOT_FOUND,'task_not_found')
        rec=self.tasks[task_id]
        if rec.state in {TaskState.SUCCEEDED,TaskState.FAILED,TaskState.CANCELLED}: return self._err_to(cancellation,ErrorCode.CONFLICT,'already_completed')
        rec.transition(TaskState.CANCELLED); return TALFrame(Opcode.EVT,rec.dst,rec.src,'state',"s='cancelled'",'$',rec.id)
    def _err_to(self,frame,code,cause): return TALFrame(Opcode.ERR,self.agent_id,frame.source,frame.action,f"code='{code.value}',retry=F,cause={cause!r}",'$',frame.correlation_id)
    def run(self,objective):
        self.trace=[TALFrame(Opcode.THK,self.agent_id,'self','plan',f"goal='audit',objective={objective!r}",'','p1')]
        self.trace+=self.submit(TALFrame(Opcode.CMD,self.agent_id,'r1','find/vec',"q='auth_cve',limit=1",'!','a7'))
        self.trace.append(TALFrame(Opcode.THK,self.agent_id,'self','dedu',"decision='execute_boundary_check'",'','p2'))
        self.trace+=self.submit(TALFrame(Opcode.CMD,self.agent_id,'e1','exec/py',"code='min(100,50)'",'!','a8'))
        self.trace.append(TALFrame(Opcode.THK,self.agent_id,'self','eval',"state='verified',decision='complete'",'','p3'))
        self.trace.append(TALFrame(Opcode.RET,self.agent_id,'usr','report',"stat='ok',out='verification_complete'",'$','root'))
        return self.trace
