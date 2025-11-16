# Display Clients

Two lightweight front-ends live under `display_clients/` so you can preview rack data without touching the physical panels. Both consume the same FastAPI endpoints exposed by `jetson/api_service`.

## iPhone Dashboard (`iphone_dashboard/`)
- Pure HTML/CSS/JS PWA meant to run full-screen on an iPhone behind the two-way mirror.
- Served statically (e.g., `python -m http.server 8080 --directory display_clients/iphone_dashboard`).
- Auto-discovers the API at `window.location.origin` but you can override by opening Safari dev tools and running:
  ```js
  localStorage.setItem('rehoboam_api', 'http://jetson-rack.local:8000');
  ```
- Shows LED status, divergence score, and recent events using the `/status`, `/divergence`, and `/health` endpoints.

## E-ink PNG renderer (`eink_client/`)
- CLI utility that renders grayscale PNGs using Pillow so you can test scene layouts before the IT8951 hardware arrives.
- Install deps with `pip install -r display_clients/eink_client/requirements.txt` (Pillow + requests).
- Run manually or via cron:
  ```bash
  python display_clients/eink_client/render.py \
    --api http://jetson-rack.local:8000 \
    --scene divergence \
    --output /tmp/rehoboam.png
  ```
- Generated PNGs can be SCP’d to the Jetson or directly pushed to the `epaper/` service for proof-of-life tests.

Both projects are intentionally simple (no build tools) so you can tweak CSS/JS quickly while standing at the rack. Use them as references when building the production kiosk UI or when writing CLI tooling.
