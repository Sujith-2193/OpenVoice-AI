"""MongoDB-backed catalog, order, and policy store.

The voice agents call this module instead of embedding demo business data in
LLM tools. Collections are initialized lazily and seeded only when empty, so a
fresh development database is immediately usable while existing data is never
overwritten.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from dotenv import find_dotenv, load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection

load_dotenv(find_dotenv())

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "openvoice")


class BusinessDataStore:
    def __init__(self, uri: str = DATABASE_URL, database_name: str = DATABASE_NAME) -> None:
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[database_name]
        self.products: Collection[dict[str, Any]] = self.db.products
        self.orders: Collection[dict[str, Any]] = self.db.orders
        self.policies: Collection[dict[str, Any]] = self.db.policies
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self.client.admin.command("ping")
        self.products.create_index([("name", ASCENDING)])
        self.products.create_index([("category", ASCENDING)])
        self.orders.create_index([("order_id", ASCENDING)], unique=True)
        self.orders.create_index([("created_at", ASCENDING)])
        self.policies.create_index([("topic", ASCENDING)], unique=True)
        self._seed_if_empty()
        self._initialized = True

    def _seed_if_empty(self) -> None:
        if self.products.count_documents({}) == 0:
            self.products.insert_many([
                {"sku": "SHIRT-RED-01", "name": "Classic Red Shirt", "category": "shirts", "price": 20, "currency": "USD", "sizes": ["S", "M", "L", "XL"], "colors": ["red"]},
                {"sku": "JEANS-BLU-01", "name": "Slim Blue Jeans", "category": "jeans", "price": 40, "currency": "USD", "sizes": ["28", "30", "32", "34"], "colors": ["blue"]},
                {"sku": "SHOES-BLK-01", "name": "Everyday Black Shoes", "category": "shoes", "price": 60, "currency": "USD", "sizes": ["7", "8", "9", "10", "11"], "colors": ["black"]},
            ])
        if self.orders.count_documents({}) == 0:
            self.orders.insert_one({
                "order_id": "OV-10001",
                "status": "out_for_delivery",
                "estimated_delivery": "today by 8 PM",
                "items": [{"sku": "SHIRT-RED-01", "quantity": 1}],
                "created_at": datetime.now(timezone.utc),
            })
        if self.policies.count_documents({}) == 0:
            self.policies.insert_many([
                {"topic": "returns", "text": "We offer a 30-day return policy for all unused items."},
                {"topic": "shipping", "text": "Standard shipping takes 3-5 business days. Expedited shipping takes 1-2 days."},
                {"topic": "refunds", "text": "Approved refunds are issued to the original payment method."},
            ])

    def search_products(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        self.initialize()
        tokens = [token for token in query.strip().split() if token]
        if not tokens:
            return []
        pattern = "|".join(re.escape(token) for token in tokens)
        cursor = self.products.find(
            {"$or": [
                {"name": {"$regex": pattern, "$options": "i"}},
                {"category": {"$regex": pattern, "$options": "i"}},
                {"colors": {"$regex": pattern, "$options": "i"}},
            ]},
            {"_id": 0},
        ).limit(limit)
        return list(cursor)

    def get_order(self, order_id: str = "latest") -> dict[str, Any] | None:
        self.initialize()
        if order_id.lower() == "latest":
            return self.orders.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        return self.orders.find_one({"order_id": order_id.upper()}, {"_id": 0})

    def get_policy(self, topic: str) -> str | None:
        self.initialize()
        topic_lower = topic.lower()
        for policy in self.policies.find({}, {"_id": 0}):
            if policy["topic"] in topic_lower or topic_lower in policy["topic"]:
                return str(policy["text"])
        return None

    def close(self) -> None:
        self.client.close()


@lru_cache(maxsize=1)
def get_store() -> BusinessDataStore:
    return BusinessDataStore()
