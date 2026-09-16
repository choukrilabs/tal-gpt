import unittest

from tal_0.agents import CoordinatorAgent, ErrorCode, TaskState
from tal_0.benchmark import TokenBenchmark
from tal_0.client import GeminiLLMClient
from tal_0.core import Opcode, TALFrame


class LifecycleTests(unittest.TestCase):
    def test_submit_records_task_and_terminal_result_uses_same_id(self):
        coordinator = CoordinatorAgent()
        trace = coordinator.submit(TALFrame(Opcode.CMD, "c0", "r1", "find/vec", "q='auth_cve'", "!", "a7"))
        self.assertEqual(trace[0].correlation_id, "a7")
        self.assertEqual(trace[-1].correlation_id, "a7")
        self.assertEqual(coordinator.state_for("a7").state, TaskState.SUCCEEDED)

    def test_concurrent_tasks_are_independent(self):
        coordinator = CoordinatorAgent()
        coordinator.submit(TALFrame(Opcode.QRY, "c0", "r1", "status", "target='a1'", "", "a1"))
        coordinator.submit(TALFrame(Opcode.QRY, "c0", "r1", "status", "target='a2'", "", "a2"))
        self.assertNotEqual(coordinator.state_for("a1").id, coordinator.state_for("a2").id)

    def test_cancel_running_task_emits_terminal_event(self):
        coordinator = CoordinatorAgent()
        task = TALFrame(Opcode.CMD, "c0", "r1", "exec", "code='timeout'", "", "a7")
        coordinator.register(task)
        record = coordinator.state_for("a7")
        record.transition(TaskState.DISPATCHED)
        record.transition(TaskState.RUNNING)
        cancellation = TALFrame(Opcode.CMD, "c0", "r1", "halt", "id='a7'", "", "c9")
        result = coordinator.cancel(cancellation)
        self.assertEqual(result.header, Opcode.EVT)
        self.assertEqual(result.correlation_id, "a7")
        self.assertEqual(coordinator.state_for("a7").state, TaskState.CANCELLED)

    def test_terminal_task_cannot_transition(self):
        coordinator = CoordinatorAgent()
        frame = TALFrame(Opcode.CMD, "c0", "r1", "find/vec", "q='auth'", "", "a1")
        coordinator.submit(frame)
        with self.assertRaises(ValueError):
            coordinator.state_for("a1").transition(TaskState.RUNNING)


class OperationalSemanticsTests(unittest.TestCase):
    def test_timeout_error_contains_retry_and_delay(self):
        coordinator = CoordinatorAgent()
        frame = TALFrame(Opcode.CMD, "c0", "e1", "exec", "code='timeout'", "", "a7")
        result = coordinator.route(frame)
        self.assertEqual(result.header, Opcode.ERR)
        self.assertIn("code='TIMEOUT'", result.payload)
        self.assertIn("retry=T", result.payload)
        self.assertIn("after=2s", result.payload)

    def test_duplicate_id_does_not_execute_twice_when_idempotent(self):
        coordinator = CoordinatorAgent()
        frame = TALFrame(Opcode.CMD, "c0", "r1", "assert/equal", "expected='x',actual='x',idem=T", "", "a7")
        first = coordinator.route(frame)
        second = coordinator.route(frame)
        self.assertEqual(first.header, Opcode.RET)
        self.assertEqual(second.header, Opcode.RET)
        self.assertIn("replayed=T", second.payload)

    def test_capability_query_returns_supported_actions(self):
        coordinator = CoordinatorAgent()
        result = coordinator.route(TALFrame(Opcode.QRY, "c0", "r1", "capabilities", "", "", "q1"))
        self.assertEqual(result.header, Opcode.RET)
        self.assertIn("find/vec", result.payload)

    def test_qry_rejects_mutating_action(self):
        coordinator = CoordinatorAgent()
        result = coordinator.route(TALFrame(Opcode.QRY, "c0", "r1", "write", "path='x'", "?", "q9"))
        self.assertEqual(result.header, Opcode.ERR)
        self.assertIn("QRY_cannot_mutate", result.payload)

    def test_missing_agent_returns_not_found(self):
        coordinator = CoordinatorAgent()
        result = coordinator.route(TALFrame(Opcode.CMD, "c0", "z9", "read", "path='x'", "", "a9"))
        self.assertEqual(result.header, Opcode.ERR)
        self.assertIn("NOT_FOUND", result.payload)

    def test_parent_correlation_is_preserved(self):
        coordinator = CoordinatorAgent()
        frame = TALParserRoundTripHelper.child_frame()
        coordinator.register(frame)
        self.assertEqual(coordinator.state_for("b1").parent, "a7")


class PackageTests(unittest.TestCase):
    def test_fallback_mentions_tal_1(self):
        self.assertIn("TAL-1", GeminiLLMClient(api_key=None).generate("demo"))

    def test_benchmark_table_names_tal_1(self):
        results = TokenBenchmark.compare("a b", "a", "a")
        self.assertIn("TAL-1", TokenBenchmark.render_table(results))


class IntegrationTests(unittest.TestCase):
    def test_coordinator_run_contains_tal1_lifecycle(self):
        trace = CoordinatorAgent().run("demo")
        headers = [frame.header for frame in trace]
        self.assertIn(Opcode.THK, headers)
        self.assertIn(Opcode.CMD, headers)
        self.assertIn(Opcode.EVT, headers)
        self.assertIn(Opcode.RET, headers)

    def test_cancel_unknown_task_is_not_found(self):
        result = CoordinatorAgent().cancel(TALFrame(Opcode.CMD, "c0", "r1", "halt", "id='missing'", "", "c1"))
        self.assertEqual(result.header, Opcode.ERR)
        self.assertIn(ErrorCode.NOT_FOUND.value, result.payload)


class TALParserRoundTripHelper:
    @staticmethod
    def child_frame():
        return TALFrame(Opcode.CMD, "r1", "r2", "read", "path='spec.md',parent=a7", "!", "b1", "a7")


if __name__ == "__main__":
    unittest.main()
