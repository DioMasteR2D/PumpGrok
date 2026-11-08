"""Read-only PumpGrok dashboard API.

Run with: python services/pumpfun-api/server.py
Writes are limited to authenticated scanner event ingestion. There is no
transaction-signing or order-submission route in this service.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DB_PATH = Path(os.environ.get("PUMPGROK_DB_PATH", "var/pumpfun-dashboard.sqlite3"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY = 256 * 1024


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signature TEXT NOT NULL,
            mint TEXT,
            event_type TEXT NOT NULL,
            schema_status TEXT NOT NULL,
            payload TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            UNIQUE(signature, event_type, mint)
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS scanner_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            status TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            detail TEXT
        )"""
    )
    db.commit()
    return db


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "PumpGrokDashboard/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        # Avoid logging URLs, request bodies, wallet addresses or auth headers.
        return

    def send_json(self, status: int, payload: Any) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_json(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._health()
        elif path == "/api/dashboard":
            self._dashboard()
        elif path == "/api/events":
            self._events()
        elif path == "/api/tokens":
            self._tokens()
        else:
            self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/ingest/event":
            self.send_json(404, {"error": "not_found"})
            return
        expected = os.environ.get("PUMPGROK_INGEST_TOKEN", "")
        supplied = self.headers.get("Authorization", "")
        if not expected:
            self.send_json(503, {"error": "ingestion_not_configured"})
            return
        if not secrets.compare_digest(supplied, f"Bearer {expected}"):
            self.send_json(401, {"error": "unauthorized"})
            return
        length = self.headers.get("Content-Length", "")
        if not length.isdigit() or int(length) > MAX_BODY:
            self.send_json(413, {"error": "invalid_body_size"})
            return
        try:
            payload = json.loads(self.rfile.read(int(length)))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(400, {"error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self.send_json(400, {"error": "invalid_payload"})
            return
        kind = payload.get("kind")
        if kind == "heartbeat":
            self._record_heartbeat(payload)
            return
        required = ("signature", "event_type", "schema_status")
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
            self.send_json(400, {"error": "missing_event_fields"})
            return
        mint = payload.get("mint")
        if mint is not None and not isinstance(mint, str):
            self.send_json(400, {"error": "invalid_mint"})
            return
        observed = payload.get("observed_at")
        if not isinstance(observed, str):
            observed = utc_now()
        db = connect_db()
        try:
            db.execute(
                """INSERT OR IGNORE INTO events
                (signature, mint, event_type, schema_status, payload, observed_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    payload["signature"],
                    mint,
                    payload["event_type"][:80],
                    payload["schema_status"][:40],
                    json.dumps(payload.get("data", {}), separators=(",", ":")),
                    observed,
                ),
            )
            db.commit()
        finally:
            db.close()
        self.send_json(202, {"accepted": True})

    def _record_heartbeat(self, payload: dict[str, Any]) -> None:
        status = payload.get("status", "connected")
        if status not in {"connected", "reconnecting", "offline"}:
            status = "unknown"
        db = connect_db()
        try:
            db.execute(
                """INSERT INTO scanner_state(id, status, last_seen, detail)
                VALUES(1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                status=excluded.status, last_seen=excluded.last_seen,
                detail=excluded.detail""",
                (status, utc_now(), str(payload.get("detail", ""))[:120]),
            )
            db.commit()
        finally:
            db.close()
        self.send_json(202, {"accepted": True})

    def _health(self) -> None:
        db = connect_db()
        try:
            row = db.execute("SELECT status, last_seen FROM scanner_state WHERE id=1").fetchone()
            count = db.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        finally:
            db.close()
        scanner = "offline"
        last_seen = None
        if row:
            last_seen = row["last_seen"]
            try:
                age = (datetime.now(UTC) - datetime.fromisoformat(last_seen)).total_seconds()
                scanner = row["status"] if age <= 90 else "stale"
            except ValueError:
                scanner = "unknown"
        self.send_json(
            200,
            {
                "service": "online",
                "scanner": scanner,
                "scanner_last_seen": last_seen,
                "observed_events": count,
                "mode": "PAPER_ONLY",
                "live_execution": False,
            },
        )

    def _dashboard(self) -> None:
        db = connect_db()
        try:
            count = db.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
            recent = db.execute(
                "SELECT observed_at FROM events ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            db.close()
        self.send_json(
            200,
            {
                "mode": "PAPER_ONLY",
                "portfolio": {
                    "balance_usd": None,
                    "realized_pnl_usd": None,
                    "unrealized_pnl_usd": None,
                    "open_positions": None,
                    "source": "paper_ledger_not_connected",
                },
                "scanner": {"events_observed": count, "last_event_at": recent["observed_at"] if recent else None},
                "limits": {
                    "trade_size_usd": 2,
                    "max_open_positions": 10,
                    "take_profit_pct": 10,
                    "stop_loss_pct": 5,
                    "daily_loss_limit_usd": 15,
                },
                "agents": [
                    {"name": name, "status": "awaiting_evidence"}
                    for name in ("LAUNCH", "CURVE", "HOLDERS", "DEV", "SOCIAL", "SNIPER", "WHALE", "RISK")
                ],
            },
        )

    def _events(self) -> None:
        db = connect_db()
        try:
            rows = db.execute(
                """SELECT signature, mint, event_type, schema_status, payload, observed_at
                FROM events ORDER BY id DESC LIMIT 100"""
            ).fetchall()
        finally:
            db.close()
        events = [
            {
                "signature": row["signature"],
                "mint": row["mint"],
                "event_type": row["event_type"],
                "schema_status": row["schema_status"],
                "data": json.loads(row["payload"]),
                "observed_at": row["observed_at"],
            }
            for row in rows
        ]
        self.send_json(200, {"events": events})

    def _tokens(self) -> None:
        db = connect_db()
        try:
            rows = db.execute(
                """SELECT mint, MAX(observed_at) AS last_seen, COUNT(*) AS events
                FROM events WHERE mint IS NOT NULL GROUP BY mint
                ORDER BY last_seen DESC LIMIT 100"""
            ).fetchall()
        finally:
            db.close()
        self.send_json(200, {"tokens": [dict(row) for row in rows]})


if __name__ == "__main__":
    connect_db().close()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
