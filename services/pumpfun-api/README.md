# PumpGrok Pump.fun dashboard service

## Components
- `server.py`: read-only JSON dashboard API with SQLite event storage.
- `pumpgrok.pumpfun.scanner`: Solana `logsSubscribe` listener that forwards decoded Pump.fun observations to the API.

## Run the API
```bash
export PUMPGROK_DB_PATH=var/pumpfun-dashboard.sqlite3
export PORT=8080
export PUMPGROK_INGEST_TOKEN='use-a-long-random-secret'
python services/pumpfun-api/server.py
```

## Run the scanner
Install the project dependencies, then configure:
```bash
export PUMPGROK_SOLANA_WS_URL='wss://your-solana-rpc-websocket'
export PUMPGROK_DASHBOARD_API='https://your-dashboard-api'
export PUMPGROK_INGEST_TOKEN='same-secret-as-api'
python -m pumpgrok.pumpfun.scanner
```

The scanner subscribes to Pump.fun program logs and writes only decoded observations. Event layouts in the current decoder are marked ASSUMED; all ingested events are therefore labelled `UNVERIFIED`. They are not eligible for price calculations, risk clearance or paper fills.

## API
- `GET /health`: service/scanner health, event count, paper-only guard.
- `GET /api/dashboard`: dashboard data and configured paper limits.
- `GET /api/events`: latest observed events.
- `GET /api/tokens`: tokens seen in observed events.
- `POST /api/ingest/event`: authenticated scanner ingestion only.

There is intentionally no live order, wallet signer, transaction submit, or trade execution endpoint. Portfolio values remain null until connected to the authoritative PumpGrok paper ledger; the dashboard must show unavailable instead of demo balances.
