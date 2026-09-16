"""Dependency-free token-count approximation and comparison utilities."""

from __future__ import annotations

import re
from typing import Dict, Union


class TokenBenchmark:
    _TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", re.UNICODE)

    @classmethod
    def count(cls, text: str) -> int:
        return len(cls._TOKEN_RE.findall(text))

    @classmethod
    def compare(cls, natural: str, structured: str, tal: str) -> Dict[str, Union[int, float]]:
        natural_tokens = cls.count(natural)
        structured_tokens = cls.count(structured)
        tal_tokens = cls.count(tal)

        def savings(base: int, value: int) -> float:
            return round((base - value) * 100.0 / base, 2) if base else 0.0

        return {
            "natural_tokens": natural_tokens,
            "structured_tokens": structured_tokens,
            "tal_tokens": tal_tokens,
            "savings_vs_natural_pct": savings(natural_tokens, tal_tokens),
            "savings_vs_structured_pct": savings(structured_tokens, tal_tokens),
        }

    @staticmethod
    def render_table(results: Dict[str, Union[int, float]]) -> str:
        rows = [
            ("Natural language", results["natural_tokens"]),
            ("Structured JSON", results["structured_tokens"]),
            ("TAL-0", results["tal_tokens"]),
            ("Savings vs natural", f"{results['savings_vs_natural_pct']:.2f}%"),
            ("Savings vs JSON", f"{results['savings_vs_structured_pct']:.2f}%"),
        ]
        width = max(len(label) for label, _ in rows)
        return "\n".join(f"  {label:<{width}}  {value}" for label, value in rows)
