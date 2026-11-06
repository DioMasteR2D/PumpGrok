# DioMasteR2D Grok Bot Integration Status

Status date: 2026-11-06
Foundation branch: `feat/diomaster-grokbot-integration-foundation`
Foundation base: `research/solana-repo-integrations`
Existing mobile-gateway branch: `bot-02-risk/android-companion-mvp`

## Purpose

This record separates components that are present in the repository from integrations that are only planned. A UI label, a pinned Git submodule, or a demo card is not proof that a service is connected or that a trade can execute.

## Audited upstream components

The research branch pins these five Git submodules:

| Component | Pinned repository | What it can contribute | Integration status in PumpGrok |
|---|---|---|---|
| GMGN skills | `GMGNAI/gmgn-skills` | Agent procedures / GMGN workflows | Submodule pinned; no verified GMGN API client or authenticated feed registered |
| Pump.fun / Bonkfun bot | `chainstacklabs/pumpfun-bonkfun-bot` | Launch/trade stream and execution examples | Submodule pinned; upstream README says learning use and requires a private key for its trading path; do not import its signer into PumpGrok |
| Solana trade SDK | `0xfnzero/sol-trade-sdk` | Rust DEX transaction construction/signing/submission | Submodule pinned; not wired into PumpGrok; signing path must remain outside the current no-key desk |
| elizaOS | `elizaos/eliza` | Agent runtime and plugin framework | Submodule pinned; not a running runtime or registered PumpGrok tool provider |
| OpenAlice | `TraderAlice/OpenAlice` | Agent orchestration / workspace concepts | Submodule pinned; not embedded or running inside the Android app |

Pinned source revisions are recorded by the Git tree at the integration branch. Re-check upstream license, API terms, security posture, and dependency compatibility before vendoring or executing any code.

## Existing PumpGrok capabilities

- Ten role instruction files and the skill library are present.
- The typed read-tool layer includes market price, liquidity, trades, holder snapshots, mint/freeze authorities, top holders, deployer history, LP status, and priority-fee reads.
- The paper/research desk is the supported operating model.
- The foundation branch Android project is a WebView wrapper loading a local HTML asset; its reference dashboard values are marked DEMO and are not live data.

## Existing deployed mobile-gateway branch (audited separately)

The Render service `diomaster2d-pumpgrok-gateway` is configured to deploy from `bot-02-risk/android-companion-mvp`, not from this foundation branch. Its last inspected Render deployment was marked `live` (commit `ea0c3ad2cf0d18c05da64a7646091fd281a3f43a`, 2026-11-04). Render application logs on 2026-11-06 showed successful authenticated MCP requests (HTTP 200 and initialization notifications 202) and no application error entries in the inspected 2026-11-06 window.

That deployed branch contains a distinct mobile market implementation:
- Authenticated read-only `GET /market/home`, `/market/search`, and `/market/candidates` routes for CHIEF/SCOUT tokens.
- GeckoTerminal trending/new pools, DexScreener profile/pair enrichment, Jupiter Price V3 cross-check, and a PumpPortal new-token/migration WebSocket cache.
- Ten transparent, rule-based role assessments (SCOUT, SIGNAL, WHALE, RUG, RISK, SNIPER, EXIT, SHILL, JOURNAL, CHIEF).
- Market observations are explicitly blocked from entry; the current feed sets `paper_entry_enabled=false` and does not claim an AI score or executed trades.

Known provider issue: Render logs from 2026-11-04 recorded HTTP 429 responses from both GeckoTerminal new pools and DexScreener token profiles. These were not observed in the inspected 2026-11-06 error-log window, but the providers remain rate-limited dependencies and need cooldown/fallback tests. The home feed's 30-second cache and PumpPortal stream do not prove that every candidate has complete safety evidence.

This is not GMGN integration. No verified GMGN account/feed adapter was found in the inspected deployed branch. The wallet endpoints present in that branch relate to a separate Bloom API integration; they are not Phantom connection and must not be described as such.

## Verified blockers (do not represent these as completed)

