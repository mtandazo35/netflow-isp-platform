const $ = (id) => document.getElementById(id);
const formatBytes = (value = 0) => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let amount = Number(value), index = 0;
  while (amount >= 1000 && index < units.length - 1) { amount /= 1000; index++; }
  return `${amount.toLocaleString('es-EC', { maximumFractionDigits: index > 2 ? 2 : 1 })} ${units[index]}`;
};
const number = (value = 0) => Number(value).toLocaleString('es-EC');
const api = async (path) => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
};

function renderClients(items) {
  const body = $('top-clients');
  body.innerHTML = '';
  if (!items.length) { body.append($('empty-row').content.cloneNode(true)); return; }
  for (const item of items) {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${item.subscriber_name || `ID ${item.subscriber_id}`}</td><td>${formatBytes(item.bytes_down)}</td><td>${formatBytes(item.bytes_up)}</td><td>${number(item.unique_destinations)}</td><td>${number(item.flows)}</td>`;
    body.append(row);
  }
}

function renderRisk(items) {
  const list = $('risk-list');
  list.innerHTML = '';
  if (!items.length) { list.innerHTML = '<p class="empty">Sin candidatos para este periodo.</p>'; return; }
  for (const item of items.slice(0, 8)) {
    const score = Math.round(Number(item.risk_score || 0));
    const node = document.createElement('div');
    node.className = `risk-item ${score >= 75 ? 'high' : ''}`;
    node.innerHTML = `<div class="risk-title"><span>${item.subscriber_name || item.subscriber_id}</span><span>${score}/100</span></div><div class="risk-meta">${formatBytes(item.total_bytes)} · ${number(item.active_hours)} horas activas · ${number(item.unique_destinations)} destinos</div><div class="bar"><span style="width:${Math.min(100, score)}%"></span></div>`;
    list.append(node);
  }
}

function renderDestinations(items) {
  const list = $('destinations');
  list.innerHTML = '';
  if (!items.length) { list.innerHTML = '<p class="empty">Sin destinos registrados.</p>'; return; }
  for (const item of items.slice(0, 8)) {
    const node = document.createElement('div');
    node.className = 'destination-item';
    node.innerHTML = `<div class="destination-title"><span>${item.domain || item.destination_ip}</span><span>${formatBytes(item.total_bytes)}</span></div><div class="destination-meta">${item.application || 'Sin clasificar'} · ${number(item.subscribers)} clientes · ${number(item.flows)} flujos</div>`;
    list.append(node);
  }
}

async function loadDashboard() {
  const hours = $('hours').value;
  $('status').textContent = 'Actualizando información…';
  $('status-dot').className = 'dot';
  try {
    const [overview, clients, risks, destinations] = await Promise.all([
      api(`/api/v1/analytics/overview?hours=${hours}`),
      api(`/api/v1/analytics/top-subscribers?hours=${hours}&limit=50`),
      api(`/api/v1/analytics/resale-candidates?hours=${Math.max(24, Number(hours))}&limit=20`),
      api(`/api/v1/analytics/top-destinations?hours=${hours}&limit=20`),
    ]);
    $('total').textContent = formatBytes(overview.total_bytes);
    $('down').textContent = formatBytes(overview.bytes_down);
    $('up').textContent = formatBytes(overview.bytes_up);
    $('subscribers').textContent = number(overview.subscribers);
    $('flows').textContent = number(overview.flows);
    $('exporters').textContent = number(overview.exporters);
    renderClients(clients.items || []);
    renderRisk(risks.items || []);
    renderDestinations(destinations.items || []);
    $('status').textContent = 'Sistema operativo';
    $('status-dot').className = 'dot ok';
    $('updated').textContent = `Actualizado ${new Date().toLocaleTimeString('es-EC')}`;
  } catch (error) {
    $('status').textContent = `Sin conexión: ${error.message}`;
    $('status-dot').className = 'dot error';
  }
}

$('refresh').addEventListener('click', loadDashboard);
$('hours').addEventListener('change', loadDashboard);
loadDashboard();
setInterval(loadDashboard, 60_000);
