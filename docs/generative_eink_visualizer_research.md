# Generative E-Ink Visualizer Research

This document distills the newly added research artifacts and strategy notes for the next-generation generative e-ink experience. It captures the shared understanding across the four technical plan PDFs and *Design Strategy for a Generative E‑Ink Visualization Engine* so future contributors can build on them without rereading each source.

## Source Materials

- `Technical Plan_ Data-Driven Generative Visual System (4-Bit Grayscale).pdf`
- `Technical Plan_ Data‑Driven Generative Visualizer (4‑Bit Grayscale).pdf`
- `Technical Plan_ Designing the Generative System Logic (4-Bit Grayscale).pdf`
- `Technical Plan_ Data-Driven Generative Visualizer (4-Bit Grayscale).pdf` (non-breaking hyphen variant)
- `Design Strategy for a Generative E‑Ink Visualization Engine.pdf`

## Core Principles

- **Home Assistant is the data spine:** Every physical device funnels into HA, giving us one authenticated API for Ecobees, HomePods, eero, window coverings, Hue/Aqara sensors, Flume water data, clean-energy feeds, etc.
- **Two-stage interpretation:** Raw HA entities become normalized features, which then feed a compact set of semantic channels that paintings respond to. This keeps the art tunable and extensible.
- **Slow, meaningful change on e-ink:** Lean into the 16-level grayscale palette, partial refresh tactics, and ritual full refreshes instead of constant animation.
- **Configuration over code:** New sensors or channels should be added through YAML/JSON config rather than Python edits wherever possible.

## Stage 1: Raw Entities → Feature Space

1. **Entity catalog lives in config** with an `id` (matching HA entity_id) and one or more feature definitions.
2. **Feature types** include numeric, binary, event-rate, state-enum, attribute extraction, and derived aggregations (e.g., 15 min rolling averages).
3. **Normalization and smoothing** happen here so downstream consumers always see 0–1 (or -1–1) values, regardless of the underlying sensor.
4. **Temporal context** is baked in: windows for recent motion, duration-until-closed for garage doors, daily totals for utilities, etc.

### Feature-Engineering Playbook

- **Event-rate windows:** Maintain per-feature deques keyed by entity to convert bursts of motion or door events into activity densities. Window length + `max_events` define the heat of a channel.
- **EWMA smoothing:** Apply exponential moving averages (τ configurable per feature) to avoid flicker on the partial-refresh display while still responding to state changes.
- **Multi-entity aggregation:** Use metadata tags (`area`, `device_class`) to auto-sum groups (e.g., `lights_on_ratio` derived from all `light.*` in a zone).
- **Derived ratios:** Normalize “how long unlocked” or “clean energy opportunity” as ratios of current duration vs. expected maximums.
- **Time-of-day envelopes:** Compose raw features with deterministic curves (sine/day-night clocks) before semantic mapping to better express circadian behaviors.

## Stage 2: Feature Space → Semantic Channels

Target 8–12 channels that summarize the house’s subconscious:

- **House Activity:** motion, doors, lights, active media.
- **Quiet / Soundscape:** presence, loudness, and content type of HomePods/TVs.
- **Daylight / Openness:** outdoor lux, blind openness, circadian expectations.
- **Comfort / Climate:** deviation from desired temp/humidity plus HVAC activity.
- **Resource Use:** water, energy, clean-energy availability, solar production (future).
- **Network Health:** eero load, latency, number of connected devices.
- **Security / Perimeter:** locks, garage door, leaks, unexpected motion when away.
- **Long-Term Drift:** slowly evolving seasonal or weekly aggregates for baseline shifts.

Channels are defined as weighted formulas over features and can include polarity (negative weights), clamps, and curve transforms to tune responsiveness.

### Channel Behavior Matrix

| Channel            | Primary features                                             | Example behaviors                                                                 |
|--------------------|--------------------------------------------------------------|------------------------------------------------------------------------------------|
| `house_activity`   | Motion rates, light counts, media state                      | Drives density of mid-layer patterns; spikes trigger partial refresh ripples.      |
| `soundscape`       | HomePod loudness, content type (music vs. voice)             | Controls wave amplitude / texture softness, muting when white noise is detected.   |
| `daylight`         | Outdoor lux, blind openness, circadian envelope              | Sets base tonal value of the canvas and contrast budget.                           |
| `comfort`          | Temp/humidity deviation, HVAC run state                      | Modulates sharpness vs. dithering to “breathe” when HVAC fights the environment.   |
| `resource_use`     | Power (future), water flow, clean-energy score               | Adds vertical streaks during spikes; negative weights calm the scene when green.   |
| `network_health`   | eero load, latency (inverse), devices online ratio           | Horizontal banding intensity + occasional “glitch” glyph when latency surges.      |
| `security_tension` | Lock state, garage door, leak sensors, unexpected motion     | Triggers localized icons (drips, open brackets) and can darken the composition.    |
| `long_term_drift`  | Rolling daylight/resource trends, weekly aggregates          | Slowly rotates the base noise field and seeds seasonal motifs.                     |

