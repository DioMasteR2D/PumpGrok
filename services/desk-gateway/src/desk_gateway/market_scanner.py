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


# Shared market-home snapshot cache: the Android home and Market tab reuse one
# provider snapshot instead of multiplying upstream requests during navigation.
_HOME_CACHE_LOCK = __import__("threading").Lock()
_HOME_CACHE: dict[str, Any] = {"at": 0.0, "value": None}


def _agent_market_decisions(row: dict[str, Any]) -> list[dict[str, str]]:
    """Transparent rule-based agent assessments; never pretend an LLM ran."""
    volume = row.get("volume_24h_usd")
    liquidity = row.get("liquidity_usd")
    change_1h = row.get("price_change_1h_pct")
    ratio = (volume / liquidity) if isinstance(volume, (int, float)) and isinstance(liquidity, (int, float)) and liquidity > 0 else None
    discovered = "PumpPortal" in row.get("source", [])
    momentum = (isinstance(change_1h, (int, float)) and change_1h >= 5) or (ratio is not None and ratio >= 1.0)
    return [
        {"agent": "SCOUT", "decision": "NEW TOKEN" if discovered else "TRENDING POOL", "reason": "Live discovery feed" if discovered else "GeckoTerminal trending/new-pool feed"},
        {"agent": "SIGNAL", "decision": "MOMENTUM WATCH" if momentum else "NO CONFIRMED MOMENTUM", "reason": f"1h change={change_1h if change_1h is not None else 'n/a'}%; 24h volume/liquidity={round(ratio, 2) if ratio is not None else 'n/a'}"},
        {"agent": "WHALE", "decision": "FLOW UNKNOWN", "reason": "Wallet-level trade flow is not connected to this snapshot"},
        {"agent": "RUG", "decision": "UNVERIFIED", "reason": "Mint/freeze authority and holder concentration not checked in this fast feed"},
        {"agent": "RISK", "decision": "BLOCK ENTRY", "reason": "Safety verification is incomplete"},
        {"agent": "SNIPER", "decision": "WAIT", "reason": "No entry while Risk gate is blocked"},
        {"agent": "EXIT", "decision": "NO POSITION CONTEXT", "reason": "No open-position signal attached to this market snapshot"},
        {"agent": "SHILL", "decision": "SENTIMENT UNKNOWN", "reason": "Social sentiment provider is not connected"},
        {"agent": "JOURNAL", "decision": "OBSERVATION ONLY", "reason": "No trade event exists for this token in the paper ledger"},
        {"agent": "CHIEF", "decision": "HOLD / WATCH", "reason": "Discovery is live; entry remains blocked pending safety checks"},
    ]


