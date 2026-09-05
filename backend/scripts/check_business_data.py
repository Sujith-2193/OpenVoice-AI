"""Smoke-test the persistent business-data layer.

Run from the backend directory with a reachable MongoDB instance:
    uv run python scripts/check_business_data.py
"""

from src.data.store import get_store


def main() -> None:
    store = get_store()
    products = store.search_products("red shirt")
    order = store.get_order("latest")
    policy = store.get_policy("returns")

    assert products, "catalog returned no products"
    assert order and order.get("order_id"), "latest order is missing"
    assert policy, "returns policy is missing"

    print("business data smoke check: PASS")
    print(f"products: {len(products)}")
    print(f"latest order: {order['order_id']}")
    print(f"returns policy: {policy}")


if __name__ == "__main__":
    main()
