from __future__ import annotations

from desk_gateway.bloom_autopilot import REQUIRED_SAFETY_CHECKS, evaluate_live_candidate


def _candidate() -> dict:
    return {
        "mint": "A" * 32,
        "curve_account": "B" * 32,
        "generated_at": 1_000,
        "ai_score": 92,
        "safety_report": {
            "verdict_recommendation": "CLEAR",
            "hard_veto": False,
            "checks": [{"id": check, "status": "pass"} for check in REQUIRED_SAFETY_CHECKS],
        },
        "onchain": {
            "verified": True,
            "mint_authority_revoked": True,
            "freeze_authority_revoked": True,
            "top10_share": 0.12,
        },
        "liquidity_usd": 75_000,
        "price_usd": 0.00001,
    }


def test_live_candidate_requires_every_evidence_gate() -> None:
    decision = evaluate_live_candidate(_candidate(), now=1_010)
    assert decision["eligible"] is True
    assert decision["status"] == "ELIGIBLE"
    assert decision["blockers"] == []


def test_missing_curve_ai_and_full_safety_report_block_entry() -> None:
    candidate = _candidate()
    candidate.pop("curve_account")
    candidate["ai_score"] = None
    candidate.pop("safety_report")
    decision = evaluate_live_candidate(candidate, now=1_010)
    assert decision["eligible"] is False
    assert decision["status"] == "BLOCKED"
    assert "verified bonding-curve account missing" in decision["blockers"]
    assert "verified AI score unavailable" in decision["blockers"]
    assert "full on-chain safety report missing" in decision["blockers"]


def test_stale_or_unsafe_candidate_is_blocked() -> None:
    candidate = _candidate()
    candidate["generated_at"] = 900
    candidate["onchain"]["freeze_authority_revoked"] = False
    candidate["onchain"]["top10_share"] = 0.40
    decision = evaluate_live_candidate(candidate, now=1_010)
    assert decision["eligible"] is False
    assert any("stale" in reason for reason in decision["blockers"])
    assert "freeze authority not proven revoked" in decision["blockers"]
    assert any("top-10 concentration" in reason for reason in decision["blockers"])


def test_missing_any_required_safety_check_blocks_entry() -> None:
    candidate = _candidate()
    candidate["safety_report"]["checks"].pop()
    decision = evaluate_live_candidate(candidate, now=1_010)
    assert decision["eligible"] is False
    assert any("safety check not passed" in reason for reason in decision["blockers"])
