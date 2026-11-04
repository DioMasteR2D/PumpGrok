"""Best-effort PumpPortal discovery stream cache.

Only discovery events are subscribed to. This module never signs or submits trades.
"""
from __future__ import annotations

import asyncio
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
_state: dict[str, Any] = {"connected": False, "last_event_at": None, "reconnects": 0}


def snapshot(limit: int = 40) -> dict[str, Any]:
    with _lock:
        events = list(_events)[-max(1, min(limit, 100)):]
        state = dict(_state)
    return {"provider": "PumpPortal WebSocket", **state, "events": events}


async def run_pumpportal_stream() -> None:
    """Keep one shared websocket open and cache new-token/migration events."""
    while True:
        try:
            async with websockets.connect(_URI, ping_interval=20, close_timeout=5, open_timeout=10) as ws:
                with _lock:
                    _state["connected"] = True
                await ws.send('{"method":"subscribeNewToken"}')
                await ws.send('{"method":"subscribeMigration"}')
                async for raw in ws:
                    try:
                        import json
                        payload = json.loads(raw)
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    event_type = str(payload.get("txType") or payload.get("type") or "stream_event")
                    mint = str(payload.get("mint") or payload.get("tokenAddress") or "")
                    if not mint:
                        continue
                    row = {
                        "type": event_type,
                        "mint": mint,
                        "name": payload.get("name") or payload.get("tokenName"),
                        "symbol": payload.get("symbol") or payload.get("tokenSymbol"),
                        "pool": payload.get("pool"),
                        "market_cap_sol": payload.get("marketCapSol"),
                        "signature": payload.get("signature"),
                        "received_at": int(time.time()),
                    }
                    with _lock:
                        _events.append(row)
                        _state["last_event_at"] = row["received_at"]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("PumpPortal discovery stream disconnected: %s", type(exc).__name__)
            with _lock:
                _state["connected"] = False
                _state["reconnects"] = int(_state.get("reconnects", 0)) + 1
            await asyncio.sleep(3)
        finally:
            with _lock:
                _state["connected"] = False
