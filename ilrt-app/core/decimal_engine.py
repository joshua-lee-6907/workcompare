from __future__ import annotations

from decimal import Decimal, getcontext
from dataclasses import dataclass


@dataclass
class ComputeResult:
    expression: str
    value: Decimal


class DecimalEngine:
    """Core compute class using configurable Decimal precision."""

    def __init__(self, precision: int = 60) -> None:
        self.set_precision(precision)

    def set_precision(self, precision: int) -> None:
        precision = max(10, int(precision))
        self.precision = precision
        getcontext().prec = precision

    def evaluate(self, left: str, op: str, right: str) -> ComputeResult:
        a = Decimal(left)
        b = Decimal(right)
        if op == "+":
            v = a + b
        elif op == "-":
            v = a - b
        elif op == "*":
            v = a * b
        elif op == "/":
            v = a / b
        else:
            raise ValueError(f"Unsupported op: {op}")
        return ComputeResult(f"{left} {op} {right}", v)
