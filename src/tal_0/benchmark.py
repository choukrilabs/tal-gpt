"""Dependency-free trace-size benchmark helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    tokens: int


class TokenBenchmark:
    @staticmethod
    def approximate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    @classmethod
    def compare(cls, natural: str, structured: str, tal: str) -> Dict[str, BenchmarkResult]:
        return {
            "Natural language": BenchmarkResult("Natural language", cls.approximate_tokens(natural)),
            "Structured": BenchmarkResult("Structured", cls.approximate_tokens(structured)),
            "TAL-1": BenchmarkResult("TAL-1", cls.approximate_tokens(tal)),
        }

    @staticmethod
    def savings(baseline: BenchmarkResult, candidate: BenchmarkResult) -> float:
        if baseline.tokens == 0:
            return 0.0
        return (baseline.tokens - candidate.tokens) / baseline.tokens * 100.0

    @staticmethod
    def render_table(results: Dict[str, BenchmarkResult]) -> str:
        lines = ["Paradigm            Tokens", "---------------------------"]
        for key in ("Natural language", "Structured", "TAL-1"):
            result = results[key]
            lines.append(f"{result.name:<19} {result.tokens:>6}")
        return "\n".join(lines)
