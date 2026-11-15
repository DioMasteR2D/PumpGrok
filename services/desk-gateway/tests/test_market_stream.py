from __future__ import annotations

from desk_gateway import market_stream


def test_trade_flow_aggregates_recent_wallet_and_volume_data() -> None:
    with market_stream._lock:
        market_stream._trade_events.clear()
        market_stream._state["connected"] = True
        market_stream._state["last_trade_at"] = 1_000
        market_stream._trade_events.extend(
            [
                {"mint": "mint-a", "side": "buy", "trader": "wallet-1", "sol_amount": 2.5, "received_at": 1_000},
                {"mint": "mint-a", "side": "buy", "trader": "wallet-2", "sol_amount": 1.0, "received_at": 999},
                {"mint": "mint-a", "side": "sell", "trader": "wallet-1", "sol_amount": 0.5, "received_at": 998},
                {"mint": "mint-b", "side": "buy", "trader": "wallet-3", "sol_amount": 9.0, "received_at": 1_000},
            ]
        )

    flow = market_stream.trade_flow("mint-a", now=1_001)

    assert flow["status"] == "OBSERVED"
    assert flow["trade_count"] == 3
    assert flow["buy_count"] == 2
    assert flow["sell_count"] == 1
    assert flow["unique_buyers"] == 2
    assert flow["unique_sellers"] == 1
    assert flow["buy_volume_sol"] == 3.5
    assert flow["sell_volume_sol"] == 0.5
    assert flow["net_buy_volume_sol"] == 3.0


def test_trade_flow_does_not_invent_missing_activity() -> None:
    with market_stream._lock:
        market_stream._trade_events.clear()
        market_stream._state["connected"] = False
        market_stream._state["last_trade_at"] = None

    flow = market_stream.trade_flow("mint-without-trades", now=1_001)

    assert flow["status"] == "STREAM_DISCONNECTED"
    assert flow["fresh"] is False
    assert flow["trade_count"] == 0
    assert flow["net_buy_volume_sol"] == 0.0


def test_creation_evidence_is_explicitly_unverified_and_expires() -> None:
    with market_stream._lock:
        market_stream._creation_evidence.clear()
        market_stream._creation_evidence["mint-new"] = {
            "curve_account": "curve-account",
            "creator": "creator-wallet",
            "signature": "signature",
            "received_at": 1_000,
        }

    fresh = market_stream.creation_evidence("mint-new", now=1_010)
    stale = market_stream.creation_evidence("mint-new", max_age_seconds=30, now=1_100)
    missing = market_stream.creation_evidence("mint-missing", now=1_010)

    assert fresh["available"] is True
    assert fresh["verified"] is False
    assert fresh["curve_account"] == "curve-account"
    assert fresh["creator"] == "creator-wallet"
    assert stale["available"] is False
    assert stale["curve_account"] is None
    assert missing["available"] is False
    assert missing["verified"] is False
