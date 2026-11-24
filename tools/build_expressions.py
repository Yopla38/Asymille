#!/usr/bin/env python3
"""Write tests/data/expressions.json: expressions and the values asymille/expressions.py gives them.

    uv run python tools/build_expressions.py

tools/check_page.js then asks the page's own parser (page/js/expr.js) for the same values: the
formula of a column and a custom fit function are read by two parsers that must agree.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT)]

from asymille.expressions import Expression, ExpressionError  # noqa: E402

ENV = {"x": 1.7, "a": 2.5, "b": -0.75, "tau": 3.0, "A": 4.0, "B": 9.0, "i": 3.0, "n": 10.0, "x0": 0.3}
TEXTS = [
    "1 + 2*3", "2^3^2", "-2^2", "(-2)^2", "2**-1", "-x^2", "a - b - 1", "a/b/2", "a*-b", "1e3 + 1.5E-2 + .5", "a*exp(-x/tau) + b", "sqrt(abs(b)) + ln(a) + log(a) + log10(100) + log2(8)",
    "sin(x)^2 + cos(x)^2", "tan(x) - sinh(x) + cosh(x) - tanh(x)", "asin(0.5) + acos(0.5) + atan(x) + atan2(a, b)", "min(a, b) + max(a, b)*pow(a, 2)", "pi*e", "erf(x) + erfc(x)",
    "heaviside(b) + heaviside(a) + heaviside(0)", "floor(a) + ceil(a) + sign(b)", "A*2 + sqrt(B) - i/n", "((a))", "+a", "a*(b + x0)^2", "1/0", "sqrt(b)", "9^9^9^9", "10*log10(B) + 30",
]
REFUSED = ["", "2x", "2 x", "a +* b", "f(x)", "sin", "sin(1, 2)", "exp()", "a.b", "a[0]", "'a'", "a ? b : c", "a; b", "(a", "a)", "a,b", "__import__('os')", "a = 1", "lambda: 1", "a < b",
           # what the formula of a column reads in the page, and a fit function must not: both refuse it here
           "mean(a)", "a[1]", "if(a > 1, a, b)", "a and b", "max(a)"]

values = []
for text in TEXTS:
    v = float(Expression(text)(ENV))
    values.append({"text": text, "value": v if math.isfinite(v) else None})
for text in REFUSED:
    try:
        Expression(text)
    except ExpressionError:
        continue
    raise SystemExit(f"asymille/expressions.py accepts {text!r}: it must not")
(ROOT / "tests" / "data" / "expressions.json").write_text(json.dumps({"env": ENV, "values": values, "refused": REFUSED}, indent=1) + "\n")
print(f"tests/data/expressions.json: {len(values)} expressions, {len(REFUSED)} refused")