def market_home(limit: int = 20) -> dict[str, Any]:
    """Aggregate live Solana trends from GeckoTerminal, DexScreener, Jupiter and PumpPortal."""
    import copy
    from desk_gateway.market_stream import snapshot as pumpportal_snapshot

    if not 1 <= limit <= 30:
        raise ValueError("limit must be between 1 and 30")
    now = time.time()
    with _HOME_CACHE_LOCK:
        cached = _HOME_CACHE.get("value")
        if cached is not None and now - float(_HOME_CACHE.get("at", 0.0)) < 12:
            result = copy.deepcopy(cached)
            result["cache_age_ms"] = int((now - float(_HOME_CACHE["at"])) * 1000)
            return result

    started = time.time()
    rows: dict[str, dict[str, Any]] = {}
    providers: list[dict[str, Any]] = []
    errors: list[str] = []
    timeout = httpx.Timeout(7.0, connect=3.0)
    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        # GeckoTerminal supplies trend ranking and new-pool discovery. Public API
        # freshness is provider-controlled; we expose our own fetched timestamp.
        for endpoint, label, kind in (
            ("https://api.geckoterminal.com/api/v2/networks/solana/trending_pools", "GeckoTerminal", "TRENDING"),
            (GECKO_NEW_POOLS, "GeckoTerminal", "NEW POOL"),
        ):
            try:
                response = client.get(endpoint, headers={"Accept": "application/json;version=20230203"})
                response.raise_for_status()
                payload = response.json()
                included = {item.get("id"): item for item in payload.get("included", []) if isinstance(item, dict)}
                count = 0
                for pool in payload.get("data", []):
                    attrs = pool.get("attributes") or {}
                    rel = pool.get("relationships") or {}
                    base_id = (((rel.get("base_token") or {}).get("data") or {}).get("id"))
                    token = included.get(base_id, {}).get("attributes", {})
                    mint = str(token.get("address") or (base_id or "").split("_")[-1])
                    if not mint:
                        continue
                    row = rows.setdefault(mint, {
                        "mint": mint, "name": token.get("name") or attrs.get("name") or "Unknown",
                        "symbol": token.get("symbol") or "—", "pool": pool.get("id"),
                        "price_usd": _number(attrs.get("base_token_price_usd")),
                        "liquidity_usd": _number(attrs.get("reserve_in_usd")),
                        "volume_24h_usd": _number((attrs.get("volume_usd") or {}).get("h24")),
                        "market_cap_usd": _number(attrs.get("market_cap_usd") or attrs.get("fdv_usd")),
                        "price_change_1h_pct": _number((attrs.get("price_change_percentage") or {}).get("h1")),
                        "price_change_24h_pct": _number((attrs.get("price_change_percentage") or {}).get("h24")),
                        "source": [], "url": None, "trend": kind,
                    })
                    if label not in row["source"]:
                        row["source"].append(label)
                    if kind == "TRENDING":
                        row["trend"] = kind
                    count += 1
                providers.append({"name": label + " " + kind.lower(), "status": "OK", "items": count})
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                log.warning("market home provider failed: %s %s", label, kind)
                providers.append({"name": label + " " + kind.lower(), "status": "UNAVAILABLE"})
                errors.append(label + " " + kind.lower() + " unavailable")

        # DexScreener contributes newest token profiles and pair-level cross-checks.
        try:
            response = client.get(DEX_PROFILES)
            response.raise_for_status()
            profiles = response.json()
            added = 0
            for profile in profiles if isinstance(profiles, list) else []:
                if profile.get("chainId") != SOLANA:
                    continue
                mint = str(profile.get("tokenAddress") or "")
                if not mint:
                    continue
                row = rows.setdefault(mint, {
                    "mint": mint, "name": profile.get("description") or profile.get("header") or "New Solana token",
                    "symbol": "—", "pool": None, "price_usd": None, "liquidity_usd": None,
                    "volume_24h_usd": None, "market_cap_usd": None, "price_change_1h_pct": None,
                    "price_change_24h_pct": None, "source": [], "url": profile.get("url"), "trend": "NEW",
                })
                if "DexScreener" not in row["source"]:
                    row["source"].append("DexScreener")
                row["url"] = row["url"] or profile.get("url")
                added += 1
            providers.append({"name": "DexScreener profiles", "status": "OK", "items": added})
        except (httpx.HTTPError, ValueError, TypeError):
            providers.append({"name": "DexScreener profiles", "status": "UNAVAILABLE"})
            errors.append("DexScreener profiles unavailable")

        # Pair enrichment is bounded to avoid bursty calls and 429s.
        enrich = list(rows.values())[:10]
        for row in enrich:
            try:
                response = client.get(f"https://api.dexscreener.com/latest/dex/tokens/{row['mint']}")
                response.raise_for_status()
                pairs = [p for p in response.json().get("pairs", []) if p.get("chainId") == SOLANA]
                if pairs:
                    pair = max(pairs, key=lambda p: _number((p.get("liquidity") or {}).get("usd")) or 0)
                    row["price_usd"] = _number(pair.get("priceUsd")) or row.get("price_usd")
                    row["liquidity_usd"] = _number((pair.get("liquidity") or {}).get("usd")) or row.get("liquidity_usd")
                    row["volume_24h_usd"] = _number((pair.get("volume") or {}).get("h24")) or row.get("volume_24h_usd")
                    row["market_cap_usd"] = _number(pair.get("marketCap") or pair.get("fdv")) or row.get("market_cap_usd")
                    row["price_change_1h_pct"] = _number((pair.get("priceChange") or {}).get("h1")) if (pair.get("priceChange") or {}).get("h1") is not None else row.get("price_change_1h_pct")
                    row["price_change_24h_pct"] = _number((pair.get("priceChange") or {}).get("h24")) if (pair.get("priceChange") or {}).get("h24") is not None else row.get("price_change_24h_pct")
                    row["name"] = pair.get("baseToken", {}).get("name") or row["name"]
                    row["symbol"] = pair.get("baseToken", {}).get("symbol") or row["symbol"]
                    row["url"] = pair.get("url") or row.get("url")
                    if "DexScreener" not in row["source"]:
                        row["source"].append("DexScreener")
            except (httpx.HTTPError, ValueError, TypeError):
                row["price_enrichment"] = "unavailable"

        # Jupiter is a price cross-check. Missing quotes stay null, never zero.
        mints = list(rows.keys())[:30]
        if mints:
            try:
                headers = {"Accept": "application/json"}
                api_key = os.environ.get("JUPITER_API_KEY", "").strip()
                if api_key:
                    headers["x-api-key"] = api_key
                response = client.get("https://api.jup.ag/price/v3", params={"ids": ",".join(mints)}, headers=headers)
                if response.is_success:
                    price_map = response.json()
                    for mint, quote in price_map.items():
                        if mint in rows and isinstance(quote, dict) and quote.get("usdPrice") is not None:
                            rows[mint]["jupiter_price_usd"] = _number(quote.get("usdPrice"))
                            if rows[mint].get("price_usd") is None:
                                rows[mint]["price_usd"] = _number(quote.get("usdPrice"))
                            if "Jupiter" not in rows[mint]["source"]:
                                rows[mint]["source"].append("Jupiter")
                providers.append({"name": "Jupiter Price V3", "status": "OK" if response.is_success else "UNAVAILABLE"})
            except (httpx.HTTPError, ValueError, TypeError):
                providers.append({"name": "Jupiter Price V3", "status": "UNAVAILABLE"})
                errors.append("Jupiter price cross-check unavailable")

    pump = pumpportal_snapshot(80)
    pump_events = pump.get("events", [])
    pump_mints = set()
    for event in pump_events:
        if int(event.get("received_at") or 0) < int(time.time()) - 180:
            continue
        mint = str(event.get("mint") or "")
        if not mint:
            continue
        pump_mints.add(mint)
        row = rows.setdefault(mint, {
            "mint": mint, "name": event.get("name") or "New PumpPortal token",
            "symbol": event.get("symbol") or "—", "pool": event.get("pool"),
            "price_usd": None, "liquidity_usd": None, "volume_24h_usd": None,
            "market_cap_usd": None, "price_change_1h_pct": None, "price_change_24h_pct": None,
            "source": [], "url": None, "trend": "NEW LIVE",
        })
        if "PumpPortal" not in row["source"]:
            row["source"].append("PumpPortal")
        row["last_stream_event"] = event.get("received_at")
        row["stream_event_type"] = event.get("type")

    providers.append({
        "name": "PumpPortal WebSocket",
        "status": "CONNECTED" if pump.get("connected") else "RECONNECTING",
        "last_event_at": pump.get("last_event_at"),
        "reconnects": pump.get("reconnects", 0),
        "items": len(pump_events),
    })

    output = list(rows.values())
    for row in output:
        row["agents"] = _agent_market_decisions(row)
        row["entry_status"] = "BLOCKED_UNVERIFIED"
        row["paper_entry_enabled"] = False
        row["risk_gate"] = "BLOCKED · VERIFY TOKEN AUTHORITIES + HOLDERS"
        row["momentum_ratio"] = (
            round(row["volume_24h_usd"] / row["liquidity_usd"], 2)
            if isinstance(row.get("volume_24h_usd"), (int, float))
            and isinstance(row.get("liquidity_usd"), (int, float))
            and row["liquidity_usd"] > 0 else None
        )
    output.sort(
        key=lambda r: (
            1 if r["mint"] in pump_mints else 0,
            1 if r.get("trend") == "TRENDING" else 0,
            r.get("volume_24h_usd") or 0,
        ),
        reverse=True,
    )
    result = {
        "mode": "paper_only",
        "scanner": "multi_source_market_home",
        "generated_at": int(time.time()),
        "elapsed_ms": int((time.time() - started) * 1000),
        "cache_age_ms": 0,
        "candidate_count": min(len(output), limit),
        "candidates": output[:limit],
        "providers": providers,
        "pumpportal_stream": {k: v for k, v in pump.items() if k != "events"},
        "errors": errors,
        "decision_policy": "Transparent rule-based read-only agent assessments; no fabricated AI output.",
        "execution": "LOCKED · no live orders",
    }
    with _HOME_CACHE_LOCK:
        _HOME_CACHE["at"] = time.time()
        _HOME_CACHE["value"] = copy.deepcopy(result)
    return result