1. `SETUP.md` is a host-runtime bootstrap procedure. It creates local desk folders and asks the operator to install skills and create agent seats; GitHub commits alone do not create those host-side agents or Trading Floor.
2. The GMGN submodule is not proof of a connected GMGN account, API, or streaming feed. No verified GMGN credential flow or adapter is registered in the inspected PumpGrok tool registry or mobile-gateway branch.
3. `scout pipeline` is registered but not implemented in the foundation checkout. The deployed mobile branch has a separate read-only market scanner; it is not the same CLI pipeline.
4. The live adapter is a refusing stub in the foundation checkout. The live gate documents unmet preconditions, including no live adapter implementation.
5. The repository security policy prohibits private keys and seed phrases from entering chat, files, settings, environment variables, logs, or agents. The Chainstack example's private-key configuration must not be copied into PumpGrok.
6. The foundation Android client has no verified Phantom Wallet Adapter integration. The deployed mobile market API is not a wallet adapter. Adding Android INTERNET permission only enables future HTTPS networking; it does not connect a wallet.
7. No APK build or device installation has been verified by this foundation PR.

## Target integration boundary

Use a read-only service boundary first:

- Android app -> HTTPS desk API (read-only endpoints, authenticated session, no wallet secrets).
- Desk API -> existing PumpGrok typed read tools and ledger/report views.
- GMGN connector -> only documented, authorized GMGN endpoints or an explicitly supported GMGN skill/runtime integration. If unavailable, return `unavailable`; never fabricate a feed.
- Candidate analysis -> source timestamp, freshness, mint, liquidity, volume windows, top-holder concentration, authority flags, LP status, developer history, and smart-money evidence.
- Scoring -> transparent, versioned 0-100 rubric. Missing/stale critical evidence must produce `BLIND` / reject, not a guessed score. Do not label rule-based role assessments as LLM/AI agent output.
- Journal -> append every candidate, BUY proposal, SELL proposal, and SKIP reason.
- Wallet -> future Phantom connection using the official wallet connection protocol from a secure HTTPS origin. Store only the public key and connection status. Never request or persist seed phrases/private keys.
- Execution -> remain disabled in this release. Any future execution design requires a separate security review, explicit human approval for exact ticket/mint/size/slippage, and a newly implemented and tested adapter. Do not toggle the current live gate.

## Screenshot strategy values are not approved configuration

The reference screenshot proposes an 8% balance allocation, -6% stop, +15% trailing activation, 70/100 score threshold, liquidity above $50k, and a 12-hour session. These are illustrative strategy parameters, not verified PumpGrok defaults and not authorization to enable real trades. The deployed scanner currently uses its own different safety thresholds and always blocks entry while critical evidence or scoring is missing. Do not silently overwrite either policy. Evaluate proposed parameters in replay/paper research only after units, data availability, and risk bounds are reviewed.

## Completion criteria before calling the integration connected

- [ ] GMGN data source has a documented, authorized API/feed and an adapter with tests, timestamps, freshness, rate limits, and failure behavior.
- [ ] Read-only HTTPS API exposes only existing typed data and journal views; authentication and deployment configuration are tested.
- [ ] Android app fetches the API, shows connection/freshness/error state, and never substitutes demo values for missing live data.
- [ ] Candidate scanner produces evidence-backed leads and explicit skip reasons, with resilient multi-provider fallback and 429 cooldown tests.
- [ ] Scoring tests cover missing, stale, conflicting, concentrated-holder, authority, liquidity, and volume cases.
- [ ] Phantom connection is implemented with the official wallet connection protocol; only the public key is retained; no signing or transaction submission is wired.
- [ ] Unit, integration, security, Android build, and device tests pass; build artifact and checksum are recorded.
- [ ] Separate review approves any later paper/live changes. Live remains refused in this release.

## Change made in this foundation branch

The Android manifest now declares `android.permission.INTERNET` so a future HTTPS API client can communicate. Cleartext HTTP remains disabled. This is a prerequisite only, not evidence of a working API, GMGN, or Phantom connection.
