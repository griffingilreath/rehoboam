# Systemd Templates

These units provide a starting point for running each Jetson service under systemd on the Jetson Nano (or any Linux host). Customize paths to match your deployment, copy to `/etc/systemd/system/`, and enable as needed.

## Step 1: Layout

Assuming the repo lives at `/opt/rehoboam` with a virtual environment in `/opt/rehoboam/.venv` and shared data directory `/opt/rehoboam/data`:

```bash
sudo mkdir -p /opt/rehoboam/data
sudo chown -R jetson:jetson /opt/rehoboam
```

## Step 2: Environment File

`/etc/rehoboam.env`:

```
REHOBOAM_HOME=/opt/rehoboam
REHOBOAM_VENV=/opt/rehoboam/.venv
REHOBOAM_DATA=/opt/rehoboam/data
PYTHONUNBUFFERED=1
```

## Step 3: Unit Files

Copy the unit files from this directory into `/etc/systemd/system/`, edit any paths/config names, and reload systemd:

```bash
sudo cp systemd/rehoboam-config-sync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rehoboam-config-sync.service
```

Repeat for each service you want running continuously.

### Included Units

- `rehoboam-config-sync.service`
- `rehoboam-collector.service`
- `rehoboam-state-engine.service`
- `rehoboam-led-encoder.service`
- `rehoboam-api.service`
- `rehoboam-ml.service` (optional but needed for `/divergence`)

Each unit sets the working directory to `${REHOBOAM_HOME}` and runs the service via the virtualenv’s Python interpreter. Adjust the ExecStart lines if you package the code differently.

## Logs & Health

Check logs with `journalctl -u <unit> -f`. All services also update `service_health.json`, so dashboards consuming `/health` remain accurate when managed by systemd.
