"""Bloom Solana swap request construction and response validation.

This module deliberately contains no strategy or candidate selection. Callers must
complete their own risk and token-safety gates before invoking the execution client.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

BLOOM_SOLANA_BASE = "https://eu.solana.bloombot.app/api/v1"
_MINT_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class BloomExecutionError(RuntimeError):
    """A Bloom request was rejected or its outcome could not be verified."""


def validate_mint(mint: str) -> str:
    value = str(mint).strip()
    if not _MINT_RE.fullmatch(value):
        raise ValueError("invalid Solana mint")
    return value


def select_spot_wallet(wallets_payload: dict[str, Any]) -> str:
    rows = wallets_payload.get("data", {}).get("wallets", [])
    if not isinstance(rows, list):
        raise BloomExecutionError("Bloom wallet response has no wallet list")
    active = [
        row for row in rows
        if isinstance(row, dict) and row.get("spot_active") and row.get("address")
    ]
    if len(active) != 1:
        raise BloomExecutionError(
            f"expected exactly one spot-active Bloom wallet; found {len(active)}"
        )
    return str(active[0]["address"])


def build_swap_payload(
    *,
    mint: str,
    side: str,
    wallet_address: str,
    amount: float,
    max_buy_sol: float = 0.01,
    take_profit_pct: float = 10.0,
    stop_loss_pct: float = -5.0,
) -> dict[str, Any]:
    """Build a bounded single-wallet Bloom swap; SELL amount is percent of holdings."""
    mint = validate_mint(mint)
    if not wallet_address or len(wallet_address) < 32:
        raise ValueError("invalid Bloom wallet address")
    normalized_side = side.strip().capitalize()
    if normalized_side not in {"Buy", "Sell"}:
        raise ValueError("side must be Buy or Sell")
    if normalized_side == "Buy":
        if not 0 < amount <= max_buy_sol:
            raise ValueError(f"buy amount must be greater than 0 and at most {max_buy_sol} SOL")
        payload: dict[str, Any] = {
            "address": mint,
            "side": "Buy",
            "wallets": [{"address": wallet_address, "amount": f"{amount:.9f}"}],
            "slippage": 5,
            "priority_fee": 0.0005,
            "processor_tip": 0.0001,
            "anti_mev": True,
            "auto_tip": False,
            "skip_if_bought": True,
            "auto_orders": [
                {
                    "target_type": "percentage",
                    "target_value": take_profit_pct,
                    "amount": 100,
                    "slippage": 5,
                    "priority_fee": 0.0005,
                    "anti_mev": True,
                },
                {
                    "target_type": "percentage",
                    "target_value": stop_loss_pct,
                    "amount": 100,
                    "slippage": 5,
                    "priority_fee": 0.0005,
                    "anti_mev": True,
                },
            ],
        }
        return payload

    if not 1 <= amount <= 100:
        raise ValueError("sell amount must be between 1 and 100 percent")
    return {
        "address": mint,
        "side": "Sell",
        "wallets": [{"address": wallet_address, "amount": f"{amount:g}"}],
        "sell_mode": "percent",
        "slippage": 5,
        "priority_fee": 0.0005,
        "processor_tip": 0.0001,
        "anti_mev": True,
        "auto_tip": False,
    }


def submit_swap(
    *,
    api_key: str,
    payload: dict[str, Any],
    timeout: float = 25.0,
) -> dict[str, Any]:
    """Submit one request to Bloom. A 200 response is SUBMITTED, not chain-confirmed."""
    if not api_key.strip():
        raise BloomExecutionError("BLOOM_API_KEY is not configured")
    response = httpx.post(
        f"{BLOOM_SOLANA_BASE}/swap",
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or result.get("success") is not True:
        raise BloomExecutionError("Bloom did not accept the swap")
    data = result.get("data") or {}
    signatures = data.get("signatures") or []
    if data.get("skipped") or not signatures:
        raise BloomExecutionError("Bloom skipped the swap or returned no transaction signature")
    return {
        "success": True,
        "order_id": data.get("order_id"),
        "signatures": signatures,
        "skipped": False,
        "confirmation": "submitted; final Solana confirmation must be checked",
    }
