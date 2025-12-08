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

## Stage 3: Channels → Visual Language

- **Background field:** Driven by `long_term_drift` and `daylight`, realized as slowly changing gradients or noise fields quantized to 16 grayscale steps.
- **Mid-layer structure:** Grids, lines, or stippling governed by `house_activity`, `soundscape`, and `comfort`, enabling visible density/clarity changes.
- **Overlay glyphs:** `resource_use` and `network_health` create pulses, streaks, or bands, with obvious motifs for spikes or degradation.
- **Event cues:** Rare triggers (leak, garage open, clean energy window) yield recognizable, localized animations or glyph swaps using partial refresh.

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

## Open Questions

- Preferred message bus between Home Assistant and the feature registry (WebSocket, MQTT, HA REST events?).
- Storage strategy for long-term aggregates (lightweight TSDB vs. rolling JSON state?).
- Testing methodology for channel formulas (golden CSV fixtures vs. synthetic HA event streams?).
- Deployment boundary between the Mac brain and the Pi/Waveshare driver.

Documenting these unresolved points up front keeps the research actionable while clarifying the assumptions embedded in the technical plan PDFs.
