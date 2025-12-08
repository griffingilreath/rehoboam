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

## Historical Context & Influence Map

### Data-Driven Generative Systems (1950s–Present)

- **Plotter pioneers (1950s–1970s):** Ben Laposky’s oscilloscope compositions, Frieder Nake’s algorithmic drawings, and Vera Molnár’s “machine imaginaire” established parametric systems where tweaking numerical inputs yielded radically different aesthetics. Their emphasis on parameter catalogs foreshadows our channel weights.
- **Algorist manifesto (1968 onward):** Jean-Pierre Hébert and Roman Verostko advocated for transparent, reproducible rulesets—mirrored in our choice to keep entity/channel configs declarative and versionable.
- **Software art era (1990s–2000s):** John Maeda’s Design by Numbers and Casey Reas/Ben Fry’s Processing culture normalized separation between *data engines* and *render scripts*, reinforcing today’s runtime abstraction.
- **ML-infused generativity (2010s+):** Projects like Refik Anadol’s data sculptures show the power of long-term trend encoding and multi-channel fusion; we borrow the idea of slow “data weather” rather than literal dashboards.

### Calm Technology & Ambient Displays

- **Weiser & Brown (1995):** “Calm technology” defined devices that inform without overwhelming. Their guidelines (peripheral awareness, center-of-attention transitions) justify the emphasis on semantic channels that modulate layers gradually.
- **Tangible Bits (1997, Hiroshi Ishii):** Highlighted mapping abstract data to physical metaphors, which inspires the glyph vocabulary and zoned canvas approach.
- **Ambient Devices (early 2000s):** The Ambient Orb and Nabaztag rabbit proved people embrace diffuse signals (color shifts, ear movements) over raw numbers. Our visualizer inherits that by avoiding per-entity readouts.
- **Google’s “Little Signals” (2022 concept):** Explored multiple modalities (movement, air, light) instead of screens. We adapt the principle by dedicating unique textures/glyphs per channel to avoid cognitive overload.

### Smart Home & Data Spine Evolution

- **X10/Insteon era (1970s–2000s):** Limited bandwidth, poor reliability—why early visualizations stayed simplistic.
- **HomeKit / SmartThings (2014+):** Vendor silos forced per-device integrations; we avoid this historical fragmentation by anchoring on Home Assistant’s unified entity model (open-source convergence circa 2017–2020).
- **Modern HA (2020+):** Event bus, MQTT bridges, and robust history APIs finally make multi-modal feature synthesis feasible at home scale. The visualizer leverages this maturity to compute aggregates like `motion_house_last_hour` without duct tape.

### E-Paper & Grayscale Display Lineage

- **Gyricon (1970s Xerox PARC):** Introduced bistable beads requiring low refresh—established the idea that content should hold meaning even when static.
- **E Ink Corp & Kindle (2007):** Mainstreamed 16-level grayscale and partial refresh, but also highlighted ghosting artifacts; informs our decision to choreograph regional updates and occasional “clearing” rituals.
- **DIY Waveshare community (2015+):** Open-source drivers, partial refresh tricks, and LUT hacking show the hardware tolerances (max ~1–2 Hz region updates) that constrain our animation cadence.
- **Contemporary art deployments:** Projects like Martin Lorenz’s “Executive Coloring Device” or e-ink storefronts demonstrate layering textures and dithers instead of solid fills—a technique we adopt for `mid-layer structure`.

### Contributor Gallery

