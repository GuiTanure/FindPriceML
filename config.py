# config.py
"""Configuration, credentials, and product persistence for the MVP."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from models import Product


class ConfigurationError(ValueError):
    """Raised when local configuration or credentials are invalid."""


def parse_price(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        price = float(value)
    else:
        text = value.strip().replace("R$", "").replace(" ", "")
        if not text:
            raise ConfigurationError("O preço não pode ser vazio.")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        elif text.count(".") > 1:
            text = text.replace(".", "")
        try:
            price = float(text)
        except ValueError as exc:
            raise ConfigurationError("Preço inválido.") from exc
    if price <= 0:
        raise ConfigurationError("O preço deve ser maior que zero.")
    return price


def product_id(query: str) -> str:
    normalized = unicodedata.normalize("NFKD", query)
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or "produto"


class ConfigStore:
    def __init__(self, path: Path | str = "data/config.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save({"settings": {"search_limit": 50, "max_search_pages": 10}, "products": []})

    def load(self) -> dict:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Não foi possível ler {self.path}: {exc}") from exc
        data.setdefault("settings", {})
        data["settings"].setdefault("search_limit", 50)
        data["settings"].setdefault("max_search_pages", 10)
        data.setdefault("products", [])
        return data

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporary.replace(self.path)

    def products(self) -> list[Product]:
        return [Product.from_dict(item) for item in self.load()["products"]]

    def add_product(self, query: str, target_price: float, catalog_product_ids: list[str] | None = None) -> Product:
        query = query.strip()
        if not query:
            raise ConfigurationError("A busca não pode ser vazia.")
        target_price = parse_price(target_price)
        data = self.load()
        new_id = product_id(query)
        if any(item.get("id") == new_id for item in data["products"]):
            raise ConfigurationError("Já existe um produto com essa busca.")
        product = Product(
            id=new_id,
            query=query,
            target_price=target_price,
            enabled=True,
            created_at=datetime.now().isoformat(timespec="seconds"),
            catalog_product_ids=[str(value).strip() for value in (catalog_product_ids or []) if str(value).strip()],
        )
        data["products"].append(asdict(product))
        self.save(data)
        return product

    def remove_product(self, product_id_value: str) -> bool:
        data = self.load()
        before = len(data["products"])
        data["products"] = [item for item in data["products"] if item.get("id") != product_id_value]
        if len(data["products"]) == before:
            return False
        self.save(data)
        return True

    def credentials(self) -> dict[str, str]:
        load_dotenv()
        values = {
            "client_id": os.getenv("ML_CLIENT_ID", "").strip(),
            "client_secret": os.getenv("ML_CLIENT_SECRET", "").strip(),
            "redirect_uri": os.getenv("ML_REDIRECT_URI", "").strip(),
            "access_token": "",
            "refresh_token": "",
        }
        token_path = self.path.parent / "tokens.json"
        if token_path.exists():
            try:
                with token_path.open("r", encoding="utf-8") as file:
                    saved = json.load(file)
                values["access_token"] = saved.get("access_token", values["access_token"])
                values["refresh_token"] = saved.get("refresh_token", values["refresh_token"])
                values["expires_in"] = saved.get("expires_in")
                values["obtained_at"] = saved.get("obtained_at")
            except (OSError, json.JSONDecodeError) as exc:
                raise ConfigurationError(f"Não foi possível ler {token_path}: {exc}") from exc
        missing = [key for key in ("client_id", "client_secret", "redirect_uri") if not values[key]]
        if missing:
            raise ConfigurationError("Credenciais ausentes: " + ", ".join(missing))
        return values

    def save_tokens(self, access_token: str, refresh_token: str | None, expires_in: int | None = None, obtained_at: int | None = None) -> None:
        token_path = self.path.parent / "tokens.json"
        data = {"access_token": access_token, "obtained_at": obtained_at or int(datetime.now().timestamp())}
        if refresh_token:
            data["refresh_token"] = refresh_token
        if expires_in is not None:
            data["expires_in"] = expires_in
        temporary = token_path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
            file.write("\n")
        temporary.replace(token_path)
