# notification_service

Dispatches Home Assistant **actionable notifications** for AI recommendations and records what was sent.

This service reads `data/ai_recommendations.json` and sends a notification per recommendation (per user) using `notify.*` services.

## Outputs

- `notifications_sent.json`: ledger mapping recommendation ids → notification tags/targets + last_sent timestamps (for dedupe).

## Configuration

```bash
cp jetson/notification_service/config.example.yaml jetson/notification_service/config.yaml
```

You must configure `notify_targets` to match your HA Companion App notify services.

## Running

```bash
python jetson/notification_service/main.py --config jetson/notification_service/config.yaml
```

