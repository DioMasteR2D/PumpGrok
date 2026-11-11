"""Gateway-specific autonomous paper policy and initial capital regressions."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "services" / "desk-gateway" / "src"))

from desk_gateway.server import _enable_autonomous_paper  # noqa: E402
from pumpgrok.config.settings import load_settings  # noqa: E402
from pumpgrok.core.risk_budget import RiskBudget  # noqa: E402
from pumpgrok.ledger.autonomy import read_autonomy  # noqa: E402
from pumpgrok.ledger.store import LedgerStore  # noqa: E402
from pumpgrok.replay.clock import FixtureClock  # noqa: E402
from pumpgrok.tools.exec.place import PlaceIn, _request_of  # noqa: E402

MINT = "So11111111111111111111111111111111111111112"
DECISION = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@pytest.fixture(autouse=True)
def clean_pumpgrok_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.upper().startswith("PUMPGROK_"):
            monkeypatch.delenv(name, raising=False)


def test_paper_profile_uses_100_usd_equivalent_sol_and_keeps_limits() -> None:
    settings = load_settings()
    assert settings.effective_mode == "paper"
    assert settings.risk.paper_equity_sol == Decimal("1.02595670")
    assert settings.risk.max_open_positions == 3
    assert settings.risk.max_trade_fraction == Decimal("0.08")
    assert settings.risk.max_token_fraction == Decimal("0.08")
    assert settings.risk.max_trades_per_day == 20
    assert settings.risk.daily_loss_halt_fraction == Decimal("0.05")
    assert settings.risk.drawdown_halt_fraction == Decimal("0.15")


def test_gateway_records_autonomous_paper_policy_once(tmp_path) -> None:
    store = LedgerStore(str(tmp_path / "ledger.sqlite"))
    clock = FixtureClock(datetime(2026, 11, 4, 12, 0, tzinfo=UTC).timestamp())
    budget = RiskBudget(paper_equity_sol=Decimal("1.02595670"))
    try:
        assert _enable_autonomous_paper(store, budget, clock) == "autonomous-paper"
        assert store.get_meta("initial_equity_lamports") == str(budget.paper_equity_lamports)
        assert read_autonomy(store) == "autonomous-paper"
        rows = store.read(types=["ConfigChanged"], limit=None)
        assert len(rows) == 1
        assert rows[0]["payload"]["by"] == "human:DioMasteR2D"
        assert _enable_autonomous_paper(store, budget, clock) == "autonomous-paper"
        assert len(store.read(types=["ConfigChanged"], limit=None)) == 1
    finally:
        store.close()


def test_exec_place_input_allows_risk_engine_to_mint_approval() -> None:
    request = PlaceIn(
        ticket_id="SOL-20261104-001",
        mint=MINT,
        side="buy",
        decision_id=DECISION,
        size_lamports=100_000_000,
        max_slippage_bps=50,
    )
    assert request.approval_id is None
    assert _request_of(request).approval_id is None
