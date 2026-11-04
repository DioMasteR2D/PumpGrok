"""Read-only Solana discovery scanner for the mobile paper desk.

The scanner never submits orders. It merges GeckoTerminal new pools with
DexScreener's latest token profiles, then verifies token authorities and
holder concentration through the configured Solana RPC. Missing evidence is
reported as unknown and never treated as a pass.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

log = logging.getLogger("desk_gateway.market")
SOLANA = "solana"
GECKO_NEW_POOLS = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"
DEX_PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
MIN_LIQUIDITY_USD = 40_000.0
MAX_TOP10_SHARE = 0.25


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number >= 0 and number < float("inf") else None
    except (TypeError, ValueError):
        return None


def _rpc(client: httpx.Client, url: str, method: str, params: list[Any]) -> Any:
    response = client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    response.raise_for_status()
    body = response.json()
    if body.get("error"):
        raise ValueError(f"Solana RPC {method} returned an error")
    return body.get("result")


def _verify_mint(client: httpx.Client, rpc_url: str, mint: str) -> dict[str, Any]:
    info = _rpc(client, rpc_url, "getAccountInfo", [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}])
    value = (info or {}).get("value")
    parsed = (((value or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
    if not parsed or "mintAuthority" not in parsed:
        return {"verified": False, "mint_authority_revoked": None, "freeze_authority_revoked": None, "top10_share": None, "reason": "Mint account data unavailable"}
    mint_revoked = parsed.get("mintAuthority") is None
    freeze_revoked = parsed.get("freezeAuthority") is None
    largest = _rpc(client, rpc_url, "getTokenLargestAccounts", [mint, {"commitment": "confirmed"}])
    supply = _rpc(client, rpc_url, "getTokenSupply", [mint, {"commitment": "confirmed"}])
    total = int(((supply or {}).get("value") or {}).get("amount") or 0)
    rows = ((largest or {}).get("value") or [])
    if total <= 0 or not rows:
        top10 = None
    else:
        top10 = sum(int(row.get("amount") or 0) for row in rows[:10]) / total
    return {
        "verified": True,
        "mint_authority_revoked": mint_revoked,
        "freeze_authority_revoked": freeze_revoked,
        "top10_share": top10,
        "reason": None if top10 is not None else "Holder concentration unavailable",
    }


def scan_market(limit: int = 40) -> dict[str, Any]:
    """Fetch discovery candidates and enrich with confirmed RPC safety facts."""
    started = time.time()
    rpc_url = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com").strip()
    timeout = httpx.Timeout(12.0, connect=5.0)
    candidates: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        try:
            response = client.get(GECKO_NEW_POOLS, params={"page": 1})
            response.raise_for_status()
            payload = response.json()
            included = {item.get("id"): item for item in payload.get("included", []) if isinstance(item, dict)}
            for pool in payload.get("data", []):
                attrs = pool.get("attributes") or {}
                rel = pool.get("relationships") or {}
                base_id = (((rel.get("base_token") or {}).get("data") or {}).get("id"))
                token = included.get(base_id, {}).get("attributes", {})
                mint = str(token.get("address") or (base_id or "").split("_")[-1])
                if not mint:
                    continue
                candidates[mint] = {
                    "mint": mint, "name": token.get("name") or attrs.get("name") or "Unknown",
                    "symbol": token.get("symbol") or "—", "pool": pool.get("id"),
                    "price_usd": _number(attrs.get("base_token_price_usd")),
                    "liquidity_usd": _number(attrs.get("reserve_in_usd")),
                    "volume_24h_usd": _number((attrs.get("volume_usd") or {}).get("h24")),
                    "market_cap_usd": _number(attrs.get("market_cap_usd") or attrs.get("fdv_usd")),
                    "source": ["GeckoTerminal"], "url": None,
                }
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            log.exception("GeckoTerminal discovery failed")
            errors.append("GeckoTerminal unavailable")
        try:
            response = client.get(DEX_PROFILES)
            response.raise_for_status()
            profiles = response.json()
            for profile in profiles if isinstance(profiles, list) else []:
                if profile.get("chainId") != SOLANA:
                    continue
                mint = str(profile.get("tokenAddress") or "")
                if not mint:
                    continue
                row = candidates.setdefault(mint, {
                    "mint": mint, "name": profile.get("description") or profile.get("header") or "New Solana token",
                    "symbol": "—", "pool": None, "price_usd": None, "liquidity_usd": None,
                    "volume_24h_usd": None, "market_cap_usd": None, "source": [], "url": profile.get("url"),
                })
                if "DexScreener" not in row["source"]:
                    row["source"].append("DexScreener")
                row["url"] = row["url"] or profile.get("url")
        except (httpx.HTTPError, ValueError, TypeError):
            log.exception("DexScreener discovery failed")
            errors.append("DexScreener unavailable")

        rows = list(candidates.values())[:max(1, min(limit, 100))]
        # Use DexScreener pair data as a second source for price/liquidity/volume.
        for row in rows:
            try:
                response = client.get(f"https://api.dexscreener.com/latest/dex/tokens/{row['mint']}")
                response.raise_for_status()
                pairs = [p for p in response.json().get("pairs", []) if p.get("chainId") == SOLANA]
                if pairs:
                    pair = max(pairs, key=lambda p: _number((p.get("liquidity") or {}).get("usd")) or 0)
                    row["price_usd"] = row["price_usd"] or _number(pair.get("priceUsd"))
                    row["liquidity_usd"] = row["liquidity_usd"] or _number((pair.get("liquidity") or {}).get("usd"))
                    row["volume_24h_usd"] = row["volume_24h_usd"] or _number((pair.get("volume") or {}).get("h24"))
                    row["market_cap_usd"] = row["market_cap_usd"] or _number(pair.get("marketCap") or pair.get("fdv"))
                    row["name"] = pair.get("baseToken", {}).get("name") or row["name"]
                    row["symbol"] = pair.get("baseToken", {}).get("symbol") or row["symbol"]
                    row["url"] = row["url"] or pair.get("url")
                    if "DexScreener" not in row["source"]:
                        row["source"].append("DexScreener")
            except (httpx.HTTPError, ValueError, TypeError):
                row["price_error"] = "Price enrichment unavailable"
            try:
                row["onchain"] = _verify_mint(client, rpc_url, row["mint"])
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                row["onchain"] = {"verified": False, "mint_authority_revoked": None, "freeze_authority_revoked": None, "top10_share": None, "reason": "On-chain verification unavailable"}
            liq = row.get("liquidity_usd")
            onchain = row["onchain"]
            checks = {
                "liquidity": liq is not None and liq >= MIN_LIQUIDITY_USD,
                "mint_authority": onchain.get("mint_authority_revoked") is True,
                "freeze_authority": onchain.get("freeze_authority_revoked") is True,
                "whale_concentration": onchain.get("top10_share") is not None and onchain["top10_share"] <= MAX_TOP10_SHARE,
            }
            row["checks"] = checks
            row["ai_score"] = None
            row["entry_status"] = "WAITING_FOR_AI_SCORE" if all(checks.values()) else "REJECTED_OR_UNVERIFIED"
            row["paper_entry_enabled"] = False
            row["blockers"] = [key for key, passed in checks.items() if not passed] + ["AI score provider not configured", "paper order approval pipeline not connected"]
    return {
        "mode": "paper_only",
        "scanner": "read_only",
        "generated_at": int(time.time()),
        "elapsed_ms": int((time.time() - started) * 1000),
        "candidate_count": len(rows),
        "candidates": rows,
        "errors": errors,
        "policy": {"minimum_liquidity_usd": MIN_LIQUIDITY_USD, "maximum_top10_concentration": MAX_TOP10_SHARE, "take_profit_pct_min": 70, "take_profit_pct_max": 130, "stop_loss_pct": 6, "trailing_drawdown_pct": 12, "position_equity_fraction": 0.08},
    }


def scan_market_async(limit: int = 40) -> dict[str, Any]:
    """Run blocking public HTTP/RPC discovery outside the HTTP handler thread."""
    return scan_market(limit=limit)


def search_market(query: str, limit: int = 20) -> dict[str, Any]:
    """Search public Solana DEX pairs by token name, symbol or mint; never places orders."""
    term = query.strip()
    if not term or len(term) > 100:
        raise ValueError("query must contain 1-100 characters")
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    started = time.time()
    response = httpx.get("https://api.dexscreener.com/latest/dex/search", params={"q": term}, timeout=12.0)
    response.raise_for_status()
    payload = response.json()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pair in payload.get("pairs") or []:
        if pair.get("chainId") != SOLANA:
            continue
        token = pair.get("baseToken") or {}
        mint = str(token.get("address") or "")
        if not mint or mint in seen:
            continue
        seen.add(mint)
        liquidity = _number((pair.get("liquidity") or {}).get("usd"))
        volume = _number((pair.get("volume") or {}).get("h24"))
        market_cap = _number(pair.get("marketCap") or pair.get("fdv"))
        rows.append({
            "mint": mint, "name": token.get("name") or "Unknown",
            "symbol": token.get("symbol") or "—", "pool": pair.get("pairAddress"),
            "price_usd": _number(pair.get("priceUsd")), "liquidity_usd": liquidity,
            "volume_24h_usd": volume, "market_cap_usd": market_cap,
            "source": ["DexScreener Search"], "url": pair.get("url"),
            "onchain": {"verified": False, "mint_authority_revoked": None, "freeze_authority_revoked": None, "top10_share": None, "reason": "Run scanner safety verification before considering entry"},
            "checks": {"liquidity": liquidity is not None and liquidity >= MIN_LIQUIDITY_USD, "mint_authority": False, "freeze_authority": False, "whale_concentration": False},
            "ai_score": None, "entry_status": "SEARCH_RESULT_UNVERIFIED", "paper_entry_enabled": False,
            "blockers": ["Search result only", "On-chain safety verification not run", "AI score provider not configured", "paper order approval pipeline not connected"],
        })
        if len(rows) >= limit:
            break
    return {"mode": "paper_only", "scanner": "read_only_search", "query": term, "generated_at": int(time.time()), "elapsed_ms": int((time.time() - started) * 1000), "candidate_count": len(rows), "candidates": rows, "errors": [], "policy": {"minimum_liquidity_usd": MIN_LIQUIDITY_USD, "maximum_top10_concentration": MAX_TOP10_SHARE}}
