# cognition_service

Bridges an external AI orchestrator (e.g., a Home Assistant add-on) into the Rehoboam pipeline.

It implements:

- **Option A (Decision feed only)**: polls `/api/agents`, `/api/decisions`, `/api/approvals` and writes `data/cognition.json`.
- **Option B (Intent → Recommendations)**: optionally generates structured suggestions and writes `data/ai_recommendations.json` (suggest-only; no execution).

## Outputs

- `cognition.json`: normalized agent/decision/approval snapshot for dashboards and e-ink scenes.
- `ai_recommendations.json`: structured AI suggestions suitable for HA actionable notifications and feedback learning.

## Configuration

Copy and edit:

```bash
cp jetson/cognition_service/config.example.yaml jetson/cognition_service/config.yaml
```

Key fields:
- `orchestrator.base_url`: e.g. `http://homeassistant.local:8999` (where the orchestrator UI/API is reachable)
- `suggestions.enabled`: start `false` until you’re confident

## Running

```bash
python jetson/cognition_service/main.py --config jetson/cognition_service/config.yaml
```

