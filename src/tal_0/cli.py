"""Command-line interface for the TAL-0 deterministic runtime."""

from __future__ import annotations

import argparse

from .agents import CoordinatorAgent
from .benchmark import TokenBenchmark


NATURAL_TRACE = (
    "I will investigate the security advisory. First I will command the research agent "
    "to search for auth_cve. The research agent finds CVE-2026-9041. Then I will ask the "
    "sandbox agent to run min(100, 50). The result is 50 and the audit passes."
)
JSON_TRACE = (
    '{"thought":"plan","command":{"from":"c0","to":"r1","action":"find_vector","query":"auth_cve"},'
    '"return":{"from":"r1","result":"CVE-2026-9041"},"command":{"to":"e1",'
    '"action":"exec_python","code":"min(100,50)"},"return":{"out":50},"final":"passed"}'
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the TAL-0 deterministic multi-agent demo.")
    parser.add_argument(
        "objective",
        nargs="?",
        default="Investigate auth_cve and test min(100, 50)",
        help="Objective sent to the coordinator.",
    )
    args = parser.parse_args(argv)

    trace = CoordinatorAgent().run(args.objective)
    print("TAL-0 runtime")
    print("==============")
    for frame in trace:
        print(frame.serialize())

    benchmark = TokenBenchmark.compare(NATURAL_TRACE, JSON_TRACE, "".join(f.serialize() for f in trace))
    print("\nToken benchmark (dependency-free approximation)")
    print("-----------------------------------------------")
    print(TokenBenchmark.render_table(benchmark))
    return 0
