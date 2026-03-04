# Home Assistant Configuration

This directory contains the Home Assistant configuration for the Rehoboam Rack house.

> **Note:** This will eventually live in its own private git repo. For now it's co-located here.

---

## Quick Setup

1. **Copy secrets:** `cp secrets.yaml.example secrets.yaml` and fill in all values
2. **Install Flume integration:** Add via HA → Settings → Integrations → Flume
3. **Set up Flume sync script:** See _Water_ section below
4. **Copy packages to HA:** If using HA OS, place this directory contents at `/config/`

---

## Directory Layout

```
home_assistant_config/
├── configuration.yaml          # Main config (includes packages/)
├── secrets.yaml.example        # Template — copy to secrets.yaml
├── automations.yaml            # HA-managed automations
├── scripts.yaml                # HA-managed scripts
├── scenes.yaml                 # HA-managed scenes
├── packages/
│   ├── municipal/
│   │   ├── README.md           # ⚠️ API maintenance guide (read this!)
│   │   ├── snow_plows.yaml     # Snow plow detection & history
│   │   ├── trash_recycling.yaml # Garbage & recycling pickup schedule
│   │   └── leaf_collection.yaml # Leaf collection season & route status
│   ├── utilities/
│   │   ├── water.yaml          # Flume water monitoring + lifetime stats
│   │   └── energy.yaml         # Electricity tracking + lifetime costs
│   ├── rehoboam/
│   │   └── rack_config.yaml    # LED helpers (synced with Rehoboam rack)
│   └── zones/
│       ├── exterior.yaml
│       ├── floor_1.yaml
│       ├── floor_2.yaml
│       └── basement.yaml
└── scripts/
    └── flume_sync.py           # Daily Flume portal category sync
```

---

## Municipal Services

See [`packages/municipal/README.md`](packages/municipal/README.md) for API maintenance details.

Key things to know:
- **Snow plows** — works automatically, stable ArcGIS endpoint
- **Trash/recycling** — requires `milwaukee_garbage_url` in secrets.yaml
- **Leaf collection** ⚠️ — **requires annual URL update each September**

---

## Water (Flume)

### How it works

Two-part system:
1. **Real-time flow** — via the native HA Flume integration (`sensor.flume_sensor_*`)
2. **Daily categories** — via `scripts/flume_sync.py` which calls the Flume portal API

### First-time setup for Flume sync

1. Make sure Python 3 is available on your HA system (HA OS has it)
2. Install `requests`: in HA terminal, run `pip3 install requests`
3. Add your Flume credentials to the environment or as arguments (see script header)
4. Test manually: `python3 /config/scripts/flume_sync.py --output /tmp/test.json --verbose`
5. The daily automation runs at 2:00 AM and accumulates results into lifetime totals

### Running it manually (backfill)

```bash
# Fetch data for a specific past date
python3 /config/scripts/flume_sync.py \
  --output /config/flume_categories.json \
  --date 2024-01-14 \
  --token-cache /config/.flume_token_cache.json \
  --verbose
```

### Lifetime totals

Category totals accumulate in `input_number.water_lifetime_*_gal`. These persist through restarts and are updated once daily after the Flume sync. They can be reset via the HA UI if you want a fresh start.

---

## Energy

Add your Eve Energy (or other) plug entity names to `packages/utilities/energy.yaml`. Look for lines with `# ← update entity name` and replace with your actual sensor entity IDs.

Energy rate is set via `input_number.electricity_price_usd_kwh` in configuration.yaml.

Lifetime totals accumulate daily at midnight into `input_number.energy_lifetime_*_kwh`.

---

## Adding New Helpers / Packages

To add a new area or integration:
1. Create `packages/{category}/{name}.yaml`
2. HA automatically picks it up (via `!include_dir_named packages`)
3. No changes to `configuration.yaml` needed

Examples of things to add:
- `packages/climate/hvac.yaml` — heating/cooling tracking
- `packages/security/cameras.yaml` — camera status
- `packages/appliances/washer_dryer.yaml` — cycle detection
- `packages/utilities/gas.yaml` — natural gas usage (if metered)

---

## Secrets Reference

All secrets are in `secrets.yaml` (not committed). See `secrets.yaml.example` for the full list.

| Secret | Used by |
|--------|---------|
| `milwaukee_garbage_url` | `trash_recycling.yaml` |
| `home_latitude` / `home_longitude` | `snow_plows.yaml`, `leaf_collection.yaml` |
| `flume_client_id/secret/username/password` | `scripts/flume_sync.py` |
| `electricity_price_usd_kwh` | `configuration.yaml` |
