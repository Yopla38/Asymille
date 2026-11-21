"""The NIST StRD nonlinear regression datasets kept in tests/data: their data, starting values and certified results.

https://www.itl.nist.gov/div898/strd/nls/nls_main.shtml (public domain). The files are as NIST publishes them.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

DATA = Path(__file__).resolve().parent / "data"
NUMBER = r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?"


def load(name: str) -> dict[str, Any]:
    lines = (DATA / f"{name}.dat").read_text().splitlines()
    certified, starts = {}, {}
    for line in lines:
        m = re.match(rf"\s*(b\d+)\s*=\s*({NUMBER})\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})", line)
        if m:
            starts[m.group(1)] = (float(m.group(2)), float(m.group(3)))
            certified[m.group(1)] = (float(m.group(4)), float(m.group(5)))
    first = next(i for i, line in enumerate(lines) if line.startswith("Data:") and "y" in line and "x" in line and i > 40)
    table = np.array([[float(v) for v in line.split()] for line in lines[first + 1:] if line.strip()])
    rss = float(next(re.search(NUMBER + r"$", line.strip()).group(0) for line in lines if line.startswith("Residual Sum of Squares")))  # type: ignore[union-attr]
    return {"x": table[:, 1], "y": table[:, 0], "certified": certified, "starts": starts, "rss": rss}
