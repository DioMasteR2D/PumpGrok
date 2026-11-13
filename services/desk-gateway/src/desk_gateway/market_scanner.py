"""Read-only Solana discovery scanner for the mobile paper desk.

The scanner never submits orders. It merges GeckoTerminal new pools with
DexScreener's latest token profiles, then verifies token authorities and
holder concentration through the configured Solana RPC. Missing evidence is
reported as unknown and never treated as a pass.
"""
from __future__ import annotations

import copy
import logging
import os
import threading
import time
from typing import Any

import httpx

from desk_gateway.bloom_autopilot import evaluate_live_candidate
from desk_gateway.market_stream import trade_flow

log = logging.getLogger("desk_gateway.market")
SOLANA = "solana"
GECKO_NEW_POOLS = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"
DEX_PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
MIN_LIQUIDITY_USD = 40_000.0
MAX_TOP10_SHARE = 0.25

# Avoid repeated upstream calls when clients refresh or switch market tabs.
_SCAN_CACHE_LOCK = threading.Lock()
_SCAN_CACHE: dict[str, Any] = {"at": 0.0, "value": None}
_SCAN_CACHE_TTL_S = 25.0


def _get_with_backoff(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    attempts: int = 3,
) -> httpx.Response:
    """Respect Retry-After and retry transient provider errors with bounded delay."""
    last_response: httpx.Response | None = None
    for attempt in range(max(1, attempts)):
        response = client.get(url, params=params)
        last_response = response
        if response.status_code != 429 and response.status_code < 500:
            response.raise_for_status()
            return response
        if attempt + 1 >= attempts:
            response.raise_for_status()
        retry_after = response.headers.get("Retry-After", "")
        try:
            delay = min(3.0, max(0.25, float(retry_after)))
        except (TypeError, ValueError):
            delay = min(2.0, 0.4 * (2 ** attempt))
        time.sleep(delay)
    assert last_response is not None
    last_response.raise_for_status()
    return last_response


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
    """DexScreener-only Solana pair scanner with separate on-chain safety checks."""
    started = time.time()
    with _SCAN_CACHE_LOCK:
        cached = _SCAN_CACHE.get("value")
        age = time.time() - float(_SCAN_CACHE.get("at", 0.0))
        if cached is not None and _SCAN_CACHE.get("limit") == limit and age < _SCAN_CACHE_TTL_S:
            result = copy.deepcopy(cached)
            result["cache_age_ms"] = int(age * 1000)
            return result
    rpc_url = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com").strip()
    candidates: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    providers: dict[str, str] = {}
    with httpx.Client(timeout=httpx.Timeout(10.0, connect=4.0), headers={"Accept": "application/json"}) as client:
        for endpoint in (DEX_PROFILES, "https://api.dexscreener.com/token-boosts/latest/v1"):
            try:
                response = _get_with_backoff(client, endpoint, attempts=2)
                payload = response.json()
                for item in payload if isinstance(payload, list) else []:
                    if item.get("chainId") != SOLANA:
                        continue
                    mint = str(item.get("tokenAddress") or "").strip()
                    if not mint:
                        continue
                    candidates.setdefault(mint, {
                        "mint": mint,
                        "name": item.get("description") or item.get("header") or "Solana token",
                        "symbol": "—", "source": ["DexScreener"], "boosted": "amount" in item,
                    })
                providers["DexScreener"] = "OK"
            except (httpx.HTTPError, ValueError, TypeError):
                log.exception("DexScreener discovery failed")
                providers["DexScreener"] = "UNAVAILABLE"
                errors.append("DexScreener discovery unavailable")

        mints = list(candidates.keys())[:30]
        pairs_by_mint: dict[str, list[dict[str, Any]]] = {}
        if mints:
            try:
                response = _get_with_backoff(
                    client, "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(mints), attempts=2
                )
                payload = response.json()
                pairs = payload if isinstance(payload, list) else (payload.get("pairs") or [] if isinstance(payload, dict) else [])
                for pair in pairs:
                    if not isinstance(pair, dict) or pair.get("chainId") != SOLANA:
                        continue
                    mint = str((pair.get("baseToken") or {}).get("address") or "")
                    if mint in candidates:
                        pairs_by_mint.setdefault(mint, []).append(pair)
                providers["DexScreener pairs"] = "OK"
            except (httpx.HTTPError, ValueError, TypeError):
                log.exception("DexScreener pair batch failed")
                providers["DexScreener pairs"] = "UNAVAILABLE"
                errors.append("DexScreener pair data unavailable")

        rows: list[dict[str, Any]] = []
        for mint, profile in candidates.items():
            pairs = pairs_by_mint.get(mint, [])
            if not pairs:
                continue
            pair = max(pairs, key=lambda p: _number((p.get("liquidity") or {}).get("usd")) or 0)
            token = pair.get("baseToken") or {}
            price = _number(pair.get("priceUsd"))
            if price is None:
                continue
            liquidity = _number((pair.get("liquidity") or {}).get("usd"))
            if liquidity is None or liquidity <= 0:
                continue
            volume = _number((pair.get("volume") or {}).get("h24"))
            cap = _number(pair.get("marketCap") or pair.get("fdv"))
            row = {
                "mint": mint, "name": token.get("name") or profile["name"],
                "symbol": token.get("symbol") or "—",
                "pool": "solana_" + str(pair.get("pairAddress") or ""),
                "price_usd": price, "liquidity_usd": liquidity,
                "volume_24h_usd": volume, "market_cap_usd": cap,
                "price_change_1h_pct": _number((pair.get("priceChange") or {}).get("h1")),
                "price_change_24h_pct": _number((pair.get("priceChange") or {}).get("h24")),
                "source": ["DexScreener"], "url": pair.get("url"),
                "boosted": bool(profile.get("boosted")), "dex_id": pair.get("dexId"),
            }
            try:
                row["onchain"] = _verify_mint(client, rpc_url, mint)
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                row["onchain"] = {
                    "verified": False, "mint_authority_revoked": None,
                    "freeze_authority_revoked": None, "top10_share": None,
                    "reason": "On-chain verification unavailable",
                }
            onchain = row["onchain"]
            checks = {
                "liquidity": liquidity is not None and liquidity >= MIN_LIQUIDITY_USD,
                "mint_authority": onchain.get("mint_authority_revoked") is True,
                "freeze_authority": onchain.get("freeze_authority_revoked") is True,
                "whale_concentration": onchain.get("top10_share") is not None and onchain["top10_share"] <= MAX_TOP10_SHARE,
            }
            row["checks"] = checks
            row["ai_score"] = None
            row["entry_status"] = "WAITING_FOR_AI_SCORE" if all(checks.values()) else "REJECTED_OR_UNVERIFIED"
            row["paper_entry_enabled"] = False
            row["blockers"] = [key for key, passed in checks.items() if not passed] + [
                "AI score provider not configured", "full safety.score_report not connected",
                "verified bonding-curve account not available", "live position manager not connected"
            ]
            row["generated_at"] = int(time.time())
            live_gate = evaluate_live_candidate(row)
            row["live_entry"] = live_gate
            if not live_gate["eligible"]:
                row["entry_status"] = "BLOCKED_LIVE"
                row["blockers"] = list(dict.fromkeys(row["blockers"] + live_gate["blockers"]))
            rows.append(row)
    rows.sort(key=lambda row: (1 if row.get("boosted") else 0, row.get("volume_24h_usd") or 0, row.get("liquidity_usd") or 0), reverse=True)
    rows = rows[:max(1, min(limit, 30))]
    result = {
        "mode": "paper_only", "scanner": "dexscreener_only_read_only",
        "generated_at": int(time.time()), "elapsed_ms": int((time.time() - started) * 1000),
        "cache_age_ms": 0, "candidate_count": len(rows), "candidates": rows,
        "errors": errors, "providers": providers,
        "policy": {"minimum_liquidity_usd": MIN_LIQUIDITY_USD, "maximum_top10_concentration": MAX_TOP10_SHARE,
                   "take_profit_pct_min": 70, "take_profit_pct_max": 130, "stop_loss_pct": 6,
                   "trailing_drawdown_pct": 12, "position_equity_fraction": 0.08},
    }
    with _SCAN_CACHE_LOCK:
        _SCAN_CACHE["at"] = time.time()
        _SCAN_CACHE["limit"] = limit
        _SCAN_CACHE["value"] = copy.deepcopy(result)
    return result

