"""PumpPortal discovery and per-token trade-flow stream cache.

This module supplies observed market-flow evidence only. It never signs or submits trades.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from threading import Lock
from typing import Any

import websockets

log = logging.getLogger("desk_gateway.market_stream")
_URI = "wss://pumpportal.fun/api/data"
_lock = Lock()
_events: deque[dict[str, Any]] = deque(maxlen=250)
_trade_events: deque[dict[str, Any]] = deque(maxlen=5_000)
_subscribed_mints: set[str] = set()
_state: dict[str, Any] = {
    "connected": False,
    "last_event_at": None,
    "last_trade_at": None,
    "reconnects": 0,
    "trade_subscriptions": 0,
}


def snapshot(limit: int = 40) -> dict[str, Any]:
    with _lock:
        events = list(_events)[-max(1, min(limit, 100)):]
        state = dict(_state)
    return {"provider": "PumpPortal WebSocket", **state, "events": events}


def trade_flow(mint: str, *, window_seconds: int = 300, now: float | None = None) -> dict[str, Any]:
    """Summarize observed buy/sell flow; unavailable or stale flow remains unknown."""
    current = time.time() if now is None else float(now)
    window = max(30, min(int(window_seconds), 900))
    with _lock:
        rows = [
            dict(row) for row in _trade_events
            if row.get("mint") == mint and current - float(row.get("received_at", 0)) <= window
        ]
        connected = bool(_state.get("connected"))
        last_trade_at = _state.get("last_trade_at")
    buys = [row for row in rows if row.get("side") == "buy"]
    sells = [row for row in rows if row.get("side") == "sell"]
    buy_wallets = {row.get("trader") for row in buys if row.get("trader")}
    sell_wallets = {row.get("trader") for row in sells if row.get("trader")}
    buy_sol = sum(float(row.get("sol_amount") or 0) for row in buys)
    sell_sol = sum(float(row.get("sol_amount") or 0) for row in sells)
    age = current - float(last_trade_at) if last_trade_at is not None else None
    fresh = bool(rows) and age is not None and age <= window
    return {
        "provider": "PumpPortal token trades",
        "status": "OBSERVED" if fresh else ("NO_RECENT_TRADES" if connected else "STREAM_DISCONNECTED"),
        "window_seconds": window,
        "trade_count": len(rows),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "unique_buyers": len(buy_wallets),
        "unique_sellers": len(sell_wallets),
        "buy_volume_sol": round(buy_sol, 6),
        "sell_volume_sol": round(sell_sol, 6),
        "net_buy_volume_sol": round(buy_sol - sell_sol, 6),
        "last_trade_at": max((row["received_at"] for row in rows), default=None),
        "fresh": fresh,
    }


async def run_pumpportal_stream() -> None:
    """Keep one websocket open for discovery plus trade flow on recently seen mints."""
    while True:
        try:
            async with websockets.connect(_URI, ping_interval=20, close_timeout=5, open_timeout=10) as ws:
                with _lock:
                    _state["connected"] = True
                    _subscribed_mints.clear()
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                await ws.send(json.dumps({"method": "subscribeMigration"}))
                async for raw in ws:
                    try:
                        payload = json.loads(raw)
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    event_type = str(payload.get("txType") or payload.get("type") or "stream_event").lower()
                    mint = str(payload.get("mint") or payload.get("tokenAddress") or "").strip()
                    if not mint:
                        continue
                    received_at = int(time.time())
                    if event_type in {"buy", "sell"}:
                        trader = str(payload.get("traderPublicKey") or "")
                        try:
                            sol_amount = max(0.0, float(payload.get("solAmount") or 0))
                        except (TypeError, ValueError):
                            sol_amount = 0.0
                        row = {
                            "mint": mint, "side": event_type, "trader": trader or None,
                            "sol_amount": sol_amount, "received_at": received_at,
                            "signature": payload.get("signature"),
                        }
                        with _lock:
                            _trade_events.append(row)
                            _state["last_trade_at"] = received_at
                        continue

                    row = {
                        "type": event_type,
                        "mint": mint,
                        "name": payload.get("name") or payload.get("tokenName"),
                        "symbol": payload.get("symbol") or payload.get("tokenSymbol"),
                        "pool": payload.get("pool"),
                        "market_cap_sol": payload.get("marketCapSol"),
                        "signature": payload.get("signature"),
                        "received_at": received_at,
                    }
                    with _lock:
                        _events.append(row)
                        _state["last_event_at"] = received_at
                        should_subscribe = mint not in _subscribed_mints and len(_subscribed_mints) < 100
                        if should_subscribe:
                            _subscribed_mints.add(mint)
                    if should_subscribe:
                        try:
                            await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
                            with _lock:
                                _state["trade_subscriptions"] = len(_subscribed_mints)
                        except Exception:
                            with _lock:
                                _subscribed_mints.discard(mint)
                            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("PumpPortal discovery/trade stream disconnected: %s", type(exc).__name__)
            with _lock:
                _state["connected"] = False
                _state["reconnects"] = int(_state.get("reconnects", 0)) + 1
                _subscribed_mints.clear()
            await asyncio.sleep(3)
        finally:
            with _lock:
                _state["connected"] = False
