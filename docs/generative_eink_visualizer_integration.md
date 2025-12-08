# Generative E-Ink Visualizer Integration Plan

This guide explains how the config-driven generative visualizer slots into the existing Rehoboam stack (Home Assistant → JSON artifacts → displays) and the concrete steps to run it across a Mac “brain” and a Raspberry Pi/Waveshare display.

## High-Level Architecture

```
Home Assistant  ─┐
Pi-hole / Sensors ├─> collector_service → data/raw_state.json
                   └─> config_sync_service → data/led_config.json
                                         │
                                         ▼
  Generative Channel Daemon (Mac Mini or Jetson)
      ├─ Loads visualizers/generative_eink configs
      ├─ Subscribes to HA events via WebSocket/MQTT REST hook
      ├─ Maintains FeatureSpace + ChannelSpace
      └─ Publishes semantic channel payloads at 1–5 Hz
                                         │
                                         ▼
  Transport (MQTT topic, HTTP POST, or shared JSON file)
                                         │
                                         ▼
  Renderer Node (Pi 4 + IT8951 panel)
      ├─ Consumes channel payloads
      ├─ Feeds VisualizerRuntime (optional smoothing)
      ├─ Renders Pillow scenes → epaper/backends (spi/usb/fake)
      └─ Performs partial/full refresh choreography
```

## Roles & Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **collector_service / state_engine** | Continue writing canonical JSON artifacts for the LED panel, dashboards, ML service, etc. No changes needed. |
| **Generative Channel Daemon** | New long-running process that wraps `VisualizerRuntime`, reads Home Assistant events (and optionally `data/events.json`) to update the feature dictionary, and emits semantic channel objects like `{house_activity: 0.72, daylight: 0.33, ...}`. |
| **Transport layer** | Lightweight publish/subscribe mechanism. Start simple by writing `data/generative_channels.json` or posting to `http://pi:8787/channels`. Graduate to MQTT topics (`rehoboam/visualizer/channels`) for decoupled deployment. |
| **Renderer node** | Raspberry Pi (or Mac during development) that receives channel payloads, calls `render_scene(...)`, and pushes frames to the e-paper panel using the existing `epaper` backends. This node is also where partial/ full refresh cadence is enforced. |

## Current Building Blocks

- `visualizers/generative_eink/` – Config, runtime, feature/channel math.
- `visualizers/generative_eink/examples/pi_weight_demo.py` – Demonstrates driving the IT8951 panel (or fake backend) with synthetic channel waveforms.
- `epaper/service/main.py` – Long-running service that can be extended with a new “generative” scene once real channel payloads are available.
- `docs/it8951_driver_playbook.md` – Hardware + driver setup for the Pi side.

## Step-by-Step Integration

1. **Finalize configs**
   - Copy `visualizers/generative_eink/config/entities.example.yaml` → `entities.yaml` and map real HA entities to features.
   - Copy `channels.example.yaml` → `channels.yaml`, then tune weights/curves.

2. **Bring up the channel daemon (Mac Mini)**
   - Create `visualizers/generative_eink/examples/channel_daemon.py` (TODO) or adapt `pi_weight_demo` to read actual HA events.
   - Connect to Home Assistant via WebSocket API (`/api/websocket`), convert `state_changed` events into `EntityStateEvent`, and feed `VisualizerRuntime.handle_event`.
   - Every 1–5 seconds, emit `runtime.get_channels()` as JSON to `~/rehoboam/data/generative_channels.json` and publish to MQTT (`rehoboam/viz/channels`).

3. **Bridge to the renderer (Pi 4 + IT8951)**
   - Option A: Share the JSON file over SMB/NFS and run a watcher that reloads when the timestamp changes.
   - Option B: Run a tiny FastAPI receiver on the Pi that accepts POSTed channel payloads, caches them in memory, and notifies the renderer loop.
   - Option C: Subscribe to the MQTT topic (preferred longer term) and update an in-memory dict per message.

4. **Render loop integration**
   - Start from `pi_weight_demo.py` and replace the synthetic `FEATURE_DRIVERS` with the real channel input (step 3).
   - Extract `render_scene` into a reusable module (future work) that the `epaper` service can call as a “scene.”
   - Use the `DisplayManager` helper (or backend directly) to orchestrate partial vs full refreshes (e.g., GC16 at sunrise/sunset, partial updates every minute for overlay glyphs).

5. **Systemd and automation**
   - Add a `rehoboam-visualizer.service` on the Pi that runs the renderer loop with `--backend spi`.
   - Ensure the service honors the `--shutdown` behavior (full refresh + sleep) on stop, just like `rehoboam-epaper.service`.
   - Optionally create a `rehoboam-visualizer-channel.service` on the Mac to keep the HA→channel daemon alive with proper logging.

6. **Fallbacks & interop**
   - If the channel feed stalls, the renderer can fade to the legacy `epaper` scenes or display a calm standby composition (e.g., `resource_use` frozen value).
   - Provide a CLI flag to run the renderer in “standalone” mode (synthetic drivers) for onsite debugging.

## Integration Touchpoints

| Area | Action |
|------|--------|
| **Docs** | `docs/generative_eink_visualizer_research.md` (vision) → this integration doc (wiring). Link both from the repo README so new contributors understand the plan. |
| **Code** | Add a `generative_scene.py` under `epaper/scenes/` that reads channel payloads from disk or MQTT and renders via `render_scene`. (Future work.) |
| **Testing** | Reuse `pi_weight_demo.py --backend fake` in CI to generate PNG fixtures once the scene stabilizes. |
| **Operations** | Update `rehoboam-epaper.service` or add a sibling unit to ensure IT8951 shutdown occurs even if the generative renderer crashes. |

## Data & Message Contracts

### Channel payload (JSON)

```json
{
  "timestamp": "2025-12-08T18:14:30Z",
  "house_activity": 0.64,
  "soundscape": 0.28,
  "daylight": 0.91,
  "comfort": 0.42,
  "resource_use": 0.33,
  "network_health": 0.51,
  "security_tension": 0.12,
  "long_term_drift": 0.77
}
```

- Transport-agnostic: file, HTTP, MQTT.
- Include a `schema_version` when the format stabilizes.
- Renderer treats missing keys as `0.0`.

### Renderer heartbeat (optional)

- Publish `/data/generative_channels.last_seen` timestamp or write `data/generative_renderer.json` so other services can confirm the panel is alive.

## Future Enhancements

- **Bidirectional control:** Let the renderer request scene changes or ask for a channel freeze if the Pi is under heavy load.
- **Partial-Refresh Planner:** Move the “which rectangles to update” logic into a shared module so both `pi_weight_demo` and the eventual `epaper` scene reuse it.
- **Channel history caching:** Store a small circular buffer (e.g., last 512 frames) on disk so you can replay channel evolution when fine-tuning visuals.
- **Health/ops integration:** Extend `service_health.json` to include the channel daemon + renderer so dashboards reflect their status alongside the other services.

By following this plan, the generative visualizer remains loosely coupled—HA events feed the channel daemon, the daemon publishes semantic values, and any renderer (Pi + Waveshare, macOS simulator, future OLED panel) can subscribe without rewriting core logic.
