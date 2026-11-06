# DioMasteR2D Grok Bot Integration Status

Status date: 2026-11-06
Implementation branch: `feat/diomaster-grokbot-integration-foundation`
Base: `research/solana-repo-integrations`

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
- The Android project is a WebView wrapper loading a local HTML asset.
- The current HTML asset contains reference-video sample metrics and is explicitly marked DEMO; those figures are not live data.

## Verified blockers (do not represent these as completed)

1. `SETUP.md` is a host-runtime bootstrap procedure. It creates local desk folders and asks the operator to install skills and create agent seats; GitHub commits alone do not create those host-side agents or Trading Floor.
2. The GMGN submodule is not proof of a connected GMGN account, API, or streaming feed. No verified GMGN credential flow or adapter is registered in the PumpGrok tool registry.
3. `scout pipeline` is registered but not implemented in this checkout.
4. The live adapter is a refusing stub. The live gate documents nine unmet preconditions, including no live adapter implementation.
5. The current repository policy prohibits private keys and seed phrases from entering chat, files, settings, environment variables, logs, or agents. The Chainstack example's private-key configuration must not be copied into PumpGrok.
6. The Android client has no verified backend API contract or Phantom Wallet Adapter integration. Adding Android INTERNET permission only enables future HTTPS networking; it does not connect a backend or wallet.
7. No APK build or device installation has been verified by this change.

## Target integration boundary

Use a read-only service boundary first:

- Android app -> HTTPS desk API (read-only endpoints, authenticated session, no wallet secrets).
- Desk API -> existing PumpGrok typed read tools and ledger/report views.
- GMGN connector -> only documented, authorized GMGN endpoints or an explicitly supported GMGN skill/runtime integration. If unavailable, return `unavailable`; never fabricate a feed.
- Candidate analysis -> source timestamp, freshness, mint, liquidity, volume windows, top-holder concentration, authority flags, LP status, developer history, and smart-money evidence.
- Scoring -> transparent, versioned 0-100 rubric. Missing/stale critical evidence must produce `BLIND` / reject, not a guessed score.
- Journal -> append every candidate, BUY proposal, SELL proposal, and SKIP reason.
- Wallet -> future browser-based Phantom connection using the official wallet-adapter / deeplink flow. Store only the public key and connection status. Never request or persist seed phrases/private keys.
- Execution -> remain disabled in this release. Any future execution design requires a separate security review, explicit human approval for exact ticket/mint/size/slippage, and a newly implemented and tested adapter. Do not toggle the current live gate.

## Screenshot strategy values are not approved configuration

The reference screenshot proposes an 8% balance allocation, -6% stop, +15% trailing activation, 70/100 score threshold, liquidity above $50k, and a 12-hour session. These are illustrative user-requested strategy parameters, not verified PumpGrok defaults and not an authorization to enable real trades. Do not silently overwrite the repository's risk policy. Evaluate proposed parameters in replay/paper research only after their units, data availability, and risk bounds are reviewed.

## Completion criteria before calling the integration connected

- [ ] GMGN data source has a documented, authorized API/feed and an adapter with tests, timestamps, freshness, rate limits, and failure behavior.
- [ ] Read-only HTTPS API exposes only existing typed data and journal views; authentication and deployment configuration are tested.
- [ ] Android app fetches the API, shows connection/freshness/error state, and never substitutes demo values for missing live data.
- [ ] Candidate scanner produces evidence-backed leads and explicit skip reasons.
- [ ] Scoring tests cover missing, stale, conflicting, concentrated-holder, authority, liquidity, and volume cases.
- [ ] Phantom connection is implemented with the official wallet connection protocol; only the public key is retained; no signing or transaction submission is wired.
- [ ] Unit, integration, security, Android build, and device tests pass; build artifact and checksum are recorded.
- [ ] Separate review approves any later paper/live changes. Live remains refused in this release.

## Change made in this branch

The Android manifest now declares `android.permission.INTERNET` so a future HTTPS API client can communicate. Cleartext HTTP remains disabled. This is a prerequisite only, not evidence of a working API, GMGN, or Phantom connection.
