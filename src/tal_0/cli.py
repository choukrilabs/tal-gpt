"""Command-line entry point for the TAL-1 reference runtime."""

from __future__ import annotations

from .agents import CoordinatorAgent
from .benchmark import TokenBenchmark


def main() -> int:
    coordinator = CoordinatorAgent()
    trace = coordinator.run("investigate a fixture security advisory and verify arithmetic")
    for frame in trace:
        print(frame.serialize())
    natural = "I will investigate the advisory, run the sandbox check, and report the verified result."
    structured = "[{role:thought,plan:[r1,e1]},{role:command,to:r1,action:find_vector},{role:return,result:CVE},{role:command,to:e1,action:exec_python},{role:return,out:50},{role:final,status:complete}]"
    tal = "".join(frame.serialize() for frame in trace)
    results = TokenBenchmark.compare(natural, structured, tal)
    print(TokenBenchmark.render_table(results))
    print(f"Savings vs Natural language: {TokenBenchmark.savings(results['Natural language'], results['TAL-1']):.2f}%")
    print(f"Savings vs Structured: {TokenBenchmark.savings(results['Structured'], results['TAL-1']):.2f}%")
    return 0
