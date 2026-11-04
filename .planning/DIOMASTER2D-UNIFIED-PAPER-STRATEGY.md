# DioMasteR2D Grokbot — Unified Paper-Trading Strategy

Status: approved product specification; implementation must remain PAPER ONLY.

## Non-negotiable mode
- The gateway must refuse live mode.
- No wallet signing, swaps, private keys, seed phrases, or real-money execution.
- Unknown, stale, missing, or unverifiable safety data means NO BUY.
- Market discovery and paper trading must be visibly distinguished from agent connectivity.

## Entry filters
- Solana token discovery from more than one independent market source where practical.
- Minimum verified pool liquidity: USD 40,000.
- Mint authority must be revoked.
- Freeze authority should also be revoked where the token program exposes it; otherwise mark unknown and reject until verified.
- Top-holder / whale concentration must be at most 25%, excluding known LP/burn/vesting/system accounts only when their classification is verifiable.
- AI/agent score at least 70/100.
- Four explicit approvals are required before a paper entry: safety/rug, whale concentration, market signal, and chief/risk approval.
- A failed critical gate or unknown critical field rejects the candidate. Never fabricate an AI score or on-chain facts.

## Portfolio and exits
- Paper position size: 8% of available paper equity per position.
- Initial stop loss: -6% from the paper entry price.
- Take-profit target band: +70% to +130% (percentage return, NOT market capitalization).
- Trailing exit: once the position has reached the +70% profit zone, track its highest observed price and paper-sell on a 12% drawdown from that high.
- Hard profit cap: +130%; paper-sell when reached.
- Stop loss remains active from entry. Exit evaluation must be deterministic and idempotent.
- Do not silently carry forward legacy defaults such as +10% TP, -5% SL, $2 per trade, or a 10-position limit. Position count is governed by the configured paper risk budget until a separate approved limit exists.

## Ten-agent responsibilities
1. Chief — orchestration and final decision.
2. Scout — new-pool/token discovery.
3. Risk — position sizing, limits, kill switch, final risk gate.
4. Whale — top-holder concentration and large-wallet analysis.
5. Sniper — paper entry only after approvals.
6. Rug — mint/freeze authority and contract safety checks.
7. Exit — stop, profit-band, and trailing exit monitoring.
8. Shill — social/community signals; supporting evidence only, never overrides safety gates.
9. Signal — price, volume, liquidity, momentum and market structure.
10. Journal — immutable decision, source, order, fill, exit and P&L history.

## Required Android experience
- Market tab showing discovered coins, symbol/name, mint, pool, price, liquidity, volume, market cap, source timestamps and AI score.
- Coin detail with all safety checks, agent votes/reasons, and source links.
- Visible paper BUY / SELL / HOLD / REJECT actions and transaction status.
- Open positions with entry, live indicative price, size, unrealized P&L, high-water mark, stop and exit state.
- Closed trades, realized P&L, win/loss counts, equity curve and per-agent decision history.
- Activity feed showing each discovery, filter, agent vote, approval/rejection, paper order, fill, price update, stop/trailing event and close.
- Market charts/animations must be driven by actual timestamped price data; never display decorative animation as if it were market activity.
- Show source freshness and clear stale/offline states.

## Implementation and acceptance gates
1. Build discovery with multiple sources and source timestamps; deduplicate by mint/pool.
2. Verify liquidity and on-chain authority/holder data; fail closed on missing data.
3. Implement the 10-agent decision pipeline with explicit structured votes and reason codes.
4. Route paper orders through the existing RiskEngine, PaperAdapter and append-only LedgerStore. Never create fake fills in the UI.
5. Add authenticated read APIs for market candidates, positions, events and paper performance; preserve per-seat authorization.
6. Add Android Market, Coin Detail, Positions and Activity screens with refresh/polling and animated visual feedback tied to real data.
7. Add deterministic unit/integration tests for every filter, risk boundary, exit condition, duplicate event and restart recovery.
8. Run CI and Android APK build; deploy Render only after tests pass. Verify live health and real endpoint responses before distributing the APK.

## Transparency
A connected/ONLINE agent seat only proves that its MCP endpoint is reachable. It does not prove that the agent is scanning, voting, or trading. The UI must report those states separately.
