"""Verified WSOL-pool reserve feed for clearly labelled paper fills.

This is not a Pump.fun bonding-curve decoder. It reads a DexScreener AMM pair
whose quote mint is wrapped SOL, verifies mint decimals through Solana RPC,
and converts the reported pool reserves into the constant-product snapshot
consumed by PaperAdapter. Missing, stale, mismatched, or non-WSOL data fails
closed.
"""
from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from pumpgrok.execution.paper_adapter.models import CurveSnapshot

WSOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = Decimal(1_000_000_000)


class DexPoolPriceSource:
    """Read actual WSOL/base reserves from DexScreener and verify token decimals."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        rpc_url: str,
        *,
        max_age_seconds: int = 45,
    ) -> None:
        self._client = client
        self._rpc_url = rpc_url
        self._max_age_seconds = max_age_seconds

    async def _token_decimals(self, mint: str) -> int | None:
        response = await self._client.post(
            self._rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            },
        )
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            return None
        value = ((body.get("result") or {}).get("value") or {})
        parsed = (((value.get("data") or {}).get("parsed") or {}).get("info") or {})
        if parsed.get("mintAuthority", "missing") == "missing":
            return None
        try:
            decimals = int(parsed.get("decimals"))
        except (TypeError, ValueError):
            return None
        return decimals if 0 <= decimals <= 18 else None

    async def curve(self, mint: str) -> CurveSnapshot | None:
        if not mint or mint == WSOL_MINT:
            return None
        try:
            response = await self._client.get(
                f"https://api.dexscreener.com/tokens/v1/solana/{mint}"
            )
            response.raise_for_status()
            payload: Any = response.json()
            if not isinstance(payload, list):
                return None
            pairs = [
                pair for pair in payload
                if isinstance(pair, dict)
                and pair.get("chainId") == "solana"
                and (pair.get("baseToken") or {}).get("address") == mint
                and (pair.get("quoteToken") or {}).get("address") == WSOL_MINT
            ]
            if not pairs:
                return None
            pair = max(
                pairs,
                key=lambda row: Decimal(str((row.get("liquidity") or {}).get("usd") or 0)),
            )
            liquidity = pair.get("liquidity") or {}
            base = Decimal(str(liquidity.get("base") or 0))
            quote = Decimal(str(liquidity.get("quote") or 0))
            native_price = Decimal(str(pair.get("priceNative") or 0))
            if not base.is_finite() or not quote.is_finite() or base <= 0 or quote <= 0:
                return None
            if not native_price.is_finite() or native_price <= 0:
                return None
            decimals = await self._token_decimals(mint)
            if decimals is None:
                return None
            token_units = int(base * (Decimal(10) ** decimals))
            sol_lamports = int(quote * LAMPORTS_PER_SOL)
            if token_units <= 0 or sol_lamports <= 0:
                return None
            reserve_price = Decimal(sol_lamports) / Decimal(token_units)
            relative_error = abs(reserve_price - native_price) / native_price
            if relative_error > Decimal("0.15"):
                return None
            return CurveSnapshot(
                mint=mint,
                s_lamports=sol_lamports,
                t_units=token_units,
                complete=False,
                source="dexscreener_wsol_pool",
                ts=time.time(),
            )
        except (httpx.HTTPError, ValueError, TypeError, InvalidOperation, KeyError):
            return None
