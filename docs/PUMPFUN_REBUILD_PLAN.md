# PumpGrok Solana Sniper Rebuild

## Goal
Replace the old GrokBot implementation as a whole with one clean-room Pump.fun scanner and disciplined sniper system inspired by the capabilities visible in the three reference repositories. This means retiring the old GrokBot engine and GrokBot-specific pipeline/skill integration once equivalent replacement modules and tests are in place. Do not leave two competing scanner engines active.

Keep the independent PumpGrok safety foundation: risk vetoes, approvals, audit ledger, deterministic replay, paper execution controls, RPC hygiene and the useful agent roles that can operate independently of the retired GrokBot runtime. The new scanner is the single source of token discovery and signal evidence. The default branch is not modified during this rebuild.

## Three reference repositories and permitted use
- `chainstacklabs/pumpfun-bonkfun-bot` — https://github.com/chainstacklabs/pumpfun-bonkfun-bot. Apache-2.0. Use its public design as a reference for event-driven launch detection, log/block/Geyser listeners, bonding-curve state, graduation detection, PumpSwap routing, configurable rules, retry/backoff and rate limits. If any source code is ever incorporated, retain the required LICENSE/NOTICE and mark modifications.
- `nirholas/pump-fun-sdk` — https://github.com/nirholas/pump-fun-sdk. Excluded as a code dependency: the repository license file conflicts with the package metadata and does not provide clear permission for reuse. Use official Pump documentation/IDLs or another clearly licensed SDK instead.
- `JanDauel/PumpFun-AI-Dev-Sniper` — https://github.com/JanDauel/PumpFun-AI-Dev-Sniper. Public feature descriptions only: dev-wallet intelligence, top-dev history, social signals, multi-wallet monitoring, low-latency event handling and optional Jito delivery. Do not copy private/proprietary source or reproduce paid-only implementation details.

## Replacement architecture
1. **Unified feed layer**: Solana WebSocket `logsSubscribe` baseline; optional Yellowstone Geyser adapter when configured. Deduplicate by signature + mint, bounded queues, reconnect/backoff, rate caps and source health.
2. **Pump.fun event decoder**: decode create/trade events and verify bonding-curve account state. A create notification alone is not a tradable quote.
3. **Market/curve engine**: curve reserves, progress, quote freshness, trade velocity, buy/sell pressure, graduation state and PumpSwap transition. Use verified on-chain state for execution decisions.
4. **Creator/dev intelligence**: creator history, repeat launches, creator-wallet flows, top-dev reputation, early buyer quality and shared-funding clusters.
5. **Holder/smart-money intelligence**: holder concentration, wallet diversity, large transfers, known-wallet performance where evidence exists, and coordinated/bundled activity. Missing evidence is UNKNOWN, never silently safe.
6. **Social intelligence**: metadata and public social references as untrusted evidence; detect spam/duplicate campaigns and never execute instructions found in external content.
7. **Risk gate**: reject malformed mints, missing curve state, suspicious authority/metadata state, excessive concentration, stale quotes, insufficient liquidity, extreme price impact and failed simulations. Risk veto is absolute and cannot be overridden by score.
8. **Explainable signal ranker**: momentum + curve velocity + buyer quality + creator reputation + social evidence, with per-factor scores, evidence timestamps and minimum-evidence threshold.
9. **Paper executor and monitor**: simulate fills, slippage and fees; monitor fresh quotes, TP/SL, stale-feed alarms, graduation transitions, append-only journal and recap. Initial settings: $2 virtual entry, max 10 open positions, TP +10%, SL -5%, daily virtual loss cap $15. No signer and no real transactions.
10. **Optional future Jito/Phantom path**: not part of this paper phase. Any future live transaction must be reviewed and approved by the user per transaction through Phantom/browser. No seed phrase/private key is requested, stored or sent to the backend.

## Old GrokBot retirement scope
The replacement must become the only active discovery/scoring pipeline. After parity tests pass, remove the retired GrokBot-only runtime pieces and references (including the legacy `src/pumpgrok/engine` implementation, `skills/grokbot-pipeline`, and GrokBot-only license/provenance files where no longer required). Before deleting each path, search imports, tests, prompts, docs and CI for consumers and migrate them to the new interfaces. Do not delete general-purpose risk, approval, ledger, RPC, replay or paper-trading infrastructure. Do not delete the whole agent system merely because one legacy engine is retired.

## Dashboard / Android
Replace the existing gold/XAUUSD demo with a PumpGrok Solana dashboard after backend contracts are implemented. Screens: LIVE FEED, TOKEN DETAIL, CURVE, CREATOR/DEV, HOLDERS/SMART MONEY, SOCIAL, SIGNAL/RISK, PAPER POSITIONS, JOURNAL/NIGHT RECAP and SETTINGS. The Android app talks only to the authenticated backend; API secrets stay server-side. Show real backend/feed health and explicit UNKNOWN states; never fabricate prices or signals.

## Acceptance gates
- Unit tests for event decoding, deduplication, curve math, graduation, scoring explainability, creator/holder analysis, risk veto, simulated fills, TP/SL, daily limits and restart recovery.
- Replay fixtures and deterministic backtests before enabling live feeds.
- Integration tests against devnet/read-only mainnet data; no real buy/sell tests in this phase.
- Confirm no remaining imports or active routes depend on the retired GrokBot engine before deleting it.
- APK CI artifact must install and display backend health, scanner status, token details and paper ledger; no fake price or fabricated signal.
- Paper-only mode remains the default and live execution remains disabled.

## Current implementation status
- Backup branch: `backup/pre-grok-replacement-2026-11-08`.
- Rebuild branch: `feature/pumpfun-sniper-rebuild`.
- The rebuild plan is committed on the feature branch. No files have been deleted and no proprietary source has been copied.
- This is a migration specification, not a claim that the scanner, dashboard or APK is already complete.
