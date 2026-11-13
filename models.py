# models.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Product:
    id: str
    query: str
    target_price: float
    enabled: bool
    created_at: str
    catalog_product_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            id=str(data["id"]),
            query=str(data["query"]),
            target_price=float(data["target_price"]),
            enabled=bool(data.get("enabled", True)),
            created_at=str(data.get("created_at", "")),
            catalog_product_ids=list(
                data.get("catalog_product_ids")
                or ([data["catalog_product_id"]] if data.get("catalog_product_id") else [])
            ),
        )
