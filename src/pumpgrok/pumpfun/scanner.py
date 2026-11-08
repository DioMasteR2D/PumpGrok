"""Read-only Pump.fun launch/event listener for the dashboard.

The decoder's field layouts are currently marked ASSUMED in pump_events.py.
Decoded observations are therefore stored as UNVERIFIED and must not be
used as a price, risk clearance, or executable trading signal.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from pumpgrok.tools.onchain.pump_events import EventDecodeError, decode_program_data

DEFAULT_PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


class PumpFunScanner:
    def __init__(self) -> None:
        self.ws_url = os.environ["PUMPGROK_SOLANA_WS_URL"]
        self.api_url = os.environ["PUMPGROK_DASHBOARD_API"].rstrip("/")
        self.token = os.environ["PUMPGROK_INGEST_TOKEN"]
        self.program_id = os.environ.get("PUMPGROK_PUMP_PROGRAM_ID", DEFAULT_PUMP_PROGRAM)
        self.client = httpx.AsyncClient(timeout=10.0)

    async def post(self, payload: dict[str, Any]) -> None:
        response = await self.client.post(
            f"{self.api_url}/api/ingest/event",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        response.raise_for_status()

    async def heartbeat(self, status: str, detail: str = "") -> None:
        await self.post({"kind": "heartbeat", "status": status, "detail": detail})

    async def handle_notification(self, message: dict[str, Any]) -> int:
        params = message.get("params")
        result = params.get("result") if isinstance(params, dict) else None
        value = result.get("value") if isinstance(result, dict) else None
        if not isinstance(value, dict):
            return 0
        signature = value.get("signature")
        logs = value.get("logs")
        if not isinstance(signature, str) or not isinstance(logs, list):
            return 0
        inserted = 0
        for line in logs:
            if not isinstance(line, str) or not line.startswith("Program data: "):
                continue
            encoded = line.removeprefix("Program data: ").strip()
            try:
                event = decode_program_data(encoded)
            except EventDecodeError:
                continue
            data = asdict(event) if is_dataclass(event) else {}
            mint = getattr(event, "mint", None)
            event_type = type(event).__name__
            payload = {
                "signature": signature,
                "mint": mint,
                "event_type": event_type,
                "schema_status": "UNVERIFIED",
                "observed_at": now_utc(),
                "data": data,
            }
            await self.post(payload)
            inserted += 1
        if inserted:
            await self.heartbeat("connected", f"decoded_events={inserted}")
        return inserted

    async def run(self) -> None:
        delay = 1.0
        while True:
            try:
                await self.heartbeat("reconnecting", "opening_solana_websocket")
                async with connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "logsSubscribe",
                                "params": [
                                    {"mentions": [self.program_id]},
                                    {"commitment": "confirmed"},
                                ],
                            }
                        )
                    )
                    acknowledgement = json.loads(await ws.recv())
                    if "error" in acknowledgement:
                        raise RuntimeError("logsSubscribe_rejected")
                    await self.heartbeat("connected", "logsSubscribe_active")
                    delay = 1.0
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        except TimeoutError:
                            await self.heartbeat("connected", "logsSubscribe_active")
                            continue
                        try:
                            message = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        if isinstance(message, dict) and message.get("method") == "logsNotification":
                            await self.handle_notification(message)
            except (OSError, RuntimeError, ConnectionClosed, httpx.HTTPError):
                try:
                    await self.heartbeat("reconnecting", "upstream_or_transport_error")
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def close(self) -> None:
        await self.client.aclose()


async def main() -> None:
    required = ("PUMPGROK_SOLANA_WS_URL", "PUMPGROK_DASHBOARD_API", "PUMPGROK_INGEST_TOKEN")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit("Missing required scanner environment configuration: " + ", ".join(missing))
    scanner = PumpFunScanner()
    try:
        await scanner.run()
    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
