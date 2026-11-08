# Video parity specification — PumpGrok WHALE

This specification records the visible product behaviour from the user-supplied 35-second reference video. It is a clean-room product target, not a claim that private source code or backend logic from the reference app is available.

## Product shell
- Mobile-first dark dashboard branded PumpGrok / WHALE.
- Initial setup screen lists the three public reference repositories as strategy sources and shows setup progress. This is attribution/context only; the app must not clone or execute unlicensed code at runtime.
- Phantom connect screen shows network, connected public wallet address and connection status. It must never request a seed phrase/private key.
- Main header shows bot mode and connection state. Paper/live mode must be explicit and impossible to confuse.

## Main live dashboard
- Portfolio balance and PnL summary, with a time-series chart.
- Token/strategy source activity cards for:
  - chainstacklabs/pumpfun-bonkfun-bot — launch/curve event monitoring and graduation tracking.
  - nirholas/pump-fun-sdk — SDK reference excluded from code reuse until licensing is unambiguous; use official Pump docs/IDL or a clearly licensed alternative.
  - JanDauel/PumpFun-AI-Dev-Sniper — public feature concepts only; no private code.
- Agent analytics panels: LAUNCH, CURVE, HOLDERS, DEV, SOCIAL, SNIPER. Each panel displays current state, observed count/metrics, last update time, source and UNKNOWN/STALE status when data is absent.
- Core decisions/event stream with UTC time, token mint, action/verdict, evidence summary and paper execution status.
- Live backend/feed heartbeat, RPC health and last successful refresh.

## Token detail
- Token identity: mint, name/symbol, creator, age, metadata/social references.
- LAUNCH: create transaction, slot, signature and verification state.
- CURVE: verified reserves, progress, price/velocity and graduation/PumpSwap transition.
- HOLDERS: top-holder concentration, creator share, wallet diversity, early buyers and large transfers.
- DEV: creator/deployer history, linked wallets and historical outcomes when evidence is available.
- SOCIAL: website/X/Telegram presence, consistency and spam/duplication flags.
- SNIPER: explainable factor score, missing evidence, risk flags and RISK verdict.
- All evidence is timestamped and sourced; unknown is not interpreted as safe.

## Paper portfolio and Night Recap
- Paper portfolio: virtual balance, open positions, realized/unrealized PnL, trade history and current risk limits.
- Starting paper settings: $2 virtual entry per position, up to 10 open positions, +10% take-profit, -5% stop-loss, $15 daily virtual loss cap.
- Night Recap: starting/ending paper balance, realized paper PnL, return multiple/percentage, trades, wins/losses, best/worst trade, agent/feed health and notable risk events.
- Every metric is computed from the append-only paper ledger. Never fabricate a wallet balance, return, trade, win rate or signal.

## Execution and wallet safety
- First release is paper-only. No signer, private-key storage, transaction signing or broadcast.
- Phantom integration in the first release is read-only connection/public-address display only.
- A later live version, if ever approved, must use explicit Phantom transaction approval for each exact transaction; no seed phrase/private key is collected by PumpGrok.
- RISK veto and human approval remain mandatory; WHALE intelligence never authorises an order.

## Acceptance checklist
- [ ] Mobile dashboard visually matches the reference information hierarchy and dark visual style.
- [ ] Phantom read-only connection state is real and safely handled.
- [ ] Launch, curve, holders, developer, social and sniper panels show live sourced backend evidence.
- [ ] Core decisions feed is backed by journal records.
- [ ] Paper portfolio is computed from real paper fills only.
- [ ] Night Recap is reproducible from the ledger.
- [ ] Backend/feed failures display offline/UNKNOWN, never demo numbers.
- [ ] Automated tests cover stale feeds, missing evidence, risk veto, paper fills, TP/SL and recap calculations.
