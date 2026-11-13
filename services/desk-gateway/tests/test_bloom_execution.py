from __future__ import annotations

from typing import Any

import httpx
import pytest

from desk_gateway.bloom_execution import (
    BloomExecutionError,
    build_swap_payload,
    select_spot_wallet,
    submit_swap,
)

MINT = "So11111111111111111111111111111111111111112"
WALLET = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"


def test_buy_payload_keeps_bounded_amount_and_attaches_exits() -> None:
    payload = build_swap_payload(
        mint=MINT, side="Buy", wallet_address=WALLET, amount=0.005
    )
    assert payload["side"] == "Buy"
    assert payload["wallets"] == [{"address": WALLET, "amount": "0.005000000"}]
    assert payload["skip_if_bought"] is True
    assert [order["target_value"] for order in payload["auto_orders"]] == [10.0, -5.0]
    assert all(order["amount"] == 100 for order in payload["auto_orders"])


def test_sell_payload_is_percentage_of_confirmed_wallet_holdings() -> None:
    payload = build_swap_payload(
        mint=MINT, side="Sell", wallet_address=WALLET, amount=35
    )
    assert payload["side"] == "Sell"
    assert payload["sell_mode"] == "percent"
    assert payload["wallets"] == [{"address": WALLET, "amount": "35"}]
    assert "auto_orders" not in payload


@pytest.mark.parametrize(
    ("side", "amount"),
    [("Buy", 0), ("Buy", 0.01001), ("Sell", 0), ("Sell", 100.1)],
)
def test_swap_payload_rejects_out_of_range_amounts(side: str, amount: float) -> None:
    with pytest.raises(ValueError):
        build_swap_payload(
            mint=MINT, side=side, wallet_address=WALLET, amount=amount
        )


def test_swap_payload_rejects_invalid_mint() -> None:
    with pytest.raises(ValueError, match="mint"):
        build_swap_payload(
            mint="not-a-mint", side="Buy", wallet_address=WALLET, amount=0.001
        )


def test_wallet_selection_requires_exactly_one_spot_wallet() -> None:
    assert select_spot_wallet({
        "data": {"wallets": [{"address": WALLET, "spot_active": True}]}
    }) == WALLET
    with pytest.raises(BloomExecutionError, match="exactly one"):
        select_spot_wallet({"data": {"wallets": []}})
    with pytest.raises(BloomExecutionError, match="exactly one"):
        select_spot_wallet({"data": {"wallets": [
            {"address": WALLET, "spot_active": True},
            {"address": WALLET, "spot_active": True},
        ]}})
    with pytest.raises(BloomExecutionError, match="malformed"):
        select_spot_wallet([])
    with pytest.raises(BloomExecutionError, match="data object"):
        select_spot_wallet({"data": []})
    with pytest.raises(BloomExecutionError, match="invalid"):
        select_spot_wallet({"data": {"wallets": [
            {"address": "not-a-wallet", "spot_active": True}
        ]}})


def test_submit_swap_does_not_treat_skipped_http_200_as_a_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("POST", "https://eu.solana.bloombot.app/api/v1/swap")
        return httpx.Response(
            200, request=request,
            json={"success": True, "data": {"order_id": "skip", "signatures": [], "skipped": True}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(BloomExecutionError, match="skipped"):
        submit_swap(api_key="test-key", payload={"side": "Buy"})


def test_submit_swap_returns_submitted_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("POST", "https://eu.solana.bloombot.app/api/v1/swap")
        return httpx.Response(
            200, request=request,
            json={"success": True, "data": {"order_id": "order-1", "signatures": ["sig-1"], "skipped": False}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = submit_swap(api_key="test-key", payload={"side": "Sell"})
    assert result["success"] is True
    assert result["signatures"] == ["sig-1"]
    assert "submitted" in result["confirmation"]



def test_submit_swap_rejects_malformed_signature_list(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("POST", "https://eu.solana.bloombot.app/api/v1/swap")
        return httpx.Response(
            200, request=request,
            json={"success": True, "data": {"order_id": "bad", "signatures": ["", None]}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(BloomExecutionError, match="valid transaction signature"):
        submit_swap(api_key="test-key", payload={"side": "Buy"})
