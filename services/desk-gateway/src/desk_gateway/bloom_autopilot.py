"""Fail-closed entry gate between Solana discovery and Bloom execution.

This module does not place orders. It defines the evidence contract a candidate
must satisfy before any autonomous executor may call Bloom. Missing evidence is
a blocker, never a pass.
"""
from __future__ import annotations

import math
import time
from typing import Any

REQUIRED_SAFETY_CHECKS = (
    "mint_authority",
    "freeze_authority",
    "lp_status",
    "top10_concentration",
    "deployer_history",
    "token2022_extensions",
    "liquidity_depth",
)


def evaluate_live_candidate(
    candidate: dict[str, Any],
    *,
    now: float | None = None,
    min_ai_score: float = 80.0,
    min_liquidity_usd: float = 40_000.0,
    max_top10_share: float = 0.25,
    max_age_seconds: float = 30.0,
) -> dict[str, Any]:
    """Return a deterministic live-entry decision; fail closed on any missing proof."""
    blockers: list[str] = []
    current = time.time() if now is None else float(now)

    mint = candidate.get("mint")
    if not isinstance(mint, str) or not 32 <= len(mint) <= 44:
        blockers.append("valid Solana mint missing")

    curve = candidate.get("curve_account")
    if not isinstance(curve, str) or not 32 <= len(curve) <= 44:
        blockers.append("verified bonding-curve account missing")

    generated_at = candidate.get("generated_at")
    try:
        age = current - float(generated_at)
        if not math.isfinite(age) or age < 0 or age > max_age_seconds:
            blockers.append("market evidence is stale or has invalid timestamp")
    except (TypeError, ValueError):
        blockers.append("market evidence timestamp missing")

    ai_score = candidate.get("ai_score")
    try:
        score = float(ai_score)
        if not math.isfinite(score) or score < min_ai_score or score > 100:
            blockers.append(f"AI score must be at least {min_ai_score:g}/100")
    except (TypeError, ValueError):
        blockers.append("verified AI score unavailable")

    safety = candidate.get("safety_report")
    if not isinstance(safety, dict):
        blockers.append("full on-chain safety report missing")
    else:
        if safety.get("verdict_recommendation") != "CLEAR":
            blockers.append("safety verdict is not CLEAR")
        if safety.get("hard_veto") is not False:
            blockers.append("safety hard-veto is active or unknown")
        rows = safety.get("checks")
        if not isinstance(rows, list):
            blockers.append("individual safety-check evidence missing")
        else:
            by_id = {
                row.get("id"): row
                for row in rows
                if isinstance(row, dict) and isinstance(row.get("id"), str)
            }
            for check_id in REQUIRED_SAFETY_CHECKS:
                row = by_id.get(check_id)
                if row is None or row.get("status") != "pass":
                    blockers.append(f"safety check not passed: {check_id}")

    onchain = candidate.get("onchain")
    if not isinstance(onchain, dict) or onchain.get("verified") is not True:
        blockers.append("mint account not verified on-chain")
    else:
        if onchain.get("mint_authority_revoked") is not True:
            blockers.append("mint authority not proven revoked")
        if onchain.get("freeze_authority_revoked") is not True:
            blockers.append("freeze authority not proven revoked")
        top10 = onchain.get("top10_share")
        try:
            concentration = float(top10)
            if not math.isfinite(concentration) or concentration > max_top10_share:
                blockers.append(f"top-10 concentration exceeds {max_top10_share:.0%} or is invalid")
        except (TypeError, ValueError):
            blockers.append("top-10 holder concentration unavailable")

    try:
        liquidity = float(candidate.get("liquidity_usd"))
        if not math.isfinite(liquidity) or liquidity < min_liquidity_usd:
            blockers.append(f"liquidity below ${min_liquidity_usd:,.0f}")
    except (TypeError, ValueError):
        blockers.append("verified pool liquidity unavailable")

    try:
        price = float(candidate.get("price_usd"))
        if not math.isfinite(price) or price <= 0:
            blockers.append("valid market price unavailable")
    except (TypeError, ValueError):
        blockers.append("valid market price unavailable")

    return {
        "eligible": not blockers,
        "status": "ELIGIBLE" if not blockers else "BLOCKED",
        "blockers": blockers,
        "evaluated_at": int(current),
    }
