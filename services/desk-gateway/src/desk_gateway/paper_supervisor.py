"""Always-on paper position supervisor for the desk gateway.

This worker only manages exits for positions already in the paper ledger. Every
sell is submitted through PaperAdapter and the existing RiskEngine under the
exit seat identity. It never calls Bloom or a live execution adapter.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any

from pumpgrok.core.adapter import OrderRequest
from pumpgrok.core.ids import CorrelationId, IdFactory, bind_calling_seat, bind_correlation
from pumpgrok.execution.paper_adapter.adapter import PaperAdapter
from pumpgrok.ledger.store import LedgerStore
from pumpgrok.replay.clock import Clock
from pumpgrok.supervisor.exit_rules import ExitRules
from pumpgrok.logging.json import bind_seat

log = logging.getLogger("desk_gateway.paper_supervisor")
EXIT_SEAT = "bot-06-exit"
SLIPPAGE_BPS = 100


class _AdapterCurveFeed:
    """Narrow curve-feed facade used by the existing exit-rule engine."""

    def __init__(self, adapter: PaperAdapter) -> None:
        self.adapter = adapter
        self._last_open: dict[str, tuple[int, int]] = {}

    async def curve(self, mint: str):
        snapshot = await self.adapter._read_curve(mint)
        if snapshot is not None and not snapshot.complete:
            self._last_open[mint] = (snapshot.s_lamports, snapshot.t_units)
        return snapshot

    def last_open_reserves(self, mint: str):
        return self._last_open.get(mint)


class PaperExitSupervisor:
    """Periodic mark-and-exit loop, with observable counters and fail-closed errors."""

    def __init__(self, *, adapter: PaperAdapter, store: LedgerStore, clock: Clock, exits: Any):
        self.adapter = adapter
        self.store = store
        self.clock = clock
        self.feed = _AdapterCurveFeed(adapter)
        self.ids = IdFactory(clock, secrets.SystemRandom())
        self.cycles = 0
        self.sells = 0
        self.errors = 0
        self.open_positions = 0
        self.last_cycle_at: float | None = None
        self.last_error: str | None = None
        self.rules = ExitRules(
            store=store,
            curves=self.feed,  # the interface is curve()/last_open_reserves()
            exits=exits,
            clock=clock,
            place_sell=self._place_sell,
        )

    async def _place_sell(self, mint: str, ticket: str, units: int, rule: str) -> dict[str, Any]:
        decision_id = self.ids.ulid()
        correlation = CorrelationId.new(self.ids)
        request = OrderRequest(
            ticket_id=ticket,
            mint=mint,
            side="sell",
            decision_id=decision_id,
            token_units=units,
            max_slippage_bps=SLIPPAGE_BPS,
            exit_reason=rule,
            correlation_id=str(correlation),
        )
        with bind_seat(EXIT_SEAT), bind_calling_seat(EXIT_SEAT), bind_correlation(correlation):
            fill = await self.adapter.place(request)
        self.sells += 1
        return {"status": fill.status.value, "reason": fill.reason or ""}

    def status(self) -> dict[str, Any]:
        return {
            "mode": "paper",
            "running": True,
            "component": "exit_supervisor",
            "cycles": self.cycles,
            "sells": self.sells,
            "errors": self.errors,
            "last_cycle_at": self.last_cycle_at,
            "last_error": self.last_error,
            "open_positions": self.open_positions,
        }

    async def run(self, interval_s: float = 5.0) -> None:
        while True:
            try:
                await self.adapter.mark_open_positions(source="paper")
                await self.rules.check(self.clock.now())
                self.open_positions = len(await self.adapter.positions())
                self.cycles += 1
                self.last_cycle_at = self.clock.now()
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.errors += 1
                self.last_error = type(exc).__name__
                log.exception("paper exit supervisor cycle failed")
            await asyncio.sleep(interval_s)