| Name | Domain | Notable Work | Influence on This Visualizer |
|------|--------|--------------|-------------------------------|
| **Ben Laposky** (1914–2000) | Analog generative art | *Oscillons* (1950s) using oscilloscopes to draw parametric curves. | Validates using mathematical feature spaces to produce fluid, organic backgrounds. |
| **Vera Molnár** (1924–2023) | Algorithmic art | Early plotter drawings like *Interruptions* (1968). | Inspires the documented “parameter catalogs” and deliberate rule-based compositions. |
| **Frieder Nake** & **Georg Nees** | Computer graphics | First exhibited computer art (1965, Stuttgart). | Reinforces the need for deterministic, code-driven line work for mid-layer structures. |
| **Harold Cohen** | AI art | *AARON* autonomous drawing system (1970s–2000s). | Shows long-running systems benefit from transparent semantic vocabularies. |
| **John Whitney** | Motion graphics | Mechanical + computer animations (*Catalog*, 1961). | Encourages treating channel modulation as musical orchestration. |
| **Casey Reas & Ben Fry** | Processing founders | Open-sourced Processing (2001). | Cemented the split between data engines and rendering sketches mirrored in our runtime. |
| **John Maeda** | Design computation | *Design by Numbers*, MIT Media Lab. | Advocates for simple, declarative creative code—mirrors our YAML-first approach. |
| **Hiroshi Ishii** | Tangible Bits | MIT Tangible Media Lab (1990s+). | Informs the mapping of abstract data to tactile metaphors (glyph lexicon). |
| **Mark Weiser & John Seely Brown** | Calm technology | Xerox PARC research (1995). | Directly drives the peripheral awareness goals and ritual refresh cadence. |
| **Amber Case** | Calm tech advocacy | *Calm Technology* (2015). | Reminds us to make failure states and alerts gentle yet legible. |
| **Nicholas Negroponte** | Ambient communication | *The Architecture Machine* (1970). | Encourages adaptive, environment-aware behavior like `long_term_drift`. |
| **Mary Lou Jepsen** & **Joseph Jacobson** | E Ink pioneers | Co-founded E Ink Corporation (1997). | Provide the hardware constraints (grayscale LUTs, partial refresh) the runtime respects. |
| **Janne Kyttanen / Ambient Devices team** | Ambient consumer products | Ambient Orb (2002). | Proves appetite for single-value ambient cues, leading to semantic channel distillation. |
| **Refik Anadol** | Data sculpture | *WDCH Dreams*, *Machine Hallucinations*. | Demonstrates emotional resonance of aggregated data “weather,” inspiring layered drift. |
| **Martin Lorenz** | E-ink installations | *Executive Coloring Device* (2018). | Validates dithering, layering, and slow-evolving compositions on e-paper mediums. |
| **Jeanne Dietrich & Waveshare OSS authors** | Hardware engineering | Reverse-engineered partial refresh LUTs. | Their documentation informs update cadence and ghosting mitigation tactics we adopt. |

### Lessons Extracted

1. **Parameter catalogs > ad-hoc tweaks:** Early generative artists documented every variable; hence our YAML configs with explicit normalization ranges and channel weights.
2. **Peripheral calm requires predictable rituals:** Calm tech history shows people trust devices with recurring behaviors, motivating sunrise/sunset full refresh cycles.
3. **Unified abstractions beat one-off integrations:** Smart-home history warns against siloed pipelines, so the runtime ingests *only* HA entities to stay future-proof.
4. **Bistable media needs slow storytelling:** E-ink lineage underlines ghosting and latency, so we treat the composition as evolving tableaux, not a live video feed.

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

## History-Informed Direction

| Historical thread                           | Takeaway for today                                            | Concrete action in this project                                              |
|---------------------------------------------|----------------------------------------------------------------|-------------------------------------------------------------------------------|
| Generative pioneers’ parameter catalogs      | Transparency + repeatability make systems extensible          | Keep all feature/channel formulas in tracked YAML with comments + ranges.    |
| Calm technology rituals                      | Peripheral experiences need predictable tempo                  | Schedule daily full refresh “breaths” and rate-limit partial updates per zone |
| Ambient displays favor metaphors over data   | Viewers grasp stories faster than raw metrics                 | Design glyph lexicon (drip, lattice, hatch) tied to semantic channels         |
| Smart home platform fragmentation            | Minimal glue code between vendors reduces maintenance         | Use HA entity metadata exclusively; no direct device SDK calls               |
| E-ink ghosting constraints                   | Content must survive static intervals                         | Ensure each layer reads as intentional print even if updates pause minutes   |
| DIY Waveshare experimentation                | Region-based drivers tolerate ~1–2 Hz per zone                | Partition the canvas and throttle updates per semantic owner                 |
| ML-era generative art emphasizing trends     | Long-term aggregates add emotional depth                      | Maintain `long_term_drift` + seasonal motifs sourced from historical data     |
| Tangible Bits’ mapping research              | Physical context grounds abstract systems                     | Annotate configs with `area` metadata and reuse it for spatialized visuals    |

## Open Questions

- Preferred message bus between Home Assistant and the feature registry (WebSocket, MQTT, HA REST events?).
- Storage strategy for long-term aggregates (lightweight TSDB vs. rolling JSON state?).
- Testing methodology for channel formulas (golden CSV fixtures vs. synthetic HA event streams?).
- Deployment boundary between the Mac brain and the Pi/Waveshare driver.
- How to best encode seasonal motifs (hand-tuned scripts vs. learned embeddings) without breaking the deterministic channel response?
- Can partial-refresh budgets be dynamically allocated based on battery/thermal constraints if the display later moves off mains power?

Documenting these unresolved points up front keeps the research actionable while clarifying the assumptions embedded in the technical plan PDFs.
