# Home Assistant Configuration

This directory contains the Home Assistant configuration for the Rehoboam Rack house.

> **Note:** This will eventually live in its own private git repo. For now it's co-located here.

---

## Quick Setup

1. **Copy secrets:** `cp secrets.yaml.example secrets.yaml` and fill in all values
2. **Install Flume integration:** Add via HA → Settings → Integrations → Flume (for real-time flow)
3. **Install AppDaemon add-on:** See _Water / Flume_ section below
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
│   │   ├── snow_plows.yaml     # Snow plow detection & persistent history
│   │   ├── trash.yaml          # Garbage pickup schedule (self-contained)
│   │   ├── recycling.yaml      # Recycling pickup schedule (self-contained)
│   │   └── leaf_collection.yaml # Leaf collection season & route status
│   ├── utilities/
│   │   ├── water_session.yaml  # Real-time Flume session tracking + leak detection
│   │   ├── water_flume.yaml    # Daily category sync (AppDaemon) + lifetime totals
│   │   └── energy.yaml         # Electricity tracking + lifetime costs
│   ├── rehoboam/
│   │   └── rack_config.yaml    # LED helpers (synced with Rehoboam rack)
│   └── zones/
│       ├── exterior.yaml
│       ├── floor_1.yaml
│       ├── floor_2.yaml
│       └── basement.yaml
└── addon_configs/
    └── appdaemon/
        ├── secrets.yaml.example  # AppDaemon credentials template
        └── apps/
            ├── apps.yaml         # AppDaemon app registration
            ├── requirements.txt  # Python deps (requests)
            └── flume_sync.py     # Daily Flume category sync app
```

---

## Municipal Services

See [`packages/municipal/README.md`](packages/municipal/README.md) for API maintenance details.

Key things to know:
- **Snow plows** — works automatically, stable ArcGIS endpoint; history persists between storms
- **Trash** — requires `milwaukee_garbage_url` in `secrets.yaml`
- **Recycling** — same endpoint as trash, fully independent package
- **Leaf collection** ⚠️ — **requires annual URL update each September** (prompted automatically on Sep 15)

Each municipal package is fully self-contained — commenting out one file won't break any other.

---

## Water (Flume)

### How it works

Three-part system:
1. **Real-time flow** — via the native HA Flume integration (`sensor.flume_sensor_*`)
2. **Session tracking** — `water_session.yaml` accumulates flow into per-session stats with a gap timer
3. **Daily categories** — `water_flume.yaml` + AppDaemon sync app pull category data from the Flume portal

### AppDaemon Setup (replaces Mac Mini cron job)

AppDaemon is a HA add-on with its own Python environment. It runs the Flume sync directly inside HA — no Mac Mini or external cron needed.

#### 1. Install AppDaemon add-on

In HA: **Settings → Add-ons → Add-on Store → AppDaemon**

#### 2. Configure credentials

```bash
# On your HA system (SSH or Terminal add-on):
cp /config/addon_configs/appdaemon/secrets.yaml.example \
   /addon_configs/appdaemon/secrets.yaml
# Edit secrets.yaml and fill in your Flume credentials
```

#### 3. Install Python dependency

In the AppDaemon add-on configuration, add to **Python packages**:
```
requests>=2.32
```
Or place `requirements.txt` in `/addon_configs/appdaemon/apps/` (AppDaemon auto-installs on startup).

#### 4. Copy app files

```bash
cp /config/addon_configs/appdaemon/apps/flume_sync.py  /addon_configs/appdaemon/apps/
cp /config/addon_configs/appdaemon/apps/apps.yaml       /addon_configs/appdaemon/apps/
```

#### 5. Test immediately (optional)

In `apps.yaml`, temporarily set `run_on_startup: true`, restart AppDaemon, then check logs:
**Settings → Add-ons → AppDaemon → Log**

You should see `[FlumeSyncApp] Sync complete` and `sensor.flume_yesterday_total` appear in HA.

#### 6. Retire the Mac Mini cron job

Once AppDaemon is verified, disable or remove the cron entry on the Mac Mini that called the old `flume_sync.py` script. The AppDaemon app runs at 02:05 AM daily automatically.

### What the sync creates

After each successful run, these sensors appear in HA:
- `sensor.flume_yesterday_total` — total gallons (with `date` and `synced_at` attributes)
- `sensor.flume_yesterday_shower` / `toilet` / `faucet` / `irrigation` / `bathtub` / `laundry` / `dishwasher` / `other` / `leak`

The `flume_sync_complete` event fires after each sync, triggering accumulation into lifetime odometers.

### Lifetime totals

Category totals accumulate in `input_number.water_lifetime_*_gal`. These persist through restarts and are updated once daily. Reset via HA UI (Settings → Helpers) if you want a fresh start.

### Sync failure alert

If no sync has run in 24+ hours, a notification fires at 6 AM. Check AppDaemon logs for details.

---

## Energy

Add your Eve Energy (or other) plug entity names to `packages/utilities/energy.yaml`. Look for lines with `# ← update entity name` and replace with your actual sensor entity IDs.

Energy rate is set via `input_number.electricity_price_usd_kwh` in `configuration.yaml`.

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
| `milwaukee_garbage_url` | `trash.yaml`, `recycling.yaml` |
| `home_latitude` / `home_longitude` | `snow_plows.yaml`, `leaf_collection.yaml` |
| `electricity_price_usd_kwh` | `configuration.yaml` |

AppDaemon has its own `secrets.yaml` at `/addon_configs/appdaemon/secrets.yaml`:

| Secret | Used by |
|--------|---------|
| `flume_client_id` / `flume_client_secret` | `apps/flume_sync.py` |
| `flume_username` / `flume_password` | `apps/flume_sync.py` |
