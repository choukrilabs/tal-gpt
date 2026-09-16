import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import unittest

from tal_0.agents import CoordinatorAgent, SubAgent
from tal_0.benchmark import TokenBenchmark
from tal_0.client import GeminiLLMClient
from tal_0.core import Opcode, TALFrame
from tal_0.tools import ToolRegistry


class RuntimeTests(unittest.TestCase):
    def test_vector_tool_returns_fixture_hit(self):
        result = ToolRegistry.default().execute("find_vector", q="auth_cve", limit=1)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output, ["CVE-2026-9041"])

    def test_python_tool_evaluates_safe_expression(self):
        result = ToolRegistry.default().execute("exec_python", code="min(100, 50)")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output, 50)

    def test_unknown_tool_returns_error(self):
        result = ToolRegistry.default().execute("does_not_exist")
        self.assertEqual(result.status, "error")

    def test_coordinator_runs_plan_command_return_eval(self):
        coordinator = CoordinatorAgent()
        trace = coordinator.run("Investigate auth_cve and test min(100, 50)")
        headers = [frame.header for frame in trace]
        self.assertEqual(headers[:2], [Opcode.THK, Opcode.CMD])
        self.assertIn(Opcode.RET, headers)
        self.assertTrue(any(frame.header == Opcode.THK and frame.action == "eval" for frame in trace))
        self.assertIn("CVE-2026-9041", trace[-1].payload)
        self.assertIn("50", trace[-1].payload)

    def test_subagent_returns_structured_result(self):
        subagent = SubAgent("e1", "sandbox", ToolRegistry.default())
        result = subagent.handle(TALFrame(Opcode.CMD, "c0", "e1", "exec/py", "code='min(100,50)'") )
        self.assertEqual(result.header, Opcode.RET)
        self.assertIn("50", result.payload)

    def test_client_without_key_uses_deterministic_fallback(self):
        client = GeminiLLMClient(api_key=None)
        result = client.generate("demo")
        self.assertIn("TAL-0", result)
        self.assertIn("fallback", result.lower())

    def test_benchmark_counts_nonempty_text(self):
        self.assertGreater(TokenBenchmark.count("abc"), 0)

    def test_benchmark_reports_savings(self):
        results = TokenBenchmark.compare("one two three four", "one two", "one")
        self.assertLess(results["tal_tokens"], results["natural_tokens"])
        self.assertGreater(results["savings_vs_natural_pct"], 0)


if __name__ == "__main__":
    unittest.main()
