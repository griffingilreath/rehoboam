# Rehoboam Runbook & Operations Guide

This guide covers operational details, configuration of advanced flows, and integration patterns for Home Assistant.

## Notification & User Mapping

### Per-User Notify Targets

Rehoboam does not maintain its own user database or notification dispatch system. Instead, it relies on **Home Assistant** to handle notifications.

**To route alerts to specific users:**

1.  **Identify the User:** The `events.json` log includes `context_user_id` (the HA user ID) when an action is triggered by a user.
2.  **Create an HA Automation:**
    *   Trigger: State change on `sensor.rehoboam_divergence_level` (if you created one) or a REST sensor polling `/recommendations`.
    *   Condition: Check the `target` or `trigger` field in the recommendation.
    *   Action: Use a `choose` block to send notifications to different devices based on the context.

### Mapping HA User IDs

The system passes Home Assistant user IDs (e.g., `39384829384...`) through to `events.json` as-is. To display friendly names in dashboards:

*   **Option A (Home Assistant):** Create a template sensor in HA that maps IDs to names, and have `collector_service` ingest that sensor via `context_entities`.
*   **Option B (Dashboard):** Maintain a simple mapping object in your dashboard's JS code:
    ```javascript
    const USERS = {
      '39384829384...': 'Griffin',
      '84938493829...': 'Guest'
    };
    ```

## Recommendations & Approvals

The `ml_service` generates recommendations (e.g., "Close blinds"), but it does **not** execute them. Execution is delegated to Home Assistant to ensure safety and authorization.

### The "Approve" Flow

1.  **Generation:** `ml_service` appends a recommendation to `divergence.json` with `status: "pending"`.
2.  **Ingestion:** Home Assistant reads this via a REST sensor:
    ```yaml
    sensor:
      - platform: rest
        name: Rehoboam Recommendations
        resource: http://<jetson-ip>:8000/recommendations
        value_template: "{{ value_json.recommendations | length }}"
        json_attributes:
          - recommendations
    ```
3.  **Approval (The "Switch"):**
    *   Create an `input_boolean.approve_rehoboam_actions` in HA.
    *   Or create actionable notifications in HA (Android/iOS) where the "Approve" button triggers the script.
4.  **Execution:**
    *   An HA automation watches the sensor.
    *   If `recommendations` is not empty AND `input_boolean.approve_rehoboam_actions` is ON (or specific logic applies):
        *   It extracts the action (e.g., `close_blinds`).
        *   It calls the corresponding HA script/service.
        *   It (Optionally) writes back to an `input_text.rehoboam_last_action` to log the result.

### Direct Execution (Jetson)

If you prefer the Jetson to execute actions directly (bypassing HA's logic engine), you would need to extend `ml_service` to send POST requests to HA's API. This is currently **not implemented** to adhere to the "read-only analysis" design principle, keeping the "actuator" logic centralized in Home Assistant.

## Data Schemas

### `events.json`

The `data/events.json` file contains a rolling log of normalized Home Assistant events.

*   **Schema:** `docs/schemas/events.schema.json`
*   **Version:** 1.0
*   **Key Fields:**
    *   `entity_id`: Source entity (e.g., `light.living_room`)
    *   `summary`: Human-readable description (e.g., "Brightness → 50%")
    *   `actor`: ID of the user/automation that triggered it (if available)
    *   `timestamp`: ISO8601 time string
