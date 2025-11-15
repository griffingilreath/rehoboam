# api_service

FastAPI application that serves the Jetson’s canonical LED state, configuration, history, and service health so dashboards and tools can stay in sync without reading files directly.

## Responsibilities

- Read `canonical_state.json`, `led_config.json`, and optional history/health files from the shared data directory.
- Expose REST endpoints used by the iPhone dashboard, E-ink renderer, and debugging tools.
- Provide lightweight caching so repeated requests don’t thrash the filesystem.
- Support CORS for front-ends hosted on different origins.

## Prerequisites

- Python 3.9+ and `pip install -r jetson/requirements.txt` (brings in FastAPI + Uvicorn).
- Upstream services writing `led_config.json`, `canonical_state.json`, and optionally `history.json`, `service_health.json`.
- Open TCP port on the Jetson (default 8000) reachable by clients.

## Configuration

1. Copy the sample file:
   ```bash
   cp jetson/api_service/config.example.yaml jetson/api_service/config.yaml
   ```
2. Key fields:
   - `data_dir`: base path for all shared JSON artifacts.
   - `led_config_filename`, `canonical_state_filename`, `history_filename`, `health_filename`: override if you store multiple versions.
   - `host` / `port`: listening socket (use `0.0.0.0` to allow LAN access).
   - `reload`: enable FastAPI auto-reload in development (don’t use in production supervisors).
   - `cors_origins`: list of allowed origins (e.g., iPhone dashboard URL).
   - `cache_ttl_seconds`: TTL for the on-disk JSON cache; `0.5s` keeps latency low while avoiding constant disk reads.
   - `logging.level`: default log verbosity.

## Running

```bash
python jetson/api_service/main.py \
  --config jetson/api_service/config.yaml
```

- Use `--reload` for hot reloading (dev only).
- Override host/port temporarily with `--host 127.0.0.1 --port 9000`.
- For systemd, point `ExecStart` at the command above and set `WorkingDirectory` to the repo root.

## Endpoints

| Path | Description | Notes |
| --- | --- | --- |
| `GET /status` | Returns `canonical_state.json` | 503 if not available yet |
| `GET /config` | Returns `led_config.json` | Useful for dashboards to label LEDs |
| `GET /history` | Returns `history.json` (optional) | Defaults to `{ "entries": [] }` |
| `GET /health` | Aggregated service health data | Source file optional |
| `GET /divergence` | Returns `divergence.json` | 404 until ML service runs |
| `GET /info` | Metadata about file locations | Helpful for debugging |

Future endpoints (WebSocket, divergence) can be layered on top without changing the data model.

## Operational Notes

- The JSON cache validates both TTL and file mtime, so updates propagate immediately when files change.
- If the history or health files aren’t present, the API gracefully returns empty payloads rather than errors.
- CORS is disabled by default; specify origins once the dashboard hostnames are known.
- For HTTPS termination, place Nginx/Caddy/Traefik in front of the service or run FastAPI behind a reverse proxy.
- `/health` simply reflects the contents of `service_health.json`, which every Jetson agent now updates, so pointing the API at the shared data directory is all that’s required for live status. Likewise `/divergence` is a thin wrapper over `divergence.json`; connect the ML service to populate it.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| 503 on `/status` | `state_engine_service` not writing `canonical_state.json` | Check upstream logs, ensure data dir path matches |
| API starts but dashboards blocked by CORS | `cors_origins` empty | Add allowed origins to config |
| `Invalid JSON` logs | Upstream file being written while read | Files are atomic by design; ensure services use tmp+rename (already implemented) |
| Port already in use | Another process bound to same port | Change config port or stop other service |

## Extending

- Add WebSocket endpoint to push canonical updates (`fastapi.websockets`).
- Stream history from SQLite or another datastore once logging lands.
- Bundle OpenAPI docs (already available at `/docs`) into your dashboard for better self-service debugging.

## Next Step

With the API online, the front display clients (iPhone dashboard and E-ink renderer) can start hitting `/status`, `/config`, and `/history`. Remaining future work includes the ML/anomaly service and richer visualization clients.