## Stage 3: Channels → Visual Language

- **Background field:** Driven by `long_term_drift` and `daylight`, realized as slowly changing gradients or noise fields quantized to 16 grayscale steps.
- **Mid-layer structure:** Grids, lines, or stippling governed by `house_activity`, `soundscape`, and `comfort`, enabling visible density/clarity changes.
- **Overlay glyphs:** `resource_use` and `network_health` create pulses, streaks, or bands, with obvious motifs for spikes or degradation.
- **Event cues:** Rare triggers (leak, garage open, clean energy window) yield recognizable, localized animations or glyph swaps using partial refresh.

### Visual Grammar Guidelines

- **Regional ownership:** Partition the canvas so each semantic channel owns a zone or layer, minimizing conflicting refresh needs.
- **Partial refresh choreography:** Queue updates per zone (e.g., top band for network, bottom band for security) to avoid whole-screen flicker.
- **Episodic rituals:** Tie full refreshes to macro events—sunrise, sunset, day rollover—so the display “breathes” on a predictable cadence.
- **Gesture vocabulary:** Keep a catalog of glyphs (water columns, lattice openings, hatch breaks) with documented triggers so new contributors extend consistently.

## Stage 4: Extensible Implementation Pattern

1. **Entity config (`entities.yaml`)** – every sensor, its feature definitions, normalization, and smoothing directives.
2. **Channel config (`channels.yaml`)** – references feature IDs with weights and optional transforms.
3. **Feature registry** – Python module that loads configs, subscribes to HA, and maintains the normalized feature dictionary.
4. **Channel mapper** – consumes the feature dictionary, produces semantic channel values, and notifies renderers.
5. **Visual modules** – receive only the semantic channel payload, so upgrades focus on composition, not plumbing.

## Deployment Notes

- **Development loop:** Run on macOS with an e-ink simulator window (quantized 16-level palette, optional ghosting emulation) to iterate quickly.
- **Field deployment:** Raspberry Pi or similar can drive the physical Waveshare display. It either runs the whole stack or pulls rendered frames from the Mac mini over the network.
- **Refresh strategy:** Partial updates for local motion, occasional whole-screen “breaths” tied to circadian events (sunrise/sunset) to mitigate ghosting.

## System Architecture Snapshot

1. **Ingestion tier:** Home Assistant WebSocket listener (or MQTT bridge) streams `state_changed` events, enriched with metadata and routed into the feature space.
2. **Feature registry:** Stateful service that maintains normalized values, historical windows, and exposes both pull (`/features`) and push (pub/sub) interfaces.
3. **Channel synthesizer:** Deterministic evaluator that emits channel payloads at configurable cadence (e.g., 1–5 Hz) plus “event” packets for rare triggers.
4. **Render dispatcher:** Feeds both a macOS simulator (for design iteration) and the Waveshare driver (Pi or microcontroller) via the same channel payload contract.
5. **Frame store (optional):** Circular buffer of the last N frames/channel states used for debugging, playback, or ML-assisted motif generation.

## Implementation Milestones

1. **Data spine hardening**
   - Stand up the HA listener with reconnect logic, entity allowlists, and heartbeat metrics.
   - Record live traffic to NDJSON for offline replay and regression tests.
2. **Feature & channel sandbox**
   - Build CLI tooling that replays recorded HA streams through `FeatureSpace`/`ChannelSpace`, emits CSV traces, and plots distributions.
   - Validate normalization ranges per feature to avoid saturation.
3. **Simulator-first rendering**
   - Implement a Pillow/Qt-based 16-level renderer that consumes channel payloads and visualizes the proposed grammar.
   - Instrument per-channel refresh counters to confirm the choreography assumptions.
4. **Waveshare deployment track**
   - Decide on push (send bitmaps) vs. pull (remote render) architecture.
   - Prototype partial refresh scheduling on physical hardware, benchmark ghosting vs. cadence.
5. **Event storytelling**
   - Author a library of “event cards” (JSON) describing trigger → glyph mapping, duration, and decay curves.
   - Add alert logging to correlate HA anomalies with what the display showed.
6. **Stability + ops**
   - Add watchdog timers, config hot-reload, and snapshotting of feature/channel state so the visualizer can survive reboots without dramatic jumps.

## Open Questions

- Preferred message bus between Home Assistant and the feature registry (WebSocket, MQTT, HA REST events?).
- Storage strategy for long-term aggregates (lightweight TSDB vs. rolling JSON state?).
- Testing methodology for channel formulas (golden CSV fixtures vs. synthetic HA event streams?).
- Deployment boundary between the Mac brain and the Pi/Waveshare driver.
- How to best encode seasonal motifs (hand-tuned scripts vs. learned embeddings) without breaking the deterministic channel response?
- Can partial-refresh budgets be dynamically allocated based on battery/thermal constraints if the display later moves off mains power?

Documenting these unresolved points up front keeps the research actionable while clarifying the assumptions embedded in the technical plan PDFs.
