const API_BASE = window.DEV_API_BASE || window.location.origin;
const DATA_BASE = window.DEV_DATA_BASE || '../data';
const ledGrid = document.getElementById('led-grid');
const contextEl = document.getElementById('context');
const piholeEl = document.getElementById('pihole');
const divergenceEl = document.getElementById('divergence');
const recommendationsEl = document.getElementById('recommendations');
const eventsEl = document.getElementById('events');

async function fetchJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Request failed: ${resp.status}`);
  return resp.json();
}

function healthClass(health) {
  switch ((health || 'unknown').toLowerCase()) {
    case 'ok':
      return 'health-ok';
    case 'warning':
      return 'health-warning';
    case 'error':
      return 'health-error';
    case 'offline':
      return 'health-offline';
    default:
      return 'health-unknown';
  }
}

function pct(n) {
  return `${Math.round((n || 0) * 100)}%`;
}

function renderLedGrid(status) {
  if (!status || !Array.isArray(status.leds)) {
    ledGrid.innerHTML = '<p>No LED data.</p>';
    return;
  }
  ledGrid.innerHTML = status.leds
    .map(
      (led) => `
        <div class="led-card ${healthClass(led.health)}">
          <h3>${led.name || `LED ${led.index}`}</h3>
          <div class="meta">Health: ${led.health || 'UNKNOWN'} · Activity: ${pct(led.activity_level)}</div>
          <div class="meta">Type: ${led.type || 'unknown'} · Last type: ${led.activity_type || 'none'}</div>
        </div>
      `
    )
    .join('');
}

function renderContext(context) {
  if (!context) {
    contextEl.textContent = 'No context yet.';
    return;
  }
  const flags = context.flags || {};
  const entities = context.entities || {};
  const parts = [
    `Timestamp: ${new Date((context.timestamp || 0) * 1000).toLocaleString()}`,
    `Daypart: ${context.daypart || 'n/a'}`,
    `Occupied: ${flags.occupied ? 'yes' : 'no'}`,
    `Rain expected: ${flags.rain_expected ? 'yes' : 'no'}`,
  ];
  const entityList = Object.entries(entities)
    .map(([id, entry]) => `${id}: ${entry.state}`)
    .join('<br/>');
  contextEl.innerHTML = `${parts.join('<br/>')}<hr/>${entityList}`;
}

function renderPihole(status) {
  if (!status || !status.leds) {
    piholeEl.textContent = 'No devices.';
    return;
  }
  const pihole = status.leds.find((led) => (led.type || '').toLowerCase() === 'pihole');
  if (!pihole) {
    piholeEl.textContent = 'No Pi-hole LED configured.';
    return;
  }
  const entries = [
    `Name: ${pihole.name}`,
    `QPS: ${(pihole.qps || 0).toFixed(1)}`,
    `Blocked ratio: ${pct(pihole.blocked_ratio)}`,
    `Status: ${pihole.pihole_status || 'unknown'}`,
  ];
  piholeEl.innerHTML = entries.join('<br/>');
}

function renderDivergence(divergence) {
  if (!divergence) {
    divergenceEl.textContent = 'No divergence data.';
    recommendationsEl.textContent = '';
    return;
  }
  divergenceEl.innerHTML = `Score: ${divergence.score?.toFixed?.(2) || divergence.score || 0}<br/>Level: ${divergence.level}`;
  const recs = divergence.recommendations || [];
  if (!recs.length) {
    recommendationsEl.textContent = 'No recommendations.';
  } else {
    recommendationsEl.innerHTML = recs
      .map(
        (r) => `
          <div>
            <strong>${r.suggestion}</strong> → ${r.target || ''}<br/>
            Trigger: ${r.trigger} · Confidence: ${(r.confidence || 0) * 100}%
          </div>
        `
      )
      .join('<hr/>');
  }
}

function renderEvents(events) {
  if (!events || !events.length) {
    eventsEl.textContent = 'No events logged.';
    return;
  }
  eventsEl.innerHTML = events
    .slice(-6)
    .reverse()
    .map(
      (evt) => `
        <div>
          <strong>${evt.friendly_name || evt.entity_id}</strong><br/>
          ${evt.summary || evt.state || ''}<br/>
          Actor: ${evt.actor || 'unknown'} (${evt.origin || 'HA'})
        </div>
      `
    )
    .join('<hr/>');
}

async function refresh() {
  try {
    const [status, divergence, health, eventsPayload] = await Promise.all([
      fetchJson(`${API_BASE}/status`),
      fetchJson(`${API_BASE}/divergence`).catch(() => null),
      fetchJson(`${API_BASE}/health`).catch(() => null),
      fetchJson(`${DATA_BASE}/events.json`).catch(() => ({ events: [] })),
    ]);
    renderLedGrid(status);
    renderContext(status?.context);
    renderPihole(status);
    renderDivergence(divergence);
    const events = eventsPayload?.events || [];
    renderEvents(events);
  } catch (err) {
    console.error('Refresh failed', err);
  }
}

document.getElementById('refresh').addEventListener('click', refresh);
refresh();
setInterval(refresh, 10000);
