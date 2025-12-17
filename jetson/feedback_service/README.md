# feedback_service

Extracts **approve / decline / snooze** feedback from Home Assistant events and persists them as a clean learning signal.

This service expects `collector_service` to be recording `mobile_app_notification_action` events into `data/events.json`.

## Outputs

- `feedback.json`: normalized feedback events, suitable for ML and recommendation tuning.
- `ai_recommendations.json`: (optional) recommendation statuses updated from `pending` → `approved/declined/snoozed`.

## Running

```bash
cp jetson/feedback_service/config.example.yaml jetson/feedback_service/config.yaml
python jetson/feedback_service/main.py --config jetson/feedback_service/config.yaml
```

