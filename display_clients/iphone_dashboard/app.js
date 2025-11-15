const API_BASE = window.localStorage.getItem('rehoboam_api') || window.location.origin;
const STATUS_URL = `${API_BASE}/status`;
const CONFIG_URL = `${API_BASE}/config`;
const HEALTH_URL = `${API_BASE}/health`;
const DIVERGENCE_URL = `${API_BASE}/divergence`;

document.getElementById('api-endpoint').textContent = API_BASE;

document.getElementById('refresh-button').addEventListener('click', () => refresh(true));

async function fetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function healthClass(status) {
  return `health-${(status || 'unknown').toLowerCase()}`;
}

function formatTimestamp(ts) {
  if (!ts) return '--';
  const date = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function renderLedGrid(state, config) {
  const grid = document.getElementById('led-grid');
  grid.innerHTML = '';
  const leds = state.leds || [];
  leds.forEach((led) => {
    const meta = config?.leds?.find((entry) => entry.index === led.index) || {};
    const card = document.createElement('div');
    card.className = `led-card ${healthClass(led.health)}`;
    const pct = Math.min(100, Math.round((led.activity_level || 0) * 100));
    card.innerHTML = `
      <h3>${led.name || meta.name || `LED ${led.index}`}</h3>
      <div class="meta">${led.health || 'UNKNOWN'} • ${led.activity_type || 'none'}</div>
      <div class="meta">${meta.type || 'unknown'}${meta.ip ? ` • ${meta.ip}` : ''}</div>
      <div class="activity"><span style="width:${pct}%"></span></div>
    `;
    grid.appendChild(card);
  });
}

function renderPiHoleSummary(state) {
  const card = document.getElementById('pihole-summary');
  const pihole = (state.leds || []).find((led) => (led.name || '').toLowerCase().includes('pi-hole'));
  if (!pihole) {
    card.textContent = 'No Pi-hole LED configured.';
    return;
  }
  card.innerHTML = `
    <strong>${pihole.name}</strong><br />
    Health: ${pihole.health} • Activity: ${(pihole.activity_level || 0).toFixed(2)}
  `;
}

function renderHealth(health) {
  const container = document.getElementById('service-health');
  const services = health?.services || [];
  if (!services.length) {
    container.textContent = 'Awaiting heartbeat from services...';
    return;
  }
  container.innerHTML = services
    .map(
      (svc) => `
      <div class="led-card ${healthClass(svc.status)}">
        <strong>${svc.name}</strong><br />
        Status: ${svc.status || 'unknown'} • Last update: ${formatTimestamp(svc.updated_at)}
      </div>`
    )
    .join('');
}

function renderDivergence(divergence) {
  const chip = document.getElementById('divergence-level');
  if (!divergence || typeof divergence.score === 'undefined') {
    chip.textContent = 'Divergence: --';
    return;
  }
  chip.textContent = `Divergence: ${divergence.level?.toUpperCase() || 'UNKNOWN'} (${divergence.score.toFixed(2)})`;
}

async function refresh(manual = false) {
  try {
    const [state, config, health, divergence] = await Promise.all([
      fetchJson(STATUS_URL),
      fetchJson(CONFIG_URL).catch(() => null),
      fetchJson(HEALTH_URL).catch(() => null),
      fetchJson(DIVERGENCE_URL).catch(() => null),
    ]);
    renderLedGrid(state, config);
    renderPiHoleSummary(state);
    renderHealth(health);
    renderDivergence(divergence);
    document.getElementById('last-update').textContent = `Updated: ${formatTimestamp(state.timestamp)}`;
  } catch (error) {
    console.error('Refresh failed', error);
    if (manual) {
      alert(`Refresh failed: ${error.message}`);
    }
  }
}

refresh();
setInterval(refresh, 10_000);
