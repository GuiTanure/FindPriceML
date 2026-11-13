"""Consulta e avaliação conservadora da reputação de vendedores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SellerEvaluation:
    approved: bool
    seller_id: str
    level_id: str | None
    power_seller_status: str | None
    reason: str
    transactions_total: int | None = None
    transactions_completed: int | None = None
    transactions_canceled: int | None = None
    ratings: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None


def _seller_evaluation_from_data(seller_id: str, data: dict[str, Any]) -> SellerEvaluation:
    reputation = data.get("seller_reputation")
    if not isinstance(reputation, dict):
        reputation = {}

    level_id = reputation.get("level_id")
    power_seller_status = reputation.get("power_seller_status")
    transactions = reputation.get("transactions") or {}
    ratings = transactions.get("ratings") if isinstance(transactions, dict) else None
    metrics = reputation.get("metrics")
    if not isinstance(metrics, dict):
        metrics = None

    total = transactions.get("total") if isinstance(transactions, dict) else None
    completed = transactions.get("completed") if isinstance(transactions, dict) else None
    canceled = transactions.get("canceled") if isinstance(transactions, dict) else None
    values = []
    for value in (total, completed, canceled):
        try:
            values.append(int(value) if value is not None else None)
        except (TypeError, ValueError):
            values.append(None)
    total, completed, canceled = values

    base = dict(
        seller_id=seller_id,
        level_id=str(level_id) if level_id is not None else None,
        power_seller_status=str(power_seller_status) if power_seller_status is not None else None,
        transactions_total=total,
        transactions_completed=completed,
        transactions_canceled=canceled,
        ratings=ratings if isinstance(ratings, dict) else None,
        metrics=metrics,
    )

    level_approved = level_id == "5_green"
    power_seller_approved = power_seller_status is not None
    approved = level_approved and power_seller_approved

    if approved:
        reason = "Aprovado: vendedor 5_green e MercadoLíder."
    else:
        reasons = []
        if not level_approved:
            reasons.append("Reprovado: reputação diferente de 5_green.")
        if not power_seller_approved:
            reasons.append("Reprovado: vendedor não possui status de MercadoLíder.")
        reason = " ".join(reasons)

    return SellerEvaluation(approved=approved, reason=reason, **base)


def evaluate_seller(api, seller_id) -> SellerEvaluation:
    """Consulta /users/{seller_id} usando a autenticação do MercadoLivreAPI."""
    normalized_seller_id = str(seller_id).strip() if seller_id is not None else ""
    if not normalized_seller_id:
        return SellerEvaluation(False, "", None, None, "Anúncio sem seller_id.")

    try:
        data = api._request("GET", f"/users/{normalized_seller_id}")
        if not isinstance(data, dict):
            raise ValueError("resposta inválida da API")
        return _seller_evaluation_from_data(normalized_seller_id, data)
    except Exception:
        return SellerEvaluation(
            approved=False,
            seller_id=normalized_seller_id,
            level_id=None,
            power_seller_status=None,
            reason="Não foi possível consultar a reputação do vendedor.",
        )
