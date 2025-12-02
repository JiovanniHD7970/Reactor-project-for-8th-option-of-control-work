from __future__ import annotations

import sys
from ctypes import CDLL, c_double
from pathlib import Path
from typing import Dict, List, Optional


_BASE_DIR = Path(__file__).resolve().parent
_LIB: Optional[CDLL] = None


def _candidate_library_names() -> List[str]:
    if sys.platform.startswith("win"):
        return ["reactor_model.dll"]
    if sys.platform == "darwin":
        return ["libreactor_model.dylib"]
    return ["libreactor_model.so", "reactor_model.so"]


def load_library() -> CDLL:
    """Load reactor_model dynamic library from the app directory."""
    global _LIB
    if _LIB is not None:
        return _LIB

    for name in _candidate_library_names():
        path = _BASE_DIR / name
        if not path.exists():
            continue

        lib = CDLL(str(path))
        lib.compute_CB.argtypes = [c_double, c_double, c_double, c_double, c_double]
        lib.compute_CB.restype = c_double

        _LIB = lib
        return lib

    raise FileNotFoundError(
        "reactor_model library not found. Place reactor_model.dll next to app.exe."
    )


def compute_CB(Q: float, CA_in: float, k1: float, k2: float, Vr: float) -> float:
    """Compute CB using the C library."""
    lib = load_library()
    return float(lib.compute_CB(Q, CA_in, k1, k2, Vr))


def sweep_CB(
    k1: float, k2: float, Vr: float,
    Q_min: float, Q_max: float, dQ: float,
    CAin_min: float, CAin_max: float, dCAin: float,
) -> List[Dict[str, float]]:
    """Compute CB for a grid of Q and CA_in values."""
    if dQ <= 0 or dCAin <= 0:
        raise ValueError("dQ and dCAin must be positive")

    results: List[Dict[str, float]] = []
    eps = 1e-9

    q = Q_min
    while q <= Q_max + eps:
        ca = CAin_min
        while ca <= CAin_max + eps:
            results.append({"Q": q, "CA_in": ca, "CB": compute_CB(q, ca, k1, k2, Vr)})
            ca += dCAin
        q += dQ

    return results