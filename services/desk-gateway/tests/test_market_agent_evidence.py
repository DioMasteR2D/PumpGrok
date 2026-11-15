from __future__ import annotations

from desk_gateway.market_scanner import _agent_market_decisions


def test_market_agents_use_observed_trade_flow_and_onchain_evidence() -> None:
    row = {
        "trend": "NEW",
        "volume_24h_usd": 100_000,
        "liquidity_usd": 50_000,
        "price_change_1h_pct": 1.0,
        "trade_flow": {
            "fresh": True, "trade_count": 12, "unique_buyers": 7,
            "unique_sellers": 2, "net_buy_volume_sol": 4.25,
        },
        "onchain": {
            "verified": True, "mint_authority_revoked": True,
            "freeze_authority_revoked": True, "top10_share": 0.18,
        },
    }

    agents = {item["agent"]: item for item in _agent_market_decisions(row)}

    assert agents["WHALE"]["decision"] == "NET BUY FLOW"
    assert "unique buyers=7" in agents["WHALE"]["reason"]
    assert agents["RUG"]["decision"] == "BASIC CHECKS PASS"
    assert agents["SIGNAL"]["decision"] == "MOMENTUM WATCH"
    assert agents["RISK"]["decision"] == "BLOCK ENTRY"
    assert agents["SNIPER"]["decision"] == "WAIT"


def test_market_agents_do_not_treat_missing_flow_or_holders_as_pass() -> None:
    agents = {
        item["agent"]: item
        for item in _agent_market_decisions({
            "trend": "NEW", "volume_24h_usd": 1, "liquidity_usd": 100,
            "price_change_1h_pct": 0, "trade_flow": {"fresh": False},
            "onchain": {"verified": False},
        })
    }

    assert agents["WHALE"]["decision"] == "FLOW UNKNOWN"
    assert agents["RUG"]["decision"] == "UNVERIFIED / RISK"
    assert agents["RISK"]["decision"] == "BLOCK ENTRY"