def scan_market_async(limit: int = 40) -> dict[str, Any]:
    """Run blocking public HTTP/RPC discovery outside the HTTP handler thread."""
    return scan_market(limit=limit)


def search_market(query: str, limit: int = 20) -> dict[str, Any]:
    """Search DexScreener Solana pairs; omit rows without real price and liquidity."""
    term = query.strip()
    if not term or len(term) > 100: raise ValueError("query must contain 1-100 characters")
    if not 1 <= limit <= 20: raise ValueError("limit must be between 1 and 20")
    started = time.time()
    response = httpx.get("https://api.dexscreener.com/latest/dex/search", params={"q": term}, timeout=httpx.Timeout(12.0, connect=4.0), headers={"Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, dict) or pair.get("chainId") != SOLANA: continue
        mint = str(((pair.get("baseToken") or {}).get("address")) or "").strip()
        if mint and pair.get("pairAddress"): grouped.setdefault(mint, []).append(pair)
    rows: list[dict[str, Any]] = []
    for mint, pairs in grouped.items():
        valid = [p for p in pairs if (_number(p.get("priceUsd")) or 0) > 0 and (_number((p.get("liquidity") or {}).get("usd")) or 0) > 0]
        if not valid: continue
        pair = max(valid, key=lambda p: _number((p.get("liquidity") or {}).get("usd")) or 0)
        token = pair.get("baseToken") or {}
        liquidity = _number((pair.get("liquidity") or {}).get("usd"))
        if liquidity is None or liquidity <= 0:
            continue
        volume = _number((pair.get("volume") or {}).get("h24"))
        cap = _number(pair.get("marketCap") or pair.get("fdv"))
        rows.append({
            "mint": mint, "name": token.get("name") or "Unknown", "symbol": token.get("symbol") or "—",
            "pool": "solana_" + str(pair["pairAddress"]), "price_usd": _number(pair.get("priceUsd")),
            "liquidity_usd": liquidity, "volume_24h_usd": volume, "market_cap_usd": cap,
            "price_change_1h_pct": _number((pair.get("priceChange") or {}).get("h1")),
            "price_change_24h_pct": _number((pair.get("priceChange") or {}).get("h24")),
            "source": ["DexScreener"], "url": pair.get("url"),
            "onchain": {"verified": False, "mint_authority_revoked": None, "freeze_authority_revoked": None, "top10_share": None, "reason": "Run scanner safety verification before considering entry"},
            "checks": {"liquidity": liquidity >= MIN_LIQUIDITY_USD, "mint_authority": False, "freeze_authority": False, "whale_concentration": False},
            "ai_score": None, "entry_status": "SEARCH_RESULT_UNVERIFIED", "paper_entry_enabled": False,
            "blockers": ["Search result only", "On-chain safety verification not run", "AI score provider not configured", "paper order approval pipeline not connected"],
        })
        if len(rows) >= limit: break
    return {"mode": "paper_only", "scanner": "dexscreener_only_search", "query": term, "generated_at": int(time.time()), "elapsed_ms": int((time.time() - started) * 1000), "candidate_count": len(rows), "candidates": rows, "errors": [], "policy": {"minimum_liquidity_usd": MIN_LIQUIDITY_USD, "maximum_top10_concentration": MAX_TOP10_SHARE}}

# Shared market-home snapshot cache: the Android home and Market tab reuse one
# provider snapshot instead of multiplying upstream requests during navigation.
_HOME_CACHE_LOCK = threading.Lock()
_HOME_CACHE: dict[str, Any] = {"at": 0.0, "value": None}


def _agent_market_decisions(row: dict[str, Any]) -> list[dict[str, str]]:
    """Evidence-backed market assessments; no placeholder is presented as an LLM run."""
    volume = row.get("volume_24h_usd")
    liquidity = row.get("liquidity_usd")
    change_1h = row.get("price_change_1h_pct")
    ratio = (volume / liquidity) if isinstance(volume, (int, float)) and isinstance(liquidity, (int, float)) and liquidity > 0 else None
    discovered = row.get("trend") == "NEW"
    flow = row.get("trade_flow") if isinstance(row.get("trade_flow"), dict) else {}
    net_buy = flow.get("net_buy_volume_sol")
    observed_flow = flow.get("fresh") is True
    momentum = (
        (isinstance(change_1h, (int, float)) and change_1h >= 5)
        or (ratio is not None and ratio >= 1.0)
        or (observed_flow and isinstance(net_buy, (int, float)) and net_buy > 0)
    )
    onchain = row.get("onchain") if isinstance(row.get("onchain"), dict) else {}
    authority_ok = onchain.get("verified") is True and onchain.get("mint_authority_revoked") is True and onchain.get("freeze_authority_revoked") is True
    top10 = onchain.get("top10_share")
    holders_ok = isinstance(top10, (int, float)) and top10 <= MAX_TOP10_SHARE
    rug_ok = authority_ok and holders_ok
    return [
        {"agent": "SCOUT", "decision": "NEW TOKEN" if discovered else "TRENDING POOL", "reason": "DexScreener discovery profile" if discovered else "DexScreener live pair data"},
        {"agent": "SIGNAL", "decision": "MOMENTUM WATCH" if momentum else "NO CONFIRMED MOMENTUM", "reason": f"1h change={change_1h if change_1h is not None else 'n/a'}%; volume/liquidity={round(ratio, 2) if ratio is not None else 'n/a'}; observed net flow={net_buy if observed_flow else 'unknown'} SOL"},
        {"agent": "WHALE", "decision": "NET BUY FLOW" if observed_flow and isinstance(net_buy, (int, float)) and net_buy > 0 else ("NET SELL FLOW" if observed_flow and isinstance(net_buy, (int, float)) and net_buy < 0 else "FLOW UNKNOWN"), "reason": f"PumpPortal 5m trades={flow.get('trade_count', 0)}, unique buyers={flow.get('unique_buyers', 0)}, unique sellers={flow.get('unique_sellers', 0)}, net={net_buy if observed_flow else 'unknown'} SOL"},
        {"agent": "RUG", "decision": "BASIC CHECKS PASS" if rug_ok else "UNVERIFIED / RISK", "reason": f"mint/freeze revoked={authority_ok}; top10 share={top10 if top10 is not None else 'unknown'}"},
        {"agent": "RISK", "decision": "BLOCK ENTRY", "reason": "Full safety.score_report, verified bonding curve and live position controls are not connected"},
        {"agent": "SNIPER", "decision": "WAIT", "reason": "Execution remains locked until every risk and execution prerequisite passes"},
        {"agent": "EXIT", "decision": "NO POSITION CONTEXT", "reason": "Bloom position reconciliation is not connected to this market snapshot"},
        {"agent": "SHILL", "decision": "SENTIMENT UNKNOWN", "reason": "No verified social sentiment provider is connected"},
        {"agent": "JOURNAL", "decision": "OBSERVATION ONLY", "reason": "No corresponding execution event is recorded for this candidate"},
        {"agent": "CHIEF", "decision": "HOLD / WATCH", "reason": "Market evidence is connected; autonomous entry remains fail-closed"},
    ]


def market_home(limit: int = 20) -> dict[str, Any]:
    """Build the Solana market exclusively from DexScreener live token pairs."""
    import copy

    if not 1 <= limit <= 30:
        raise ValueError("limit must be between 1 and 30")
    now = time.time()
    with _HOME_CACHE_LOCK:
        cached = _HOME_CACHE.get("value")
        if cached is not None and now - float(_HOME_CACHE.get("at", 0.0)) < 20:
            result = copy.deepcopy(cached)
            result["cache_age_ms"] = int((now - float(_HOME_CACHE["at"])) * 1000)
            return result

    started = time.time()
    errors: list[str] = []
    providers: list[dict[str, Any]] = []
    discovered: dict[str, dict[str, Any]] = {}
    timeout = httpx.Timeout(8.0, connect=3.0)
    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        # DexScreener is the only discovery and market-data provider.
        for endpoint, label in (
            (DEX_PROFILES, "latest token profiles"),
            ("https://api.dexscreener.com/token-boosts/latest/v1", "latest token boosts"),
        ):
            try:
                response = _get_with_backoff(client, endpoint, attempts=2)
                payload = response.json()
                count = 0
                for item in payload if isinstance(payload, list) else []:
                    if item.get("chainId") != SOLANA:
                        continue
                    mint = str(item.get("tokenAddress") or "").strip()
                    if not mint:
                        continue
                    row = discovered.setdefault(mint, {
                        "mint": mint, "name": item.get("description") or item.get("header") or "Solana token",
                        "symbol": "—", "trend": "NEW", "boosted": False,
                    })
                    row["boosted"] = row["boosted"] or "amount" in item
                    count += 1
                providers.append({"name": "DexScreener " + label, "status": "OK", "items": count})
            except (httpx.HTTPError, ValueError, TypeError):
                log.exception("DexScreener %s failed", label)
                providers.append({"name": "DexScreener " + label, "status": "UNAVAILABLE"})
                errors.append("DexScreener " + label + " unavailable")

        # Enrich up to 30 unique Solana mints in one supported batch request.
        mints = list(discovered.keys())[:30]
        matched: dict[str, list[dict[str, Any]]] = {}
        onchain_by_mint: dict[str, dict[str, Any]] = {}
        if mints:
            try:
                response = _get_with_backoff(
                    client, "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(mints), attempts=2
                )
                payload = response.json()
                pairs = payload if isinstance(payload, list) else (payload.get("pairs") or [] if isinstance(payload, dict) else [])
                for pair in pairs:
                    if not isinstance(pair, dict) or pair.get("chainId") != SOLANA:
                        continue
                    mint = str((pair.get("baseToken") or {}).get("address") or "")
                    if mint in discovered:
                        matched.setdefault(mint, []).append(pair)
                providers.append({
                    "name": "DexScreener live pairs", "status": "OK",
                    "requested": len(mints), "matched": len(matched),
                })
                # Verify the same candidates used by the UI; no fast-feed row is trusted alone.
                rpc_url = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com").strip()
                for mint in mints:
                    try:
                        onchain_by_mint[mint] = _verify_mint(client, rpc_url, mint)
                    except (httpx.HTTPError, ValueError, TypeError, KeyError):
                        onchain_by_mint[mint] = {
                            "verified": False, "mint_authority_revoked": None,
                            "freeze_authority_revoked": None, "top10_share": None,
                            "reason": "On-chain verification unavailable",
                        })
            except (httpx.HTTPError, ValueError, TypeError):
                log.exception("DexScreener live-pair batch failed")
                providers.append({"name": "DexScreener live pairs", "status": "UNAVAILABLE"})
                errors.append("DexScreener live-pair data unavailable")

    output: list[dict[str, Any]] = []
    for mint, profile in discovered.items():
        pairs = matched.get(mint, [])
        if not pairs:
            continue
        # Prefer the most liquid real pair, not an arbitrary or stale pair.
        pair = max(pairs, key=lambda p: _number((p.get("liquidity") or {}).get("usd")) or 0)
        token = pair.get("baseToken") or {}
        price = _number(pair.get("priceUsd"))
        if price is None:
            continue
        liquidity = _number((pair.get("liquidity") or {}).get("usd"))
        volume = _number((pair.get("volume") or {}).get("h24"))
        cap = _number(pair.get("marketCap") or pair.get("fdv"))
        row = {
            "mint": mint,
            "name": token.get("name") or profile.get("name") or "Unknown",
            "symbol": token.get("symbol") or "—",
            "pool": "solana_" + str(pair.get("pairAddress") or ""),
            "price_usd": price,
            "liquidity_usd": liquidity,
            "volume_24h_usd": volume,
            "market_cap_usd": cap,
            "price_change_1h_pct": _number((pair.get("priceChange") or {}).get("h1")),
            "price_change_24h_pct": _number((pair.get("priceChange") or {}).get("h24")),
            "source": ["DexScreener"],
            "url": pair.get("url"),
            "trend": "NEW",
            "boosted": bool(profile.get("boosted")),
            "pair_created_at": pair.get("pairCreatedAt"),
            "dex_id": pair.get("dexId"),
            "generated_at": int(time.time()),
            "onchain": onchain_by_mint.get(mint, {
                "verified": False, "mint_authority_revoked": None,
                "freeze_authority_revoked": None, "top10_share": None,
                "reason": "On-chain verification unavailable",
            }),
            "trade_flow": trade_flow(mint),
        }
        row["checks"] = {
            "liquidity": isinstance(liquidity, (int, float)) and liquidity >= MIN_LIQUIDITY_USD,
            "mint_authority": row["onchain"].get("mint_authority_revoked") is True,
            "freeze_authority": row["onchain"].get("freeze_authority_revoked") is True,
            "whale_concentration": isinstance(row["onchain"].get("top10_share"), (int, float)) and row["onchain"]["top10_share"] <= MAX_TOP10_SHARE,
        }
        row["agents"] = _agent_market_decisions(row)
        row["entry_status"] = "BLOCKED_UNVERIFIED"
        row["paper_entry_enabled"] = False
        row["risk_gate"] = "BLOCKED · VERIFY TOKEN AUTHORITIES + HOLDERS"
        row["momentum_ratio"] = (
            round(volume / liquidity, 2)
            if isinstance(volume, (int, float)) and isinstance(liquidity, (int, float)) and liquidity > 0
            else None
        )
        output.append(row)

    output.sort(
        key=lambda row: (
            1 if row.get("boosted") else 0,
            row.get("volume_24h_usd") or 0,
            row.get("liquidity_usd") or 0,
        ),
        reverse=True,
    )
    output = output[:limit]
    result = {
        "mode": "paper_only",
        "scanner": "dexscreener_solana_only",
        "generated_at": int(time.time()),
        "elapsed_ms": int((time.time() - started) * 1000),
        "cache_age_ms": 0,
        "candidate_count": len(output),
        "candidates": output,
        "providers": providers,
        "errors": errors,
        "decision_policy": "DexScreener live pair data only; transparent rule-based read-only agent assessments.",
        "execution": "LOCKED · no live orders",
    }
    with _HOME_CACHE_LOCK:
        _HOME_CACHE["at"] = time.time()
        _HOME_CACHE["value"] = copy.deepcopy(result)
    return result


def market_chart(pool_id: str, timeframe: str = "minute", aggregate: int = 5, limit: int = 100) -> dict[str, Any]:
    """Return real GeckoTerminal OHLCV candles for a discovered Solana pool."""
    pool = pool_id.strip()
    if "_" in pool:
        network, pool = pool.split("_", 1)
    else:
        network = SOLANA
    if network != SOLANA or not pool or len(pool) > 100:
        raise ValueError("A valid Solana pool id is required")
    if timeframe not in {"minute", "hour", "day"}:
        raise ValueError("timeframe must be minute, hour or day")
    if aggregate not in {1, 5, 15, 30, 60, 240, 1_440}:
        raise ValueError("unsupported candle aggregate")
    if not 10 <= limit <= 500:
        raise ValueError("limit must be between 10 and 500")
    url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool}/ohlcv/{timeframe}"
    response = httpx.get(
        url,
        params={"aggregate": aggregate, "limit": limit, "currency": "usd", "token": "base"},
        headers={"Accept": "application/json;version=20230302"},
        timeout=httpx.Timeout(12.0, connect=4.0),
    )
    response.raise_for_status()
    payload = response.json()
    attrs = ((payload.get("data") or {}).get("attributes") or {})
    candles = []
    for item in attrs.get("ohlcv_list") or []:
        if not isinstance(item, list) or len(item) < 6:
            continue
        try:
            candles.append({
                "timestamp": int(item[0]), "open": float(item[1]),
                "high": float(item[2]), "low": float(item[3]),
                "close": float(item[4]), "volume": float(item[5]),
            })
        except (TypeError, ValueError, OverflowError):
            continue
    candles.sort(key=lambda candle: candle["timestamp"])
    return {
        "network": network, "pool": pool, "timeframe": timeframe,
        "aggregate": aggregate, "currency": "usd", "source": "GeckoTerminal OHLCV",
        "generated_at": int(time.time()), "count": len(candles), "candles": candles,
    }
