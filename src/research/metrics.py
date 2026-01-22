# src/research/metrics.py
from __future__ import annotations

from typing import List, Optional, Tuple
import math


def mse(a: List[float], b: List[float]) -> Optional[float]:
    if not a or not b or len(a) != len(b):
        return None
    s = 0.0
    for x, y in zip(a, b):
        d = x - y
        s += d * d
    return s / float(len(a))


def mae(a: List[float], b: List[float]) -> Optional[float]:
    if not a or not b or len(a) != len(b):
        return None
    s = 0.0
    for x, y in zip(a, b):
        s += abs(x - y)
    return s / float(len(a))


def pearson_r(a: List[float], b: List[float]) -> Optional[float]:
    """
    Pearson correlation coefficient between two equal-length lists.
    Useful for "agreement" between model per-distance score and heuristic delta profile.
    """
    if not a or not b or len(a) != len(b):
        return None
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    num = 0.0
    da = 0.0
    db = 0.0
    for x, y in zip(a, b):
        xa = x - ma
        yb = y - mb
        num += xa * yb
        da += xa * xa
        db += yb * yb
    if da <= 1e-12 or db <= 1e-12:
        return None
    return num / math.sqrt(da * db)


def topk_overlap(a: List[float], b: List[float], k: int = 20) -> Optional[float]:
    """
    Measures overlap between top-k indices of two score arrays.
    Useful for "error localization along lap distance": do the same bins light up?
    Returns overlap ratio in [0,1].
    """
    if not a or not b or len(a) != len(b) or k <= 0:
        return None
    k = min(k, len(a))
    ia = sorted(range(len(a)), key=lambda i: a[i], reverse=True)[:k]
    ib = sorted(range(len(b)), key=lambda i: b[i], reverse=True)[:k]
    sa = set(ia)
    sb = set(ib)
    return len(sa & sb) / float(k)
