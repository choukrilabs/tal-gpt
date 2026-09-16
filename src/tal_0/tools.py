"""Explicit tool registry and side-effect-limited built-ins."""

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


class _SafeExpression:
    _binops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _cmpops = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
    _functions = {"min": min, "max": max, "abs": abs, "round": round}

    @classmethod
    def evaluate(cls, source: str) -> Any:
        tree = ast.parse(source, mode="eval")
        return cls._eval(tree.body)

    @classmethod
    def _eval(cls, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
            return node.value
        if isinstance(node, ast.List):
            return [cls._eval(x) for x in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(cls._eval(x) for x in node.elts)
        if isinstance(node, ast.Dict):
            return {cls._eval(k): cls._eval(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = cls._eval(node.operand)
            return +value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in cls._binops:
            left, right = cls._eval(node.left), cls._eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent exceeds sandbox limit")
            return cls._binops[type(node.op)](left, right)
        if isinstance(node, ast.Compare):
            left = cls._eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                if type(op) not in cls._cmpops:
                    raise ValueError("comparison is not permitted")
                right = cls._eval(comparator)
                if not cls._cmpops[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in cls._functions:
            if node.keywords:
                raise ValueError("keyword arguments are not permitted")
            return cls._functions[node.func.id](*[cls._eval(arg) for arg in node.args])
        raise ValueError("expression contains a disallowed construct")


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        if not name or not callable(handler):
            raise ValueError("tool name must be non-empty and handler callable")
        self._handlers[name] = handler

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(status="error", error=f"unknown_tool:{name}")
        try:
            return ToolResult(status="ok", output=handler(**kwargs))
        except Exception as exc:
            return ToolResult(status="error", error=f"tool_error:{type(exc).__name__}:{exc}")

    @classmethod
    def default(cls) -> "ToolRegistry":
        registry = cls()
        registry.register("find_vector", _find_vector)
        registry.register("exec_python", _exec_python)
        registry.register("assert_equal", _assert_equal)
        return registry


def _find_vector(q: str, limit: int = 5) -> list[str]:
    fixtures = {
        "auth_cve": ["CVE-2026-9041"],
        "token_leak": ["CVE-2026-9041", "jwt.py"],
    }
    return fixtures.get(str(q).strip().lower(), [])[: max(0, int(limit))]


def _exec_python(code: str) -> Any:
    if len(code) > 500:
        raise ValueError("sandbox expression exceeds 500 characters")
    return _SafeExpression.evaluate(code)


def _assert_equal(expected: Any, actual: Any) -> bool:
    if expected != actual:
        raise AssertionError(f"expected={expected!r},actual={actual!r}")
    return True
