from __future__ import annotations


def deduct_mg(remaining_mg: int, take_mg: int, weight_unit: str = "kg") -> int:
    del weight_unit
    if take_mg < 0 or take_mg > remaining_mg:
        raise ValueError("invalid take")
    return remaining_mg - take_mg
