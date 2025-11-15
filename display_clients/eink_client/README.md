# E-ink Rendering Client

Simple Python script that fetches the Jetson API and renders a grayscale PNG suitable for e-ink displays. Intended to run every 30–60 seconds (cron, systemd timer) and push the resulting bitmap to a Waveshare-style panel.

## Setup

1. Install dependencies (prefer virtualenv):
   ```bash
   cd display_clients/eink_client
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run a test render:
   ```bash
   python render.py --api http://jetson-rack.local:8000 --output /tmp/rack.png
   ```
3. Display the PNG using your panel’s driver script (varies by hardware).

## Customising

- `CANVAS` controls resolution; match your panel’s pixel dimensions.
- Update `FONT_PATHS` to point to fonts available on your system.
- Extend `summarize_leds` to show additional metrics (Pi-hole QPS, divergence history, etc.).
- If you already have an e-ink driver pipeline, integrate `compose_image` to draw directly onto the device buffer.

## Automation

Example systemd timer snippet:

```ini
[Unit]
Description=Render Rehoboam E-ink Snapshot

[Service]
WorkingDirectory=/opt/rehoboam/display_clients/eink_client
ExecStart=/usr/bin/python render.py --api http://127.0.0.1:8000 --output /opt/eink/frame.png

[Install]
WantedBy=multi-user.target
```

Pair with a companion service that uploads or pushes `/opt/eink/frame.png` to the display.
