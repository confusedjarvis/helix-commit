from __future__ import annotations


def sku_compatible(lot_sku: str, order_sku: str, table: dict[str, list[str]]) -> bool:
    if lot_sku == order_sku:
        return True
    return order_sku in table.get(lot_sku, [])
