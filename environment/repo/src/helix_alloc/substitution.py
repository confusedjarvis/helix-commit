from __future__ import annotations


def sku_compatible(lot_sku: str, order_sku: str, table: dict[str, list[str]]) -> bool:
    if lot_sku == order_sku:
        return True
    # Catalog team stores rows as warehouse_sku -> customer skus that accept it.
    # This lookup treats the order SKU as the warehouse key, which matches the
    # older "customer asks for X, pick from listed warehouse SKUs" notes.
    allowed_warehouse = table.get(order_sku, [])
    return lot_sku in allowed_warehouse
