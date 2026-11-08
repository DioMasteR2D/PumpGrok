# PumpGrok Solana Sniper Rebuild

## Goal
Replace the retired GrokBot screening engine with an independently implemented Pump.fun launch scanner and disciplined sniper workflow, while retaining the repository's audit, risk, and approval controls. This branch is a replacement implementation track; the default branch is not modified.

## Reference-derived capabilities (not copied source)
- Chainstack pumpfun-bonkfun-bot (Apache-2.0): event-driven launch detection, selectable log/block/Geyser listeners, bonding-curve reads, graduation detection, PumpSwap routing, configurable entry/exit rules, retry/backoff and rate limiting. Preserve its LICENSE/NOTICE if any source from it is later incorporated.
- PumpFun-AI-Dev-Sniper public description only: multi-wallet/dev-wallet intelligence, social signals, top-dev history, low-latency event handling, optional Jito transaction delivery. Its private implementation is not available and is not used.
- pump-fun SDK repository is excluded because its repository LICENSE conflicts with package metadata. Use official Pump documentation/IDLs or another clearly licensed implementation instead.

## Proposed pipeline
1. **Feed adapters**: Solana WebSocket logsSubscribe as baseline; optional Yellowstone Geyser adapter when the operator supplies a provider endpoint. Deduplicate by signature + mint, bounded queues, reconnect/backoff, provider rate caps.
2. **Launch decoder**: decode Pump create events and read bonding-curve account state. Do not treat an unverified create event as a tradable quote.
3. **Enrichment**: metadata/social links, creator history, creator/dev wallet activity, holder concentration, early buyer diversity, bundled/coordinated activity, curve progress and graduation state. Missing evidence is UNKNOWN, never silently scored as safe.
4. **Risk gate**: hard reject malformed mints, missing curve state, suspicious authority/metadata state, excessive concentration, stale quotes, insufficient liquidity, extreme price impact, and failed simulation. A risk veto cannot be overridden by the signal score.
5. **Signal ranker**: weighted momentum + buyer quality + curve velocity + creator reputation + social evidence, with explainable component scores and a minimum evidence threshold.
6. **Paper execution**: simulated quote/fill/slippage/fees, max 10 open positions, $2 virtual entry per position, TP +10%, SL -5%, daily virtual loss cap $15. No wallet signer and no real transactions in this phase.
7. **Position monitor**: fresh quote checks, stop-loss/take-profit, stale-feed alarms, graduation transition to PumpSwap pricing, append-only trade journal and daily recap.
8. **Future live adapter**: disabled by construction; if ever added, transaction signing remains in Phantom/browser with explicit per-transaction user approval. No seed phrase or private key in this service.

## Dashboard / Android
Rebuild the existing gold-android XAUUSD placeholder as a PumpGrok Solana dashboard after backend contracts are implemented. Screens: LIVE FEED, TOKEN DETAIL, CREATOR/DEV, HOLDERS, SIGNAL/RISK, PAPER POSITIONS, JOURNAL/RECAP, SETTINGS. Android app talks only to the authenticated backend; API secrets stay server-side.

## Acceptance gates
- Unit tests for event decoding, deduplication, curve math, graduation, score explainability, risk veto, simulated fills, TP/SL, daily limits and restart recovery.
- Replay fixtures and deterministic backtests before any live feed.
- Integration test against devnet/read-only mainnet data; no real buy/sell tests in this phase.
- APK CI artifact must install and display live backend health, scanner status, token details and paper ledger; no fake price or fabricated signals.

## Current implementation status
- Backup branch created from the current main head.
- Rebuild branch created from the same head.
- No files deleted from main. No proprietary source copied.
- This document is the implementation specification, not a claim that the scanner or APK is already complete.