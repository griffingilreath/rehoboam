# Home Assistant Rack Configuration

This repo assumes Home Assistant (HA) is the human-friendly source of truth for what each LED port represents. `config_sync_service` reads HA helper entities, writes `data/led_config.json`, and the rest of the pipeline follows.

## Helpers

Define the following HA helpers (Settings → Devices & Services → Helpers):

```yaml
# configuration.yaml (or helpers.yaml if you split config)
input_text:
  led0_name:
    name: LED 0 Name
  led0_ip:
    name: LED 0 IP
  led0_ha_availability_entity:
    name: LED 0 HA Availability Entity
  led0_event_entities:
    name: LED 0 Event Entities
  # ... repeat for led1_* through led15_*

input_select:
  led0_type:
    name: LED 0 Type
    options:
      - bridge
      - server
      - pihole
      - switch
      - ap
      - other
  # ... repeat for each index
```

Helpful naming pattern: `R1` through `R8` for indices 0–7 (Rack top) and `S1` through `S8` for indices 8–15 (Shelf/bottom). Example mapping:

| Index | Label | Example values |
|-------|-------|----------------|
| 0 | R1 - Ethernet In | `name="Ethernet In"`, `type="uplink"`, leave IP blank (WAN info comes from context) |
| 1 | R2 - Jetson Nano / Teensy | `name="Rehoboam"`, `type="server"`, `ip="192.168.1.50"` |
| 2 | R3 - Pi-hole | `name="Pi-hole"`, `type="pihole"`, `ip="192.168.1.51"`, optional `event_entities="sensor.pihole_dns_queries_total"` |
| 3 | R4 - Pi-drive / NAS | `name="Pi-Drive"`, `type="nas"`, `ip="192.168.1.60"` |
| 4 | R5 - Mac mini | `name="Mac mini"`, `type="server"`, `ip="192.168.1.40"` |
| 5 | R6 - AirPort Express | `name="Airport Express"`, `type="bridge"`, `ip="192.168.1.20"` |
| 6 | R7 - Eero | `name="Eero"`, `type="router"`, `ip="192.168.1.2"` |
| 7 | R8 - Switch↔Switch uplink | `name="Switch link"`, `type="uplink"` |
| 8 | S1 - Hue | `name="Hue"`, `type="bridge"`, `ha_availability="binary_sensor.hue_bridge_available"` |
| 9 | S2 - Lutron | `name="Lutron"`, `type="bridge"`, `ha_availability="binary_sensor.lutron_bridge_available"` |
| 10 | S3 - Ikea | `name="Ikea"`, `type="bridge"`, `ip="192.168.1.90"` |
| 11 | S4 - Aqara | `name="Aqara"`, `type="bridge"`, `ip="192.168.1.91"` |
| 12 | S5 - Starling | `name="Starling"`, `type="bridge"`, `ip="192.168.1.92"` |
| 13 | S6 - Home Assistant | `name="Home Assistant"`, `type="server"`, `ha_availability="binary_sensor.homeassistant"` |
| 14 | S7 - Eufy | `name="Eufy"`, `type="bridge"`, `ip="192.168.1.93"` |
| 15 | S8 - Switch link | `name="Switch↔Switch"`, `type="uplink"` |

Feel free to swap these labels; the key is to keep the `R` row reserved for rack/network gear and the `S` row for smart-home bridges so the physical LED panel matches the Lovelace layout.

## Lovelace Dashboard

Create a dashboard (e.g., "Rack Config") with a grid card showing all helpers. Example snippet:

```yaml
title: Rack Config
views:
  - title: Ports
    path: rack-config
    cards:
      - type: grid
        columns: 4
        square: false
        cards:
          - type: entities
            title: R1 (LED 0)
            entities:
              - input_text.led0_name
              - input_text.led0_ip
              - input_select.led0_type
              - input_text.led0_ha_availability_entity
              - input_text.led0_event_entities
          # repeat for LED 1..15
```

You can organize the cards into two rows to mirror the physical layout (R row, S row). For faster updates, consider using the "companion" card or a simple table card (like "Mushroom" or "Fold-entity-row") to reduce scrolling.

### Bidirectional view

Add `rest` sensors that read the FastAPI endpoints so the dashboard shows live status next to the helpers:

```yaml
sensor:
  - platform: rest
    name: Rehoboam canonical state
    resource: http://rehoboam.local:8000/status
    value_template: "{{ value_json.summary.health }}"
    json_attributes_path: "$.leds"
    json_attributes:
      - leds
```

Add a second `rest` sensor for `/recommendations` if you want Lovelace chips/cards that list active suggestions:

```yaml
sensor:
  - platform: rest
    name: Rehoboam recommendations
    resource: http://rehoboam.local:8000/recommendations
    value_template: "{{ value_json.recommendations | length }}"
    json_attributes:
      - recommendations
```

Use entity-filter cards to highlight LEDs whose `health != "OK"` and a `conditional-card` to surface the recommendation list whenever the count is greater than zero. This keeps the HA UI, LEDs, and iPhone/e-ink dashboards in agreement.

## Optional Automations

- **Default event entities:** for bridges like Hue, set `input_text.led8_event_entities` via automation to a comma-separated list of relevant HA entities.
- **Validation:** trigger a notification if a required field is blank (e.g., Pi-hole type with no IP) so the panel isn’t configured with incomplete data.
- **Friendly scripts:** create scripts `script.r1_update`, `script.r2_update`, etc., that set the helpers based on a dropdown so you don’t type IPs manually.
- **Port presets:** pair an `input_select` with automations to prefill helpers for common roles (e.g., “R5 = Mac mini” vs “R5 = Airport Express”). `config_sync_service` will propagate those changes automatically.

Example validation automation:

```yaml
automation:
  - alias: LED config missing IP
    trigger:
      - platform: state
        entity_id: input_select.led2_type
    condition:
      - condition: state
        entity_id: input_select.led2_type
        state: pihole
      - condition: template
        value_template: >-
          {{ states('input_text.led2_ip') in ['', none] }}
    action:
      - service: persistent_notification.create
        data:
          title: "Pi-hole LED needs IP"
          message: "Set input_text.led2_ip so the collector can ping the device."
```

## Sync Expectations

- `config_sync_service` polls HA every `poll_interval_seconds` (default 30–60 seconds). Edits in the dashboard update `led_config.json` automatically on the next poll.
- No code changes or redeploys are needed to remap LEDs—just edit the helpers.

## Feeding HA from the Panel (optional)

If you want HA to display what the panel is showing (e.g., health codes), you can expose `data/canonical_state.json` via the API service and create HA `rest` sensors that read `/status` and `/divergence`. This gives you HA automations like "if Hue LED health == ERROR, flash a Lovelace badge".

## References

- Home Assistant helpers: https://www.home-assistant.io/integrations/input_text/
- Example Rack Config UI from the README (see columns R/S in the "How the pieces fit" section).
