"""Tests for the read-only GeckoTerminal OHLCV chart adapter."""

from __future__ import annotations

from typing import Any

import pytest

from desk_gateway.market_scanner import market_chart


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_market_chart_normalizes_and_sorts_candles(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_get(url: str, **kwargs: Any) -> _Response:
        captured["url"] = url
        captured.update(kwargs)
        return _Response({
            "data": {"attributes": {"ohlcv_list": [
                [200, "2", "3", "1", "2.5", "40"],
                [100, "1", "2", "0.5", "2", "20"],
                ["bad", "x", "x", "x", "x", "x"],
            ]}}
        })

    monkeypatch.setattr("desk_gateway.market_scanner.httpx.get", fake_get)
    result = market_chart("solana_pool123", "minute", 5, 100)

    assert result["source"] == "GeckoTerminal OHLCV"
    assert result["pool"] == "pool123"
    assert result["count"] == 2
    assert [candle["timestamp"] for candle in result["candles"]] == [100, 200]
    assert result["candles"][0]["close"] == 2.0
    assert captured["params"] == {
        "aggregate": 5, "limit": 100, "currency": "usd", "token": "base"
    }


@pytest.mark.parametrize(
    ("pool", "timeframe", "aggregate", "limit"),
    [
        ("", "minute", 5, 100),
        ("ethereum_pool", "minute", 5, 100),
        ("solana_pool", "week", 5, 100),
        ("solana_pool", "minute", 7, 100),
        ("solana_pool", "minute", 5, 9),
        ("solana_pool", "minute", 5, 501),
    ],
)
def test_market_chart_rejects_invalid_parameters(
    pool: str, timeframe: str, aggregate: int, limit: int
) -> None:
    with pytest.raises(ValueError):
        market_chart(pool, timeframe, aggregate, limit)
