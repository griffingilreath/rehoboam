# iPhone Dashboard Client

Minimal PWA-style dashboard intended to run on an iPhone 12 Pro Max (full-screen Safari via Guided Access). It reads the Jetson API and displays LED health, activity, Pi-hole highlights, and service health summaries.

## Setup

1. Build and run the Jetson services (config sync, collector, state engine, API, optional ML).
2. Serve the dashboard files.
   - Easiest: `python -m http.server 8080 --directory display_clients/iphone_dashboard`.
   - Or host from any static file server / CDN.
3. On the iPhone, open `http://jetson-rack.local:8080` (adjust hostname/port).
4. Use Safari’s share sheet → “Add to Home Screen” for kiosk-like behavior.

## Configuration

The dashboard uses `window.location.origin` as the API base. To override:

```js
localStorage.setItem('rehoboam_api', 'http://jetson-rack.local:8000');
```

Reload the page to apply.

## Files

- `index.html` – Layout (header, LED grid, cards).
- `styles.css` – Glassmorphism-inspired styling for dark-mode displays.
- `app.js` – Fetches `/status`, `/config`, `/health`, `/divergence` and renders tiles. Includes manual refresh + auto-refresh every 10 seconds.

## Tips

- Keep Safari in Guided Access to prevent accidental navigation.
- Adjust CSS grid breakpoints if you repurpose for larger displays.
- Extend `renderPiHoleSummary` / `renderHealth` to include more metrics (charts, spark lines) as needed.
