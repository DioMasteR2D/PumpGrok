# Solana / AI repository integration review

Date: 2026-11-06
Target: PumpGrok
Branch: research/solana-repo-integrations

## Decision

Do not vendor or execute the five repositories wholesale. PumpGrok's safety boundary remains authoritative: research and paper/replay only; no private keys, no signing, no transaction broadcast, and no path that can move real funds. Integrate only isolated, read-only data and analysis capabilities after tests.

## Repository review

| Repository | What it provides | PumpGrok fit | Decision |
|---|---|---|---|
| [GMGNAI/gmgn-skills](https://github.com/GMGNAI/gmgn-skills) | GMGN CLI / agent skills for Solana token, market, holder, wallet, smart-money and K-line research. It also exposes swap and strategy-order commands. | High for discovery and due diligence; external API key and service dependency. | First read-only adapter candidate. Allow market/token/holder/wallet/track reads only. Explicitly block swap, cooking, order strategy, multi-swap and wallet mutation commands. |
| [chainstacklabs/pumpfun-bonkfun-bot](https://github.com/chainstacklabs/pumpfun-bonkfun-bot) | Python bot and cookbook for listening to Pump.fun, letsbonk.fun and StonkFun creation/trade events, then buying and exiting. README explicitly says it is for learning and not production. | Useful reference for event detection, curve state and launchpad protocol behavior. | Study selected read/listen/curve concepts; do not copy its autonomous trading loop or wallet execution. Treat all protocol assumptions as unverified until fixture/replay tests pass. |
| [0xfnzero/sol-trade-sdk](https://github.com/0xfnzero/sol-trade-sdk) | Rust SDK for low-latency Solana DEX transaction construction and submission, Pump.fun/PumpSwap/LaunchLab/Raydium/Meteora support and MEV routing. | Potential future execution research, but directly conflicts with PumpGrok's no-sign/no-send boundary. | Reference only. Do not add as a runtime dependency or expose transaction/sign/broadcast APIs. Offline parsing/replay examples may be studied separately. |
| [elizaos/eliza](https://github.com/elizaos/eliza) | Large TypeScript agent runtime and app stack, plugins, UI and Android/Linux distribution tooling. | Useful patterns for agent/plugin boundaries; large overlapping framework would add complexity. | Reference architecture only. Do not replace PumpGrok's ten-seat desk or import the monorepo. |
| [TraderAlice/OpenAlice](https://github.com/TraderAlice/OpenAlice) | Local AI trading/research workspace, agents, market tools, scheduled issues and staged trading workflows. Its README describes trading execution as beta. | Useful UX and research-workspace concepts; separate desktop application with its own stack. | Reference UX only. Do not embed its trading execution or broker integrations. |

## Proposed integration order

1. **GMGN read-only research connector** — optional provider behind the existing datasource/tool interfaces. Start with market trending/new-token lists, token details/security, holder analysis and smart-money/wallet activity. Use the public demo credential only for read-only smoke tests; never place credentials in source, logs or committed config. If the provider requires a personal API key, keep it in the operator's secret store and make the connector unavailable when unset.
2. **Chainstack event/curve research** — compare event schemas and curve calculations against PumpGrok fixtures. No wallet, buy, sell, transaction builder or broadcaster code.
3. **SDK and agent-framework comparison** — document useful interfaces and replay-safe parsing patterns; no runtime dependency until there is a concrete, tested need.
4. **UI/workspace inspiration** — borrow only interaction ideas after the existing PumpGrok operator workflow is verified.

## Required gates before any code integration

- New provider is opt-in and read-only by construction.
- Network responses are treated as untrusted data; validate mint addresses, timestamps, numeric ranges and source freshness.
- Provider failures, rate limits and stale data fail closed: no candidate promotion and no simulated fill based on missing prices.
- Store source, fetch time and raw-response hash for replay/audit; redact credentials and wallet identifiers from logs.
- Add deterministic fixtures and tests for malformed responses, duplicate events, out-of-order events, timeouts and HTTP 429.
- Preserve the existing risk veto, paper-only boundary, kill switch and approval-ticket lifecycle.
- No private-key handling, signing, swap submission, order placement or transaction broadcasting.

## Notes

- GMGN's own README describes both read-only analytics and powerful trading endpoints. The connector must expose an allowlist of read methods rather than a generic CLI passthrough.
- Chainstack's README labels its bot as learning-purpose / not production. It is a protocol reference, not a production-ready dependency.
- The Sol Trade SDK README describes transaction building, signing and multi-channel submission. These capabilities are out of scope for PumpGrok.
- Eliza and OpenAlice are substantial independent applications. Copying either wholesale would create a second agent/runtime stack rather than improve the existing desk.

## Source links

- https://github.com/GMGNAI/gmgn-skills
- https://github.com/chainstacklabs/pumpfun-bonkfun-bot
- https://github.com/0xfnzero/sol-trade-sdk
- https://github.com/elizaos/eliza
- https://github.com/TraderAlice/OpenAlice
- https://github.com/DioMasteR2D/PumpGrok
