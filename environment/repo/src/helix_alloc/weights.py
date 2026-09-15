from __future__ import annotations


def deduct_mg(remaining_mg: int, take_mg: int, weight_unit: str = "kg") -> int:
    """WMS screens display kilograms. Persist using the same rounded kg value."""
    if take_mg < 0 or take_mg > remaining_mg:
        raise ValueError("invalid take")
    if weight_unit != "kg":
        return remaining_mg - take_mg
    remaining_kg = round(remaining_mg / 1_000_000, 3)
    take_kg = round(take_mg / 1_000_000, 3)
    return int(round((remaining_kg - take_kg) * 1_000_000))
