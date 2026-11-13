from __future__ import annotations

import json
from pathlib import Path

from config import ConfigurationError


DEFAULT_BLOCKED_SELLERS_PATH = Path("data/blocked_sellers.json")


def load_blocked_seller_ids(path: Path | str = DEFAULT_BLOCKED_SELLERS_PATH) -> frozenset[str]:
    blocked_path = Path(path)
    if not blocked_path.exists():
        return frozenset()

    try:
        with blocked_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Não foi possível ler {blocked_path}: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("seller_ids"), list):
        raise ConfigurationError(
            f"Formato inválido em {blocked_path}: esperado um objeto com a lista 'seller_ids'."
        )

    seller_ids = set()
    for seller_id in data["seller_ids"]:
        normalized_seller_id = str(seller_id).strip()
        if normalized_seller_id:
            seller_ids.add(normalized_seller_id)
    return frozenset(seller_ids)
