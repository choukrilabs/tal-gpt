"""Explicit, dependency-free tool registry with a restricted Python evaluator."""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class ToolResult:
    status: str
    output: Any = None
    error: Optional[str] = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., ToolResult]] = {}

    @classmethod
    def default(cls) -> "ToolRegistry":
        registry = cls()
        registry.register("find_vector", registry.find_vector)
        registry.register("exec_python", registry.exec_python)
        registry.register("assert_equal", registry.assert_equal)
        return registry

    def register(self, name: str, function: Callable[..., ToolResult]) -> None:
        if not name or "/" in name:
            raise ValueError("tool name must be a non-empty local identifier")
        self._tools[name] = function

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        function = self._tools.get(name)
        if function is None:
            return ToolResult("error", error=f"unknown tool:{name}")
        try:
            return function(**kwargs)
        except Exception as exc:
            return ToolResult("error", error=str(exc))

    @staticmethod
    def find_vector(q: str, limit: int = 5) -> ToolResult:
        corpus = {
            "auth": ["TAL-1 is a coordination protocol", "Prefer native authorization boundaries"],
            "authentication": ["Authentication remains a host responsibility"],
            "auth_cve": ["fixture:CVE-DEMO-0001 in jwt_handler.py"],
        }
        hits = corpus.get(q.lower(), [])[: max(0, min(limit, 20))]
        return ToolResult("ok", hits)

    @staticmethod
    def exec_python(code: str) -> ToolResult:
        if code.strip() == "timeout":
            return ToolResult("error", error="timeout: simulated tool timeout")
        try:
            tree = ast.parse(code, mode="eval")
            evaluator = _SafeEvaluator()
            return ToolResult("ok", evaluator.eval(tree.body))
        except Exception as exc:
            return ToolResult("error", error=f"python:{exc}")

    @staticmethod
    def assert_equal(expected: Any, actual: Any) -> ToolResult:
        if expected == actual:
            return ToolResult("ok", True)
        return ToolResult("error", error=f"assertion failed: expected={expected!r}, actual={actual!r}")


class _SafeEvaluator(ast.NodeVisitor):
    _binops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    def eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
            return node.value
        if isinstance(node, ast.List):
            return [self.eval(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self.eval(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return {self.eval(k): self.eval(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._unary:
            return self._unary[type(node.op)](self.eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in self._binops:
            return self._binops[type(node.op)](self.eval(node.left), self.eval(node.right))
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = self.eval(node.left), self.eval(node.comparators[0])
            op = node.ops[0]
            comparisons = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
            if type(op) in comparisons:
                return comparisons[type(op)](left, right)
        if isinstance(node, ast.BoolOp):
            vals = [self.eval(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(vals)
            if isinstance(node.op, ast.Or):
                return any(vals)
        if isinstance(node, ast.IfExp):
            return self.eval(node.body if self.eval(node.test) else node.orelse)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"min", "max", "abs", "round", "sum", "len"}:
            fn = {"min": min, "max": max, "abs": abs, "round": round, "sum": sum, "len": len}[node.func.id]
            return fn(*(self.eval(arg) for arg in node.args))
        if isinstance(node, ast.NameConstant):
            return node.value
        raise ValueError(f"unsupported expression:{ast.dump(node, include_attributes=False)}")
