import unittest
from tal_0 import CoordinatorAgent, ErrorCode, Opcode, TALFrame, TaskState, TokenBenchmark, GeminiLLMClient

class LifecycleTests(unittest.TestCase):
    def test_submit_records_task_and_terminal_result_uses_same_id(self):
        c=CoordinatorAgent(); trace=c.submit(TALFrame(Opcode.CMD,'c0','r1','find/vec',"q='auth_cve'",'!','a7'))
        self.assertEqual(trace[-1].correlation_id,'a7'); self.assertEqual(c.state_for('a7').state,TaskState.SUCCEEDED)
    def test_concurrent_tasks_are_independent(self):
        c=CoordinatorAgent(); c.submit(TALFrame(Opcode.QRY,'c0','r1','status',"target='a1'",'','a1')); c.submit(TALFrame(Opcode.QRY,'c0','r1','status',"target='a2'",'','a2')); self.assertNotEqual(c.state_for('a1').id,c.state_for('a2').id)
    def test_cancel_running_task_uses_task_key_and_preserves_request_id(self):
        c=CoordinatorAgent(); task=TALFrame(Opcode.CMD,'c0','r1','exec',"code='timeout'",'','a7'); rec=c.register(task); rec.transition(TaskState.DISPATCHED); rec.transition(TaskState.RUNNING)
        result=c.cancel(TALFrame(Opcode.CMD,'c0','r1','halt',"task='a7'",'','c9'))
        self.assertEqual(result.header,Opcode.EVT); self.assertEqual(result.correlation_id,'a7'); self.assertEqual(c.state_for('a7').state,TaskState.CANCELLED)
    def test_terminal_task_cannot_transition(self):
        c=CoordinatorAgent(); c.submit(TALFrame(Opcode.CMD,'c0','r1','find/vec',"q='auth'",'','a1'))
        with self.assertRaises(ValueError): c.state_for('a1').transition(TaskState.RUNNING)

class OperationalTests(unittest.TestCase):
    def test_timeout_error_contains_retry(self):
        r=CoordinatorAgent().route(TALFrame(Opcode.CMD,'c0','e1','exec',"code='timeout'",'','a7')); self.assertEqual(r.header,Opcode.ERR); self.assertIn("TIMEOUT",r.payload); self.assertIn('retry=T',r.payload)
    def test_idempotent_replay(self):
        c=CoordinatorAgent(); f=TALFrame(Opcode.CMD,'c0','r1','assert/equal',"expected='x',actual='x',idem=T",'','a7'); c.route(f); r=c.route(f); self.assertIn('replayed=T',r.payload)
    def test_qry_rejects_mutation(self):
        r=CoordinatorAgent().route(TALFrame(Opcode.QRY,'c0','r1','write',"path='x'",'?','q9')); self.assertEqual(r.header,Opcode.ERR)
    def test_capabilities(self):
        r=CoordinatorAgent().route(TALFrame(Opcode.QRY,'c0','r1','capabilities','','','q1')); self.assertEqual(r.header,Opcode.RET); self.assertIn('find/vec',r.payload)

class IntegrationTests(unittest.TestCase):
    def test_run_emits_tal1_lifecycle(self):
        headers=[f.header for f in CoordinatorAgent().run('demo')]; self.assertIn(Opcode.THK,headers); self.assertIn(Opcode.CMD,headers); self.assertIn(Opcode.EVT,headers); self.assertIn(Opcode.RET,headers)
    def test_cancel_missing_task(self):
        r=CoordinatorAgent().cancel(TALFrame(Opcode.CMD,'c0','r1','halt',"task='missing'",'','c1')); self.assertEqual(r.header,Opcode.ERR); self.assertIn(ErrorCode.NOT_FOUND.value,r.payload)

class PackageTests(unittest.TestCase):
    def test_fallback_mentions_tal1(self): self.assertIn('TAL-1',GeminiLLMClient(api_key=None).generate('demo'))
    def test_benchmark_mentions_tal1(self): self.assertIn('TAL-1',TokenBenchmark.render_table(TokenBenchmark.compare('a','b','c')))

if __name__=='__main__': unittest.main()
