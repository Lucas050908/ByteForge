const DEFAULT_API_BASE = 'http://127.0.0.1:8080';
const BASE = window.BYTEFORGE_API_BASE || localStorage.getItem('BYTEFORGE_API_BASE') || (location.protocol === 'file:' ? DEFAULT_API_BASE : '');
const _nativeFetch = window.fetch.bind(window);
window.fetch = (input, init={}) => {
  const url = typeof input === 'string' ? input : input?.url || '';
  const apiUrl = url.startsWith('/api/') || url.includes('/api/');
  if (apiUrl) init = {...init, credentials:'include'};
  return _nativeFetch(input, init);
};
let _authUser = null;
let _setupRequired = false;

function showLogin(msg='', setup=false) {
  _setupRequired = setup;
  const screen = document.getElementById('login-screen');
  if (screen) screen.classList.remove('hidden');
  document.querySelectorAll('.login-setup-only').forEach(el => el.style.display = setup ? 'block' : 'none');
  document.getElementById('login-user').value = 'ADMIN';
  document.getElementById('login-user').disabled = setup;
  document.getElementById('login-btn').textContent = setup ? 'CREATE ADMIN PASSWORD' : 'LOGIN';
  if (msg) document.getElementById('login-msg').textContent = msg;
}

function hideLogin() {
  const screen = document.getElementById('login-screen');
  if (screen) screen.classList.add('hidden');
}

async function authStatus() {
  try {
    const r = await fetch(BASE + '/api/auth/status');
    return await r.json();
  } catch {
    return {authenticated:false};
  }
}

async function login() {
  if (_setupRequired) {
    const body = {
      password: document.getElementById('login-pass').value,
      confirm: document.getElementById('login-confirm').value
    };
    try {
      const r = await fetch(BASE + '/api/auth/setup', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const d = await r.json();
      showLogin(d.msg || 'Admin password setup', !d.ok);
      if (d.ok) {
        _setupRequired = false;
        document.getElementById('login-pass').value = '';
        document.getElementById('login-confirm').value = '';
      }
    } catch(e) {
      showLogin(apiOfflineMessage());
    }
    return;
  }
  const body = {
    username: document.getElementById('login-user').value,
    password: document.getElementById('login-pass').value,
    otp: document.getElementById('login-otp').value
  };
  const btn = document.getElementById('login-btn');
  btn.disabled = true;
  try {
    const r = await fetch(BASE + '/api/auth/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d = await r.json();
    if (!d.ok) {
      if (d.requires_2fa) {
        document.getElementById('login-otp-label').style.display = 'block';
        document.getElementById('login-otp').style.display = 'block';
      }
      showLogin(d.msg || 'Login failed');
      return;
    }
    _authUser = d.user;
    hideLogin();
    startApp();
  } catch(e) {
    showLogin(apiOfflineMessage());
  } finally {
    btn.disabled = false;
  }
}

function apiOfflineMessage() {
  if (location.protocol === 'file:') {
    return 'Could not reach ByteForge API. Start the server, then open http://127.0.0.1:8080';
  }
  return 'Could not reach ByteForge API. Make sure byteforge-server.py is running.';
}

async function logout() {
  await fetch(BASE + '/api/auth/logout', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  location.reload();
}

async function changePassword() {
  const body = {
    current: document.getElementById('auth-current').value,
    new_password: document.getElementById('auth-new').value
  };
  const r = await fetch(BASE + '/api/auth/password', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d = await r.json();
  toast(d.msg || 'Password updated', d.ok);
}

async function setup2FA() {
  const r = await fetch(BASE + '/api/auth/2fa/setup', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const d = await r.json();
  if (!d.ok) { toast(d.msg || '2FA setup failed', false); return; }
  document.getElementById('totp-secret').innerHTML = `${escapeHTML(d.secret)}<br><span style="color:var(--t3)">Add this secret manually in your authenticator app.</span>`;
  toast('2FA secret generated');
}

async function enable2FA() {
  const otp = document.getElementById('totp-code').value;
  const r = await fetch(BASE + '/api/auth/2fa/enable', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({otp})});
  const d = await r.json();
  toast(d.msg || '2FA updated', d.ok);
  if (d.ok) updateAuthPanel();
}

async function updateAuthPanel() {
  const d = await authStatus();
  _authUser = d.user;
  const userEl = document.getElementById('auth-user');
  const twoEl = document.getElementById('auth-2fa');
  if (userEl) userEl.textContent = d.user?.username || 'local';
  if (twoEl) twoEl.textContent = d.user?.totp_enabled ? 'ENABLED' : 'DISABLED';
}

// ── NAV ──
function nav(id, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sb-item').forEach(s => s.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  el.classList.add('active');
  loadPage(id);
}

function loadPage(id) {
  const map = {overview:loadOverview, system:loadSystem, network:loadNetwork, nas:loadNAS, raid:loadRAID, docker:loadDocker, minecraft:loadGameServers, proxy:loadProxy, files:loadFiles, access:loadAccess, settings:loadSettings, diskheath:loadDiskHealth, appstore:loadApps, terminal:initTerminal, backup:loadBackup, studio:loadStudio, dash:loadDashEditor};
  if (map[id]) map[id]();
}

// ── CLOCK ──
function tick() {
  const n = new Date();
  document.getElementById('clock').textContent = n.toISOString().slice(0,10) + ' ' + n.toTimeString().slice(0,8);
}
tick(); setInterval(tick, 1000);

// ── TOAST ──
function toast(msg, ok=true) {
  const t = document.getElementById('toast');
  t.innerHTML = (ok?'<span style="color:var(--ok)">✓</span>':'<span style="color:var(--err)">✗</span>') + ' ' + msg;
  t.style.borderColor = ok ? 'var(--ok)' : 'var(--err)';
  t.style.display = 'block';
  clearTimeout(t._t); t._t = setTimeout(() => t.style.display='none', 3500);
}

// ── BADGE ──
function mkbadge(status, okLabel='AKTIV', errLabel='INAKTIV') {
  const ok = ['running','active','active (running)','online'].includes((status||'').toLowerCase());
  const cls = ok ? 'b-ok' : 'b-err';
  return `<span class="badge ${cls}"><span class="bd"></span>${(ok?okLabel:errLabel).toUpperCase()}</span>`;
}

// ── API ──
async function api(path) {
  try {
    const r = await fetch(BASE+path);
    if (r.status === 401) { showLogin('Please log in to continue.'); return null; }
    return await r.json();
  } catch { return null; }
}

// ── TICKER UPDATE ──
async function updateTicker() {
  const d = await api('/api/all');
  if (!d) return;
  const s = d.system;
  document.getElementById('tk-cpu').textContent = s.cpu + '%';
  document.getElementById('tk-ram').textContent = s.ram_pct + '%';
  document.getElementById('tk-temp').textContent = s.temp + '°C';
  document.getElementById('tk-up').textContent = s.uptime;
  document.getElementById('tk-mc').textContent = d.minecraft.status === 'running' ? 'ONLINE' : 'OFFLINE';
  document.getElementById('sb-docker-count').textContent = d.docker.length;
  document.getElementById('sb-game-count').textContent = d.game_servers?.length || 0;
  window._lastData = d;
  checkNotifications(s);
  updateGraphs();
  // Refresh active page stats
  if (document.getElementById('page-overview')?.classList.contains('active')) loadOverview();
  else if (document.getElementById('page-system')?.classList.contains('active')) loadSystem();
}

// ── OVERVIEW ──
async function loadOverview() {
  const [d, hw] = await Promise.all([
    window._lastData ? Promise.resolve(window._lastData) : api('/api/all'),
    api('/api/hardware')
  ]);
  if (!d) return;
  const s = d.system;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerHTML = val; };

  // System stats
  set('ov-cpu', s.cpu + '<span class="u">%</span>');
  set('ov-ram', s.ram_pct + '<span class="u">%</span>');
  set('ov-ram-s', `${s.ram_used_mb} MB / ${s.ram_total_mb} MB`);
  set('ov-temp', s.temp + '<span class="u">°C</span>');
  set('ov-up', '⏱ Uptime: ' + s.uptime);

  // Network
  const latest = _graphData?.net_rx?.slice(-1)[0];
  if (latest !== undefined) {
    set('ov-net-rx', fmtBytes(latest) + '<span class="u">/s</span>');
    const txLatest = _graphData?.net_tx?.slice(-1)[0];
    if (txLatest !== undefined) set('ov-net-tx', fmtBytes(txLatest) + '<span class="u">/s</span>');
  } else {
    set('ov-net-rx', '—'); set('ov-net-tx', '—');
  }

  // Docker
  set('ov-dc', d.docker.length);

  // Game servers
  const gsOnline = (d.game_servers || []).filter(s => s.status === 'running').length;
  const gsTotal = (d.game_servers || []).length;
  set('ov-gs-online', gsOnline);
  set('ov-gs-total', gsTotal);

  // NAS
  set('ov-nas-b', mkbadge(d.nas.status));
  set('ov-nas-shares', d.nas.shares?.length ? d.nas.shares.length + ' share(s)' : 'Ingen shares konfigureret');

  // RAID
  const raidOk = d.raid.status === 'active';
  set('ov-raid-b', mkbadge(raidOk ? 'running' : d.raid.status));
  set('ov-raid-info', raidOk ? 'Array aktiv' : (d.raid.status === 'inactive' ? 'Ingen RAID' : d.raid.status));

  // Hardware
  if (hw) {
    set('ov-hostname', hw.hostname || '—');
    const osStr = hw.os_name || hw.platform;
    const kernelStr = hw.kernel ? `<br><span style="font-size:9px;color:var(--t3)">${escapeHTML(hw.kernel)}</span>` : '';
    set('ov-os', escapeHTML(osStr) + kernelStr);
    set('ov-cpu-model', escapeHTML(hw.cpu_model) + `<br><span style="color:var(--t3)">${hw.cpu_cores} logiske tråde</span>`);
    set('ov-gpu', escapeHTML(hw.gpu));
  }

  // Disks — color coded by usage
  if (d.disks?.length) {
    document.getElementById('ov-disks').innerHTML = d.disks.map(dk => {
      const pct = parseInt(dk.pct) || 0;
      const barColor = pct > 90 ? 'var(--err)' : pct > 75 ? 'var(--warn)' : 'var(--o)';
      const pctColor = pct > 90 ? 'var(--err)' : pct > 75 ? 'var(--warn)' : 'var(--o2)';
      return `<div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <span style="font-family:var(--display);font-size:20px;letter-spacing:2px">${escapeHTML(dk.mount)}</span>
          <span style="font-family:var(--mono);font-size:11px;color:${pctColor};font-weight:700">${pct}%</span>
        </div>
        <div style="height:6px;background:var(--b);overflow:hidden;margin-bottom:8px">
          <div style="height:6px;width:${pct}%;background:${barColor};transition:width 1s"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--t3)">
          <span>${dk.used}GB brugt</span><span>${dk.free}GB fri</span><span>${dk.total}GB total</span>
        </div>
      </div>`;
    }).join('');
  } else {
    document.getElementById('ov-disks').innerHTML = '<div class="card"><div class="cs">Ingen diskdata tilgængelig</div></div>';
  }
}

function fmtBytes(bytes) {
  if (!bytes || bytes < 1024) return (bytes || 0) + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ── SYSTEM ──
async function loadSystem() {
  const s = await api('/api/system');
  if (!s) return;
  const cpuPct = s.cpu;
  const ramPct = s.ram_pct;
  document.getElementById('ring-cpu').textContent = cpuPct + '%';
  document.getElementById('ring-ram').textContent = ramPct + '%';
  const offset = pct => 201 - (201 * pct / 100);
  document.getElementById('ring-cpu-c').style.strokeDashoffset = offset(cpuPct);
  document.getElementById('ring-ram-c').style.strokeDashoffset = offset(ramPct);
  document.getElementById('sys-temp2').textContent = s.temp;
  document.getElementById('sys-uptime2').textContent = s.uptime;
  document.getElementById('sys-ram-detail').textContent = s.ram_used_mb + ' MB brugt af ' + s.ram_total_mb + ' MB total';
  document.getElementById('sys-ram-bar2').style.width = ramPct + '%';
}

// ── NETWORK ──
async function loadNetwork() {
  const [uptime, net, devices, wh] = await Promise.all([
    api('/api/uptime'), api('/api/network'), api('/api/network/devices'), api('/api/webhook')
  ]);
  // Uptime bars from real history
  ['nfs','inet'].forEach(id => {
    const barEl = document.getElementById('mon-' + id);
    const pingEl = document.getElementById('ping-' + id);
    if (!barEl) return;
    const check = uptime?.[id];
    const up = check?.up ?? true;
    const history = check?.history || [];
    // Pad with nulls if history shorter than 30
    const bars = [...Array(Math.max(0, 30 - history.length)).fill(null), ...history];
    barEl.innerHTML = bars.map(h =>
      h === null ? `<div class="mbar" style="opacity:.2"></div>`
                 : `<div class="mbar ${h ? 'up' : 'down'}"></div>`
    ).join('');
    if (pingEl && check) {
      if (check.latency_ms != null) {
        pingEl.textContent = check.latency_ms + ' ms';
        pingEl.style.color = check.latency_ms > 100 ? 'var(--warn)' : 'var(--ok)';
      } else {
        pingEl.textContent = up ? 'ONLINE' : 'OFFLINE';
        pingEl.style.color = up ? 'var(--ok)' : 'var(--danger)';
      }
    }
  });
  // Network info + DNS
  if (net) {
    const dns = (net.dns || []).join(', ') || '—';
    document.getElementById('net-info').innerHTML = `
      <tr><td>Interface</td><td style="color:var(--o2)">${escapeHTML(net.interface)}</td></tr>
      <tr><td>IP Adresse</td><td style="color:var(--o2)">${escapeHTML(net.ip)}</td></tr>
      <tr><td>Gateway</td><td style="color:var(--o2)">${escapeHTML(net.gateway)}</td></tr>
      <tr><td>DNS</td><td style="color:var(--o2)">${escapeHTML(dns)}</td></tr>
      <tr><td>Hostname</td><td style="color:var(--o2)">${escapeHTML(net.hostname)}</td></tr>
    `;
  }
  // Connected devices
  const devEl = document.getElementById('net-devices');
  if (devEl) {
    if (!devices || !devices.length) {
      devEl.innerHTML = '<tr><td colspan="4" style="color:var(--t3);font-family:var(--mono);font-size:10px">Ingen enheder fundet</td></tr>';
    } else {
      const stateColor = s => s === 'REACHABLE' ? 'var(--ok)' : s === 'STALE' ? 'var(--warn)' : 'var(--t3)';
      devEl.innerHTML = devices.map(d => `<tr>
        <td style="color:var(--o2)">${escapeHTML(d.ip)}</td>
        <td>${escapeHTML(d.hostname)}</td>
        <td style="font-family:var(--mono);font-size:10px;color:var(--t3)">${escapeHTML(d.mac)}</td>
        <td style="color:${stateColor(d.state)};font-family:var(--mono);font-size:9px">${escapeHTML(d.state)}</td>
      </tr>`).join('');
    }
  }
  // Load saved webhook URL
  if (wh?.url) document.getElementById('webhook-url').value = wh.url;
}

async function saveWebhook() {
  const url = document.getElementById('webhook-url').value.trim();
  const r = await fetch(BASE+'/api/webhook/save', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({url})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Gemt' : 'Fejl'), d.ok);
}

async function testWebhook() {
  const url = document.getElementById('webhook-url').value.trim();
  if (!url) { toast('Ingen webhook URL', false); return; }
  toast('Sender test alert...');
  const r = await fetch(BASE+'/api/webhook/test', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({url})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Alert sendt!' : 'Fejl'), d.ok);
}


// ── NAS ──
async function loadNAS() {
  const [n, net] = await Promise.all([api('/api/nas'), api('/api/network')]);
  const ip = net?.ip || window.location.hostname;
  // Pre-fill subnet in modal
  if (ip && ip !== '?') {
    const parts = ip.split('.');
    if (parts.length === 4) document.getElementById('nas-new-subnet').value = `${parts[0]}.${parts[1]}.${parts[2]}.0/24`;
  }
  const sharePath = n?.shares?.length ? n.shares[0].split(' ')[0] : '/mnt/nas-share';
  const winEl = document.getElementById('nas-win-cmd');
  const nfsEl = document.getElementById('nas-nfs-cmd');
  const macEl = document.getElementById('nas-mac-cmd');
  if (winEl) winEl.textContent = `\\\\${ip}\\nas-share`;
  if (nfsEl) nfsEl.textContent = `sudo mount -t nfs ${ip}:${sharePath} /mnt/remote`;
  if (macEl) macEl.textContent = `Cmd+K → nfs://${ip}${sharePath}`;
  if (!n) return;
  document.getElementById('nas-badge').innerHTML = mkbadge(n.status);
  const exportsList = document.getElementById('nas-exports-list');
  if (!n.shares.length) {
    exportsList.innerHTML = `<div class="card" style="border-style:dashed;text-align:center;padding:24px">
      <div style="font-family:var(--display);font-size:16px;letter-spacing:2px;color:var(--t3)">INGEN SHARES KONFIGURERET</div>
      <div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:8px">Klik <b style="color:var(--o)">+ TILFØJ SHARE</b> for at sætte NFS op automatisk.</div>
    </div>`;
  } else {
    exportsList.innerHTML = `<div class="card" style="padding:0;overflow:hidden">
      <table class="tbl" style="width:100%">
        <thead><tr><th>Sti</th><th>Klienter & Options</th><th></th></tr></thead>
        <tbody>${n.shares.map(s => {
          const path = s.split(' ')[0];
          const rest = s.slice(path.length).trim();
          return `<tr>
            <td style="font-family:var(--mono);color:var(--o2)">${escapeHTML(path)}</td>
            <td style="font-family:var(--mono);font-size:10px;color:var(--t3)">${escapeHTML(rest)}</td>
            <td><button class="btn btn-r btn-sm" onclick="nasRemoveShare('${escapeHTML(path)}')">🗑 FJERN</button></td>
          </tr>`;
        }).join('')}</tbody>
      </table>
    </div>`;
  }
  const d = window._lastData?.disks || (await api('/api/disks'));
  if (d) document.getElementById('nas-storage').innerHTML = d.map(dk=>`
    <div class="card" style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between"><span style="font-family:var(--display);letter-spacing:2px">${escapeHTML(dk.mount)}</span><b style="color:var(--o)">${escapeHTML(dk.pct)}%</b></div>
      <div class="bar"><div class="bar-f" style="width:${escapeHTML(dk.pct)}%"></div></div>
      <div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:6px">${escapeHTML(dk.used)}G brugt af ${escapeHTML(dk.total)}G</div>
    </div>`).join('');
}

function openNasSetup() {
  const modal = document.getElementById('nas-setup-modal');
  modal.style.display = 'flex';
  document.getElementById('nas-setup-form').style.display = 'flex';
  document.getElementById('nas-setup-log').style.display = 'none';
  document.getElementById('nas-setup-footer').style.display = 'none';
  document.getElementById('nas-setup-log').innerHTML = '';
}

function closeNasSetup() {
  document.getElementById('nas-setup-modal').style.display = 'none';
}

async function runNasSetup() {
  const path = document.getElementById('nas-new-path').value.trim();
  const subnet = document.getElementById('nas-new-subnet').value.trim();
  const readonly = document.getElementById('nas-readonly').checked;
  const smb_user = document.getElementById('nas-smb-user').value.trim();
  const smb_pass = document.getElementById('nas-smb-pass').value;
  if (!path || !subnet) { toast('Udfyld sti og netværk', false); return; }
  document.getElementById('nas-setup-form').style.display = 'none';
  const log = document.getElementById('nas-setup-log');
  log.style.display = 'block';
  log.innerHTML = '<div style="color:var(--t3)">Konfigurerer NFS...</div>';
  const r = await fetch(BASE+'/api/nas/setup', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({path, subnet, readonly, smb_user, smb_pass})});
  const d = await r.json();
  log.innerHTML = (d.steps || [d.msg || 'Fejl']).map(l =>
    `<div class="${l.startsWith('✓')?'log-ok':l.startsWith('✗')?'log-err':''}">${escapeHTML(l)}</div>`
  ).join('');
  document.getElementById('nas-setup-footer').style.display = 'flex';
  if (d.ok) { toast('NFS share oprettet!'); setTimeout(loadNAS, 500); }
  else toast('NFS setup fejlede', false);
}

async function nasRemoveShare(path) {
  if (!confirm(`Fjern share: ${path}?`)) return;
  const r = await fetch(BASE+'/api/nas/remove', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({path})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Fjernet' : 'Fejl'), d.ok);
  if (d.ok) loadNAS();
}
// nasRestart defined below (async implementation)

// ── RAID ──
async function loadRAID() {
  const r = await api('/api/raid');
  if (!r) return;
  document.getElementById('raid-badge').innerHTML = mkbadge(r.status==='active'?'running':r.status);
  if (!r.info || r.status === 'inactive') {
    document.getElementById('raid-info').innerHTML = '<span style="color:var(--t3)">Ingen RAID array fundet. Tilslut mindst 2 ekstra diske og konfigurér med mdadm.</span>';
    return;
  }
  // Parse mdstat lines into structured display
  const lines = r.info.split('\n');
  let html = '';
  lines.forEach(line => {
    if (line.startsWith('md')) {
      const m = line.match(/^(md\S+)\s*:\s*(\w+)\s+(\w+)\s+(.*)/);
      if (m) {
        const [,dev,state,level,rest] = m;
        const color = state === 'active' ? 'var(--ok)' : 'var(--danger)';
        html += `<div style="margin-bottom:6px"><span style="font-family:var(--display);color:var(--o);letter-spacing:2px">${escapeHTML(dev)}</span>  <span style="font-family:var(--mono);font-size:10px;color:${color}">${escapeHTML(state).toUpperCase()}</span>  <span style="font-family:var(--mono);font-size:10px;color:var(--t3)">${escapeHTML(level)} · ${escapeHTML(rest)}</span></div>`;
      } else {
        html += `<div style="color:var(--t2);font-size:11px">${escapeHTML(line)}</div>`;
      }
    } else if (line.includes('recovery') || line.includes('resync')) {
      html += `<div style="color:var(--warn);font-size:10px;margin-top:4px">⟳ ${escapeHTML(line)}</div>`;
    } else if (line.trim()) {
      html += `<div style="color:var(--t3);font-size:10px">${escapeHTML(line)}</div>`;
    }
  });
  document.getElementById('raid-info').innerHTML = html || '<span style="color:var(--t3)">Ingen aktive arrays.</span>';
}

// ── DOCKER ──
// ── LANGUAGE SYSTEM ──
const LANG = {
  da: {
    'nav.overview':'Overblik','nav.dashboard':'Dashboard','nav.system':'System','nav.network':'Netværk',
    'nav.storage':'Storage','nav.nas':'NAS','nav.raid':'RAID','nav.backup':'Backup & Sync','nav.diskhealth':'Disk Health',
    'nav.services':'Services','nav.docker':'Docker','nav.gameservers':'Game Servers','nav.proxy':'Proxy & SSL','nav.websites':'Websites','nav.privacy':'Privacy Suite',
    'nav.platform':'Platform','nav.files':'Filer','nav.access':'Adgang','nav.settings':'Settings',
    'nav.tools':'Tools','nav.ai':'AI Assistant','nav.devtools':'Dev Tools','nav.marketplace':'Marketplace',
    'ver.tagline':'SELVSTÆNDIG',
    'set.theme':'Theme','set.language':'Sprog','set.background':'Baggrund',
    'docker.notinstalled':'DOCKER IKKE INSTALLERET',
    'docker.notinstalled.desc':'Docker kræves for at køre containers og game servers.',
    'docker.btn.install':'▣ INSTALLER DOCKER NU',
    'docker.installing':'Installerer Docker, vent venligst...',
    'docker.running':'KØRENDE',
    'gs.servername':'Server navn','gs.type':'Type',
    'nav.appstore':'Apps','nav.terminal':'Terminal',
  },
  en: {
    'nav.overview':'Overview','nav.dashboard':'Dashboard','nav.system':'System','nav.network':'Network',
    'nav.storage':'Storage','nav.nas':'NAS','nav.raid':'RAID','nav.backup':'Backup & Sync','nav.diskhealth':'Disk Health',
    'nav.services':'Services','nav.docker':'Docker','nav.gameservers':'Game Servers','nav.proxy':'Proxy & SSL','nav.websites':'Websites','nav.privacy':'Privacy Suite',
    'nav.platform':'Platform','nav.files':'Files','nav.access':'Access','nav.settings':'Settings',
    'nav.tools':'Tools','nav.ai':'AI Assistant','nav.devtools':'Dev Tools','nav.marketplace':'Marketplace',
    'ver.tagline':'STANDALONE',
    'set.theme':'Theme','set.language':'Language','set.background':'Background',
    'docker.notinstalled':'DOCKER NOT INSTALLED',
    'docker.notinstalled.desc':'Docker is required to run containers and game servers.',
    'docker.btn.install':'▣ INSTALL DOCKER NOW',
    'docker.installing':'Installing Docker, please wait...',
    'docker.running':'RUNNING',
    'gs.servername':'Server name','gs.type':'Type',
    'nav.appstore':'Apps','nav.terminal':'Terminal',
  }
};

function applyLanguage(lang) {
  const dict = LANG[lang] || LANG.da;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] !== undefined) el.textContent = dict[key];
  });
  window._currentLang = lang;
}

// ── THEME SYSTEM ──
function applyTheme(theme) {
  const styleId = 'bf-theme-style';
  let el = document.getElementById(styleId);
  if (!el) { el = document.createElement('style'); el.id = styleId; document.head.appendChild(el); }
  const themes = {
    'forge-dark': '',
    'forge-light': `
      :root{--bg:#f0ece6;--s:#e8e2d9;--p:#ddd7cc;--b:#c0b8ad;--b2:#a89f93;
        --t:#1a1208;--t2:#4a3f30;--t3:#8a7a65;--o:#d45a00;--o2:#e07020;--o3:rgba(212,90,0,.1)}
      body::before{background-image:linear-gradient(var(--b) 1px,transparent 1px),linear-gradient(90deg,var(--b) 1px,transparent 1px);opacity:.4}
      #topbar{background:rgba(240,236,230,.96)} #sidebar{background:var(--s)}`,
    'high-contrast': `
      :root{--bg:#000;--s:#0a0a0a;--p:#111;--b:#fff;--b2:#ccc;
        --t:#fff;--t2:#eee;--t3:#aaa;--o:#ff6b1a;--o2:#ff9a3c;--o3:rgba(255,107,26,.15)}
      body::before{opacity:.15}`,
    'cyberpunk': `
      :root{--bg:#0a0014;--s:#10001f;--p:#1a003a;--b:#4b0082;--b2:#7b00d4;
        --t:#f0e0ff;--t2:#cc88ff;--t3:#7733aa;--o:#e040fb;--o2:#ea80fc;--o3:rgba(224,64,251,.12);
        --ok:#00e5ff;--err:#ff1744;--warn:#ffea00}
      #topbar{background:rgba(10,0,20,.97)} #sidebar{background:var(--s)}
      .logo-text{color:#ea80fc} .logo-text b{color:#e040fb}`,
    'ocean': `
      :root{--bg:#040d1a;--s:#071525;--p:#0b2040;--b:#163a6b;--b2:#1e5090;
        --t:#c0deff;--t2:#5599cc;--t3:#1e3a5f;--o:#00bcd4;--o2:#4dd0e1;--o3:rgba(0,188,212,.12);
        --ok:#00e676;--err:#ff1744;--warn:#ffab40}
      #topbar{background:rgba(4,13,26,.97)} #sidebar{background:var(--s)}
      .logo-text{color:#c0deff} .logo-text b{color:#00bcd4}`,
    'matrix': `
      :root{--bg:#000;--s:#000;--p:#001100;--b:#003300;--b2:#005500;
        --t:#00ff41;--t2:#00bb30;--t3:#005500;--o:#00ff41;--o2:#00cc30;--o3:rgba(0,255,65,.1);
        --ok:#00ff41;--err:#ff0000;--warn:#ffff00;
        --mono:'DM Mono',monospace;--display:'DM Mono',monospace;--body:'DM Mono',monospace}
      #topbar{background:#000} #sidebar{background:#000}
      .logo-text,.logo-text b{color:#00ff41}`,
    'military': `
      :root{--bg:#0f110a;--s:#161a0f;--p:#1e2414;--b:#3a4228;--b2:#4e5a34;
        --t:#d4cc99;--t2:#8a8a5a;--t3:#4a4a2a;--o:#8ba446;--o2:#a8c254;--o3:rgba(139,164,70,.12);
        --ok:#6ab04c;--err:#c0392b;--warn:#e67e22}
      #topbar{background:rgba(15,17,10,.97)} #sidebar{background:var(--s)}
      .logo-text{color:#d4cc99} .logo-text b{color:#8ba446}`,
  };
  el.textContent = themes[theme] || '';
  window._currentTheme = theme;
  const sel = document.getElementById('set-theme');
  if (sel) sel.value = theme;
}

// ── MOBILE SIDEBAR ──
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  sb.classList.toggle('sb-open');
}

// ── DOCKER WITH INSTALL BANNER ──
async function loadDocker() {
  const [c, setup] = await Promise.all([api('/api/docker'), api('/api/setup')]);
  const banner = document.getElementById('docker-install-banner');
  if (banner) banner.style.display = (setup && !setup.docker_ok) ? 'block' : 'none';
  const tb = document.getElementById('docker-tbl');
  if (!c||!c.length) { tb.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--t3)">${LANG[window._currentLang||'da']['docker.running']||'Ingen containere kørende'}</td></tr>`; return; }
  tb.innerHTML = c.map(x => {
    const ok = x.status.includes('Up');
    return `<tr>
      <td><b>${x.name}</b></td>
      <td>${x.image}</td>
      <td>${mkbadge(ok?'running':'stopped',x.status,x.status)}</td>
      <td style="color:var(--t3)">—</td>
      <td>
        <button class="btn btn-o btn-sm" onclick="containerAction('${x.name}','start')" style="margin-right:4px">▶</button>
        <button class="btn btn-r btn-sm" onclick="containerAction('${x.name}','stop')">■ STOP</button>
      </td>
    </tr>`;
  }).join('');
}

async function runDockerInstall() {
  const btn = document.getElementById('docker-install-btn');
  const prog = document.getElementById('docker-install-progress');
  if (btn) btn.disabled = true;
  if (prog) prog.style.display = 'block';
  toast('Installerer Docker... Dette kan tage op til 2 minutter.');
  try {
    const r = await fetch(BASE+'/api/setup/docker',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d = await r.json();
    toast(d.msg||'Docker installeret', d.ok);
    if (!d.ok) console.warn('ByteForge Docker install:', d.msg);
    if (d.ok) {
      if (prog) prog.style.display = 'none';
      document.getElementById('docker-install-banner').style.display = 'none';
    }
  } catch(e) {
    toast('Fejl: '+e.message, false);
  }
  if (btn) btn.disabled = false;
  if (prog) prog.style.display = 'none';
}

async function containerAction(name, action) {
  toast((action==='stop'?'Stopper':'Starter') + ' container: ' + name);
  try {
    const r = await fetch(BASE+'/api/docker/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({container:name,action})});
    const d = await r.json();
    toast(d.msg||'Udført', d.ok);
    setTimeout(loadDocker, 1200);
  } catch(e) { toast('Fejl: '+e.message, false); }
}

function stopContainer(name) { containerAction(name, 'stop'); }

async function deployPreset(name) {
  const presetApps = {webdev:['portainer'], monitoring:['grafana'], ai:['ollama'], privacy:['bitwarden','pihole'], media:['jellyfin'], custom:null};
  if (name === 'custom') { toast('Upload din docker-compose.yml via Filer-siden', true); return; }
  const apps = presetApps[name];
  if (!apps) { toast('Preset ikke tilgængeligt endnu', false); return; }
  for (const app of apps) {
    toast('Deployer ' + app + '...');
    try {
      const r = await fetch(BASE+'/api/apps/deploy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app})});
      const d = await r.json();
      toast(d.msg||app+' deployet', d.ok);
    } catch(e) { toast('Fejl ved '+app+': '+e.message, false); }
  }
  setTimeout(loadDocker, 2000);
}

// ── GAME SERVERS ──
function escapeHTML(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function loadGameServers(withLogs=false) {
  const data = await api('/api/game-servers' + (withLogs ? '?logs=1' : ''));
  if (!data) return;
  if (data.types) { window._serverTypes = data.types; renderGamePicker(); }
  const servers = data.servers || [];
  document.getElementById('gs-total').textContent = servers.length;
  document.getElementById('gs-online').textContent = servers.filter(s => s.status === 'running').length;
  document.getElementById('gs-restart').textContent = servers.filter(s => s.auto_restart).length;
  document.getElementById('sb-game-count').textContent = servers.length;
  const list = document.getElementById('game-server-list');
  if (!servers.length) {
    list.innerHTML = `<div class="card" style="padding:32px;text-align:center;border-style:dashed;grid-column:1/-1">
      <div style="font-size:48px;margin-bottom:12px">🎮</div>
      <div style="font-family:var(--display);font-size:20px;letter-spacing:2px;color:var(--t3)">INGEN SERVERE ENDNU</div>
      <div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:8px">Vælg et spil ovenfor og klik DEPLOY</div>
    </div>`;
    return;
  }
  list.innerHTML = servers.map(s => {
    const typeInfo = (window._serverTypes || {})[s.type] || {};
    const cover = typeInfo.cover || '';
    const running = s.status === 'running';
    const statusColor = running ? 'var(--ok)' : 'var(--t3)';
    const coverHTML = cover
      ? `<img class="sc-cover" src="${escapeHTML(cover)}" alt="${escapeHTML(s.name)}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="sc-cover-placeholder" style="display:none;background:linear-gradient(135deg,var(--s),var(--b))">🎮</div>`
      : `<div class="sc-cover-placeholder" style="background:linear-gradient(135deg,var(--s),var(--b))">🎮</div>`;
    return `<div class="server-card">
      ${coverHTML}
      <div class="sc-body">
        <div class="sc-head">
          <div>
            <div class="sc-name">${escapeHTML(s.name)}</div>
            <div class="sc-type">${escapeHTML(s.kind)}</div>
          </div>
          <div style="text-align:right">
            <div style="font-family:var(--mono);font-size:10px;font-weight:700;color:${statusColor}">${running ? '● ONLINE' : '○ OFFLINE'}</div>
            ${s.port ? `<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:2px">:${s.port}</div>` : ''}
          </div>
        </div>
        <div class="sc-stats">
          <div class="sc-stat"><div class="sc-stat-label">CPU Limit</div><div class="sc-stat-val">${escapeHTML(s.cpu_limit)} cores</div></div>
          <div class="sc-stat"><div class="sc-stat-label">RAM Limit</div><div class="sc-stat-val">${escapeHTML(s.memory_limit)}</div></div>
          <div class="sc-stat"><div class="sc-stat-label">CPU Nu</div><div class="sc-stat-val">${running ? escapeHTML(s.stats?.cpu) : '—'}</div></div>
          <div class="sc-stat"><div class="sc-stat-label">RAM Nu</div><div class="sc-stat-val">${running ? escapeHTML(s.stats?.memory) : '—'}</div></div>
        </div>
        <div class="sc-actions">
          <button class="btn btn-o btn-sm" onclick="gameAction('${s.id}','start')" ${running?'disabled':''}>▶ START</button>
          <button class="btn btn-g btn-sm" onclick="gameAction('${s.id}','restart')">⟳</button>
          <button class="btn btn-r btn-sm" onclick="gameAction('${s.id}','stop')" ${!running?'disabled':''}>■ STOP</button>
          <button class="btn btn-g btn-sm" onclick="showServerLog('${s.id}')">📋 LOG</button>
          <button class="btn btn-g btn-sm" onclick="openModsModal('${escapeHTML(s.id)}','${escapeHTML(s.name)}','${escapeHTML(s.kind)}')">🧩 MODS</button>
          <button class="sc-delete" onclick="deleteServer('${s.id}','${escapeHTML(s.name)}')">🗑 SLET</button>
        </div>
      </div>
    </div>`;
  }).join('');
  window._gameServers = servers;
  if (withLogs && servers[0]) showServerLog(servers[0].id);
}

// ── GAME PICKER ──
let _gpCurrentCat = 'All', _gpSelected = null;

function renderGamePicker() {
  const types = window._serverTypes || {};
  const grid = document.getElementById('game-picker-grid');
  if (!grid) return;
  const entries = Object.entries(types).filter(([, v]) => _gpCurrentCat === 'All' || v.category === _gpCurrentCat);
  grid.innerHTML = entries.map(([key, t]) => {
    const sel = _gpSelected === key;
    const cover = t.cover || '';
    return `<div class="game-pick-card ${sel ? 'selected' : ''}" onclick="selectGame('${key}')">
      ${cover
        ? `<img src="${escapeHTML(cover)}" alt="${escapeHTML(t.name)}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="no-img" style="display:none">🎮</div>`
        : `<div class="no-img">🎮</div>`}
      <div class="game-pick-name">${escapeHTML(t.name)}</div>
      <div class="game-pick-cat">${escapeHTML(t.category)}</div>
    </div>`;
  }).join('');
}

function filterGamePicker(cat) {
  _gpCurrentCat = cat;
  document.querySelectorAll('.gpcat-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-gcat') === cat));
  renderGamePicker();
}

function selectGame(key) {
  _gpSelected = key;
  renderGamePicker();
  const t = (window._serverTypes || {})[key];
  if (!t) return;
  const panel = document.getElementById('gs-create-panel');
  document.getElementById('gs-selected-name').textContent = t.name;
  document.getElementById('new-server-type').value = key;
  document.getElementById('new-server-name').value = '';
  document.getElementById('new-server-name').placeholder = `Mit ${t.name} Server...`;
  panel.classList.add('visible');
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function deleteServer(id, name) {
  if (!confirm(`Slet "${name}"? Dette stopper og fjerner containeren.`)) return;
  const r = await fetch(BASE+'/api/game-servers/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Slettet' : 'Fejl'), d.ok);
  if (d.ok) loadGameServers();
}

function updateCoverPreview() {} // no longer used

function showServerLog(id) {
  const s = (window._gameServers || []).find(x => x.id === id);
  if (!s) return;
  document.getElementById('gs-log-title').textContent = s.container;
  document.getElementById('mc-logs').innerHTML = s.logs
    ? s.logs.split('\n').filter(Boolean).map(l => `<div>${escapeHTML(l)}</div>`).join('')
    : '<span style="color:var(--t3)">Ingen logs endnu. Tryk LOGS for at hente nyeste output.</span>';
}

async function gameAction(id, action) {
  const labels = {start:'Starter',stop:'Stopper',restart:'Genstarter'};
  toast((labels[action] || action) + ' server...');
  try {
    const r = await fetch(BASE+'/api/game-servers/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,action})});
    const d = await r.json();
    toast(d.msg || 'Udført', d.ok);
    setTimeout(() => loadGameServers(true), 1500);
  } catch(e) { toast('Kunne ikke nå ByteForge API', false); }
}

async function createGameServer() {
  const body = {
    name: document.getElementById('new-server-name').value || 'ByteForge Server',
    type: document.getElementById('new-server-type').value,
    port: document.getElementById('new-server-port')?.value || '',
    cpu_limit: document.getElementById('new-server-cpu').value || '2',
    memory_limit: document.getElementById('new-server-ram').value || '4g',
    auto_restart: true
  };
  if (!body.type) { toast('Vælg et spil først', false); return; }
  toast(`Deployer ${(window._serverTypes||{})[body.type]?.name || body.type}...`);
  try {
    const r = await fetch(BASE+'/api/game-servers/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d = await r.json();
    toast(d.msg || 'Server oprettet', d.ok);
    if (d.ok) {
      document.getElementById('gs-create-panel')?.classList.remove('visible');
      _gpSelected = null;
    }
    loadGameServers(true);
  } catch(e) { toast('Server kunne ikke oprettes', false); }
}

// ── REVERSE PROXY / SSL ──
async function loadProxy() {
  const data = await api('/api/proxy');
  if (!data) return;
  const status = data.status?.status || 'unknown';
  const running = status === 'running';
  document.getElementById('proxy-status').innerHTML = running ? '<span style="color:var(--ok)">ONLINE</span>' : '<span style="color:var(--warn)">OFFLINE</span>';
  document.getElementById('proxy-status-sub').textContent = `${data.status?.container || 'byteforge-caddy'} · ${status}`;
  document.getElementById('proxy-caddyfile').textContent = data.caddyfile || '-';
  document.getElementById('proxy-nginxfile').textContent = data.nginx_config || '-';

  const targetBox = document.getElementById('proxy-targets');
  const targets = data.targets || [];
  if (!targets.length) {
    targetBox.innerHTML = '<div class="file-row"><strong>No mapped container ports found</strong><span></span><span></span><span></span><span></span></div>';
  } else {
    targetBox.innerHTML = targets.map(t => `
      <div class="file-row">
        <span>▣</span>
        <strong>${escapeHTML(t.name)}</strong>
        <span>${escapeHTML(t.container_port)}</span>
        <span>${escapeHTML(t.host)}:${escapeHTML(t.port)}</span>
        <button class="btn btn-g btn-sm" data-host="${escapeHTML(t.host)}" data-port="${escapeHTML(t.port)}" onclick="selectProxyTarget(this)">USE</button>
      </div>`).join('');
  }

  const hosts = data.hosts || [];
  const out = document.getElementById('proxy-hosts');
  if (!hosts.length) {
    out.innerHTML = '<div class="cs">No proxy hosts yet. Add a domain and apply Caddy to start automatic SSL.</div>';
    return;
  }
  out.innerHTML = `<table class="tbl"><thead><tr><th>Domain</th><th>Target</th><th>SSL</th><th>Status</th><th></th></tr></thead><tbody>
    ${hosts.map(h => `
      <tr>
        <td>${escapeHTML(h.domain)}</td>
        <td>${escapeHTML(h.target_scheme)}://${escapeHTML(h.target_host)}:${escapeHTML(h.target_port)}</td>
        <td>${h.ssl ? '<span class="badge b-ok"><span class="bd"></span>AUTO</span>' : '<span class="badge b-warn"><span class="bd"></span>HTTP</span>'}</td>
        <td>${h.enabled ? '<span class="badge b-ok"><span class="bd"></span>ENABLED</span>' : '<span class="badge b-dim"><span class="bd"></span>DISABLED</span>'}</td>
        <td><button class="btn btn-r btn-sm" onclick="deleteProxyHost('${escapeHTML(h.id)}')">DELETE</button></td>
      </tr>`).join('')}
  </tbody></table>`;
}

function selectProxyTarget(btn) {
  document.getElementById('proxy-target-host').value = btn.getAttribute('data-host') || '127.0.0.1';
  document.getElementById('proxy-target-port').value = btn.getAttribute('data-port') || '';
}

async function createProxyHost() {
  const body = {
    domain: document.getElementById('proxy-domain').value,
    target_scheme: document.getElementById('proxy-scheme').value,
    target_host: document.getElementById('proxy-target-host').value,
    target_port: document.getElementById('proxy-target-port').value,
    tls_email: document.getElementById('proxy-email').value,
    ssl: document.getElementById('proxy-ssl').checked,
    enabled: true
  };
  toast('Saving proxy host...');
  const r = await fetch(BASE+'/api/proxy/hosts/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d = await r.json();
  toast(d.msg || 'Proxy host saved', d.ok);
  if (d.ok) loadProxy();
}

async function deleteProxyHost(id) {
  const r = await fetch(BASE+'/api/proxy/hosts/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  const d = await r.json();
  toast(d.msg || 'Deleted', d.ok);
  loadProxy();
}

async function applyProxy() {
  toast('Applying Caddy proxy...');
  const r = await fetch(BASE+'/api/proxy/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const d = await r.json();
  toast(d.msg || 'Proxy applied', d.ok);
  setTimeout(loadProxy, 1200);
}

async function proxyAction(action) {
  const r = await fetch(BASE+'/api/proxy/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
  const d = await r.json();
  toast(d.msg || 'Proxy updated', d.ok);
  setTimeout(loadProxy, 1000);
}

async function deployNPM() {
  toast('Installing Nginx Proxy Manager...');
  const r = await fetch(BASE+'/api/proxy/npm/deploy',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const d = await r.json();
  toast(d.msg || 'NPM deployed', d.ok);
  setTimeout(loadProxy, 1200);
}

let _filePath = '';
let _showHidden = false;

function _fileResetPath() { _filePath = ''; }

function toggleHidden() {
  _showHidden = !_showHidden;
  const btn = document.getElementById('btn-hidden');
  if (btn) btn.style.color = _showHidden ? 'var(--o)' : '';
  loadFiles();
}

function _fileIcon(name, type) {
  if (type === 'folder') return `<svg width="72" height="60" viewBox="0 0 72 60" fill="none">
    <path d="M4 14C4 10.7 6.7 8 10 8H28L34 15H62C65.3 15 68 17.7 68 21V51C68 54.3 65.3 57 62 57H10C6.7 57 4 54.3 4 51V14Z" fill="#FF7A2A"/>
    <path d="M4 25H68V51C68 54.3 65.3 57 62 57H10C6.7 57 4 54.3 4 51V25Z" fill="#FFAA55"/>
    <rect x="26" y="37" width="20" height="3" rx="1.5" fill="rgba(255,255,255,.45)"/>
  </svg>`;
  const ext = (name.split('.').pop() || '').toLowerCase();
  const types = [
    {exts:['jpg','jpeg','png','gif','webp','svg','bmp','ico','tiff','heic','avif'], color:'#2ECC71', badge:'#1a7a43', label:'IMG'},
    {exts:['mp4','mkv','avi','mov','webm','flv','wmv','m4v','ts'],                  color:'#9B59B6', badge:'#5b2d7a', label:'VID'},
    {exts:['mp3','wav','flac','ogg','m4a','aac','wma','opus'],                      color:'#3498DB', badge:'#1a5c8a', label:'AUD'},
    {exts:['pdf'],                                                                   color:'#E74C3C', badge:'#8a1a1a', label:'PDF'},
    {exts:['doc','docx','odt','rtf'],                                               color:'#2980B9', badge:'#1a4a7a', label:'DOC'},
    {exts:['xls','xlsx','ods','csv'],                                               color:'#27AE60', badge:'#145c30', label:'XLS'},
    {exts:['txt','md','log'],                                                       color:'#95A5A6', badge:'#4a5a5a', label:'TXT'},
    {exts:['py','js','ts','jsx','tsx','html','css','json','sh','bash','bat','ps1','yaml','yml','toml','ini','cfg','conf','php','go','rs','cpp','c','h','java','rb','swift','kt'], color:'#F39C12', badge:'#8a5500', label:'</>'},
    {exts:['zip','tar','gz','bz2','xz','rar','7z','deb','rpm'],                    color:'#7F8C8D', badge:'#3a4a4a', label:'ZIP'},
    {exts:['exe','msi','AppImage','dmg','pkg'],                                     color:'#E74C3C', badge:'#8a1a1a', label:'EXE'},
  ];
  let color = '#555', badge = '#2a2a2a', label = ext.slice(0,4).toUpperCase() || 'FILE';
  for (const t of types) { if (t.exts.includes(ext)) { color = t.color; badge = t.badge; label = t.label; break; } }
  const fs = label === '</>' ? 9 : label.length > 3 ? 8 : 10;
  return `<svg width="58" height="70" viewBox="0 0 58 70" fill="none">
    <path d="M5 3H37L53 19V63C53 65.8 50.8 68 48 68H10C7.2 68 5 65.8 5 63V5C5 3.9 5.9 3 7 3Z" fill="${color}" opacity=".12"/>
    <path d="M5 3H37L53 19V63C53 65.8 50.8 68 48 68H10C7.2 68 5 65.8 5 63V5C5 3.9 5.9 3 7 3Z" stroke="${color}" stroke-width="1.5"/>
    <path d="M37 3L53 19H39C37.9 19 37 18.1 37 17V3Z" fill="${color}" opacity=".4"/>
    <rect x="8" y="44" width="42" height="17" rx="3" fill="${badge}"/>
    <text x="29" y="56.5" font-family="'DM Mono',monospace" font-size="${fs}" fill="${color}" text-anchor="middle" font-weight="700">${label}</text>
  </svg>`;
}

function _formatSize(b) {
  if (!b) return '';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return Math.ceil(b/1024) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}

function _renderBreadcrumb(scope) {
  const bc = document.getElementById('file-breadcrumb');
  if (!bc) return;
  const parts = _filePath ? _filePath.split('/').filter(Boolean) : [];
  let html = `<span class="fb-crumb${!parts.length?' active':''}" onclick="_navToPath('')">${escapeHTML(scope.toUpperCase())}</span>`;
  let built = '';
  for (let i = 0; i < parts.length; i++) {
    built += (built ? '/' : '') + parts[i];
    const p = built, active = i === parts.length - 1;
    html += `<span class="fb-sep">/</span><span class="fb-crumb${active?' active':''}" onclick="_navToPath('${escapeHTML(p)}')">${escapeHTML(parts[i])}</span>`;
  }
  bc.innerHTML = html;
}

function _enterFolder(name) {
  _filePath = _filePath ? _filePath + '/' + name : name;
  loadFiles();
}

function _navToPath(path) {
  _filePath = path;
  loadFiles();
}

async function loadFiles() {
  const scope = document.getElementById('file-scope')?.value || 'public';
  const out = document.getElementById('file-list');
  if (!out) return;
  out.innerHTML = '<div class="file-empty">Indlæser...</div>';
  _renderBreadcrumb(scope);
  const data = await api('/api/files?scope=' + encodeURIComponent(scope) + '&path=' + encodeURIComponent(_filePath) + (_showHidden ? '&hidden=1' : ''));
  if (!data) return;
  const items = [...(data.items || [])].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  if (!items.length) { out.innerHTML = '<div class="file-empty">// TOM MAPPE</div>'; return; }
  out.innerHTML = items.map(item => {
    const enc = encodeURIComponent(item.name);
    const n = escapeHTML(item.name);
    const click = item.type === 'folder'
      ? `_enterFolder('${n}')`
      : `previewFile('${n}')`;
    const meta = item.type === 'file'
      ? _formatSize(item.size)
      : (item.modified ? new Date(item.modified * 1000).toLocaleDateString('da-DK', {day:'2-digit',month:'short'}) : '');
    return `<div class="file-item" onclick="${click}" oncontextmenu="_showCtxMenu(event,'${n}','${item.type}')" title="${n}">
      <button class="file-item-del" onclick="event.stopPropagation();deleteFile('${enc}')" title="Slet">✕</button>
      ${_fileIcon(item.name, item.type)}
      <div class="file-item-name">${n}</div>
      ${meta ? `<div class="file-item-meta">${meta}</div>` : ''}
    </div>`;
  }).join('');
  _initDragDrop();
}

async function deleteFile(name) {
  const scope = document.getElementById('file-scope').value;
  const path = (_filePath ? _filePath + '/' : '') + decodeURIComponent(name);
  const r = await fetch(BASE+'/api/files/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'delete',scope,path})});
  const d = await r.json();
  toast(d.msg || 'Slettet', d.ok);
  loadFiles();
}

async function makeFolder() {
  const name = prompt('Mappenavn:');
  if (!name || !name.trim()) return;
  const scope = document.getElementById('file-scope').value;
  const path = (_filePath ? _filePath + '/' : '') + name.trim();
  const d = await (await fetch(BASE+'/api/files/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'mkdir',scope,path})})).json();
  toast(d.msg || 'Mappe oprettet', d.ok);
  if (d.ok) loadFiles();
}

async function searchFiles() {
  const scope = document.getElementById('file-scope').value;
  const query = document.getElementById('file-query').value.trim();
  if (!query) { loadFiles(); return; }
  const out = document.getElementById('file-list');
  out.innerHTML = '<div class="file-empty">Søger...</div>';
  document.getElementById('file-breadcrumb').innerHTML = `<span class="fb-crumb">Søgeresultater for "${escapeHTML(query)}"</span>`;
  const r = await fetch(BASE+'/api/files/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'search',scope,query})});
  const d = await r.json();
  const matches = d.matches || [];
  if (!matches.length) { out.innerHTML = '<div class="file-empty">// INGEN RESULTATER</div>'; return; }
  out.innerHTML = matches.map(m => {
    const enc = encodeURIComponent(m.name || m.path);
    return `<div class="file-item" title="${escapeHTML(m.path || m.name)}">
      <button class="file-item-del" onclick="event.stopPropagation();deleteFile('${enc}')" title="Slet">✕</button>
      ${_fileIcon(m.name || m.path, m.type)}
      <div class="file-item-name">${escapeHTML(m.path || m.name)}</div>
    </div>`;
  }).join('');
}

async function uploadFile() {
  const input = document.getElementById('file-upload');
  if (!input.files.length) return;
  const scope = document.getElementById('file-scope').value;
  for (const file of input.files) {
    const form = new FormData();
    form.append('scope', scope);
    form.append('path', _filePath);
    form.append('file', file);
    const r = await fetch(BASE+'/api/files/upload',{method:'POST',body:form});
    const d = await r.json();
    toast(d.msg || file.name + ' uploadet', d.ok);
  }
  input.value = '';
  loadFiles();
}

// ── Kontekstmenu ─────────────────────────────────────────────────────────────
let _ctxName = '', _ctxType = '';

function _showCtxMenu(e, name, type) {
  e.preventDefault();
  e.stopPropagation();
  _ctxName = name;
  _ctxType = type;
  document.getElementById('file-ctx')?.remove();
  const isFile = type === 'file';
  const m = document.createElement('div');
  m.className = 'ctx-menu';
  m.id = 'file-ctx';
  m.innerHTML = `
    ${isFile ? `<div class="ctx-item" onclick="_ctxAction('preview')">👁 &nbsp;Forhåndsvis</div>
    <div class="ctx-item" onclick="_ctxAction('download')">⬇ &nbsp;Download</div><div class="ctx-sep"></div>` : ''}
    <div class="ctx-item" onclick="_ctxAction('rename')">✏ &nbsp;Omdøb</div>
    <div class="ctx-sep"></div>
    <div class="ctx-item danger" onclick="_ctxAction('delete')">✕ &nbsp;Slet</div>`;
  m.style.cssText = `left:${Math.min(e.clientX, innerWidth-180)}px;top:${Math.min(e.clientY, innerHeight-160)}px`;
  document.body.appendChild(m);
  setTimeout(() => document.addEventListener('click', () => document.getElementById('file-ctx')?.remove(), {once:true}), 0);
}

function _ctxAction(action) {
  document.getElementById('file-ctx')?.remove();
  const enc = encodeURIComponent(_ctxName);
  if (action === 'preview') previewFile(_ctxName);
  else if (action === 'download') downloadFile(enc);
  else if (action === 'rename') renameFile(_ctxName);
  else if (action === 'delete') deleteFile(enc);
}

// ── Rename ────────────────────────────────────────────────────────────────────
async function renameFile(name) {
  const newName = prompt('Nyt navn:', name);
  if (!newName || newName === name) return;
  const scope = document.getElementById('file-scope').value;
  const path = (_filePath ? _filePath + '/' : '') + name;
  const d = await (await fetch(BASE+'/api/files/action',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'rename',scope,path,new_name:newName})})).json();
  toast(d.msg || 'Omdøbt', d.ok);
  if (d.ok) loadFiles();
}

// ── Preview ───────────────────────────────────────────────────────────────────
function previewFile(name) {
  const scope = document.getElementById('file-scope').value;
  const path = (_filePath ? _filePath + '/' : '') + name;
  const url = BASE + '/api/files/get?scope=' + encodeURIComponent(scope) + '&path=' + encodeURIComponent(path);
  const ext = name.split('.').pop().toLowerCase();
  const IMGS = ['jpg','jpeg','png','gif','webp','svg','bmp','tiff','heic','avif'];
  const VIDS = ['mp4','webm','mov','m4v'];
  const AUDS = ['mp3','wav','ogg','flac','m4a','aac'];
  const TXTS = ['txt','md','log','json','yaml','yml','toml','ini','cfg','conf','html','css','js','ts','jsx','py','sh','bat','ps1','php','go','rs','cpp','c','h','java','rb'];

  let body;
  if (IMGS.includes(ext))      body = `<img src="${url}" alt="${escapeHTML(name)}"/>`;
  else if (VIDS.includes(ext)) body = `<video controls autoplay style="max-width:100%;max-height:65vh"><source src="${url}"></video>`;
  else if (AUDS.includes(ext)) body = `<audio controls autoplay style="width:340px"><source src="${url}"></audio>`;
  else if (TXTS.includes(ext)) body = `<pre id="fpreview-text">Indlæser...</pre>`;
  else                         body = `<div style="padding:40px;color:var(--t2);font-family:var(--mono);text-align:center">Kan ikke forhåndsvise denne filtype.<br/>Brug download-knappen.</div>`;

  const ov = document.createElement('div');
  ov.className = 'fmodal-overlay';
  ov.id = 'file-modal';
  ov.innerHTML = `<div class="fmodal">
    <div class="fmodal-head">
      <div class="fmodal-title">${escapeHTML(name)}</div>
      <button class="btn btn-g btn-sm" onclick="document.getElementById('file-modal').remove()">✕</button>
    </div>
    <div class="fmodal-body">${body}</div>
    <div class="fmodal-foot">
      <button class="btn btn-g btn-sm" onclick="downloadFile('${encodeURIComponent(name)}')">⬇ DOWNLOAD</button>
      <button class="btn btn-g btn-sm" onclick="document.getElementById('file-modal').remove()">LUK</button>
    </div>
  </div>`;
  document.body.appendChild(ov);
  ov.addEventListener('click', e => { if (e.target === ov) ov.remove(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') document.getElementById('file-modal')?.remove(); }, {once:true});

  if (TXTS.includes(ext)) {
    fetch(url).then(r => r.text()).then(t => {
      const el = document.getElementById('fpreview-text');
      if (el) el.textContent = t.length > 100000 ? t.slice(0,100000) + '\n\n[afkortet…]' : t;
    }).catch(() => { const el = document.getElementById('fpreview-text'); if (el) el.textContent = 'Kan ikke indlæse fil.'; });
  }
}

// ── Download ──────────────────────────────────────────────────────────────────
function downloadFile(encodedName) {
  const name = decodeURIComponent(encodedName);
  const scope = document.getElementById('file-scope').value;
  const path = (_filePath ? _filePath + '/' : '') + name;
  const a = document.createElement('a');
  a.href = BASE + '/api/files/get?scope=' + encodeURIComponent(scope) + '&path=' + encodeURIComponent(path);
  a.download = name;
  a.click();
}

// ── Drag-and-drop upload ──────────────────────────────────────────────────────
function _initDragDrop() {
  const grid = document.getElementById('file-list');
  if (!grid || grid._dd) return;
  grid._dd = true;
  grid.addEventListener('dragover', e => { e.preventDefault(); grid.classList.add('drag-over'); });
  grid.addEventListener('dragleave', e => { if (!grid.contains(e.relatedTarget)) grid.classList.remove('drag-over'); });
  grid.addEventListener('drop', async e => {
    e.preventDefault();
    grid.classList.remove('drag-over');
    const files = [...(e.dataTransfer?.files || [])];
    if (!files.length) return;
    const scope = document.getElementById('file-scope').value;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      toast(`Uploader ${i+1}/${files.length}: ${file.name}`, true);
      const form = new FormData();
      form.append('scope', scope);
      form.append('path', _filePath);
      form.append('file', file);
      await fetch(BASE+'/api/files/upload',{method:'POST',body:form});
    }
    toast(`${files.length} fil${files.length>1?'er':''} uploadet`, true);
    loadFiles();
  });
}

async function loadAccess() {
  const data = await api('/api/users');
  const out = document.getElementById('user-list');
  if (!data || !out) return;
  out.innerHTML = data.users.map(u => `<div class="access-row"><strong>${escapeHTML(u.name)}</strong><span>${escapeHTML(u.role)}</span><span>${escapeHTML((u.access || []).join(', '))}</span></div>`).join('');
}

async function loadSettings() {
  const [userData, setup] = await Promise.all([api('/api/users'), api('/api/setup')]);
  if (userData?.settings) {
    const theme = userData.settings.theme || 'forge-dark';
    const lang = userData.settings.language || 'da';
    document.getElementById('set-theme').value = theme;
    document.getElementById('set-language').value = lang;
    applyTheme(theme);
    applyLanguage(lang);
    const bg = userData.settings.background || 'grid';
    document.getElementById('set-background').value = ['grid','none','forge','matrix','nebula'].includes(bg) ? '' : bg;
    applyBackground(bg);
    highlightBgPreset(bg);
  }
  if (setup) {
    document.getElementById('setup-docker').innerHTML = setup.docker_ok
      ? '<span style="color:var(--ok)">✓ Installeret</span>'
      : '<span style="color:var(--warn)">✗ Ikke installeret</span>';
    document.getElementById('setup-service').innerHTML = setup.service_ok
      ? '<span style="color:var(--ok)">✓ Aktiv</span>'
      : '<span style="color:var(--t3)">Ikke installeret</span>';
    document.getElementById('setup-port').textContent = setup.port;
    document.getElementById('setup-basedir').textContent = setup.base_dir;
  }
  updateAuthPanel();
}

function applyBackground(bg) {
  const styleId = 'bf-bg-style';
  let el = document.getElementById(styleId);
  if (!el) { el = document.createElement('style'); el.id = styleId; document.head.appendChild(el); }
  if (bg === 'grid' || !bg) {
    el.textContent = '';
  } else if (bg === 'none') {
    el.textContent = 'body::before{display:none!important}';
  } else if (bg === 'forge') {
    el.textContent = 'body::before{background-image:none!important;background:radial-gradient(ellipse 80% 80% at 50% 50%,rgba(255,107,26,.18) 0%,transparent 70%)!important;opacity:1!important}';
  } else if (bg === 'matrix') {
    el.textContent = 'body{background:linear-gradient(135deg,#001100,#003300)!important}body::before{background-image:linear-gradient(rgba(0,255,0,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,0,.07) 1px,transparent 1px)!important;background-size:30px 30px!important;opacity:1!important}';
  } else if (bg === 'nebula') {
    el.textContent = 'body{background:linear-gradient(135deg,#0d0d2b,#1a0533)!important}body::before{background-image:linear-gradient(rgba(120,60,255,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(120,60,255,.08) 1px,transparent 1px)!important;background-size:30px 30px!important;opacity:1!important}';
  } else {
    el.textContent = `body::before{background-image:none!important;background:url(${JSON.stringify(bg)}) center/cover fixed no-repeat!important;opacity:.25!important}`;
  }
}

function highlightBgPreset(bg) {
  document.querySelectorAll('.bg-preset').forEach(el => el.classList.remove('active'));
  const el = document.getElementById('bgp-' + bg);
  if (el) el.classList.add('active');
}

function setBgPreset(preset) {
  applyBackground(preset);
  highlightBgPreset(preset);
  document.getElementById('set-background').value = '';
  fetch(BASE+'/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({background:preset})});
}

async function uploadBackground() {
  const fileInput = document.getElementById('bg-upload');
  if (!fileInput.files[0]) { toast('Vælg et billede først', false); return; }
  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  toast('Uploader baggrundsbillede...');
  try {
    const r = await fetch(BASE+'/api/background/upload', {method:'POST', body:fd});
    const d = await r.json();
    if (d.ok) { applyBackground(d.url); document.getElementById('set-background').value = d.url; toast('Baggrund opdateret!', true); }
    else { toast(d.msg || 'Upload fejlede', false); }
  } catch(e) { toast('Fejl: '+e.message, false); }
}

async function installService() {
  toast('Installerer ByteForge som service...');
  try {
    const r = await fetch(BASE+'/api/setup/service',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d = await r.json();
    toast(d.msg||'Service installeret', d.ok);
    loadSettings();
  } catch(e) { toast('Fejl: '+e.message, false); }
}

async function installDockerSystem() {
  toast('Installerer Docker... Dette kan tage op til 2 minutter.');
  try {
    const r = await fetch(BASE+'/api/setup/docker',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d = await r.json();
    toast(d.msg||'Docker installeret', d.ok);
    loadSettings();
  } catch(e) { toast('Fejl: '+e.message, false); }
}

async function saveSettings() {
  const urlBg = document.getElementById('set-background').value.trim();
  const activePr = document.querySelector('.bg-preset.active');
  const bg = urlBg || (activePr ? activePr.id.replace('bgp-','') : 'grid');
  const body = {theme:document.getElementById('set-theme').value, language:document.getElementById('set-language').value, background:bg};
  const r = await fetch(BASE+'/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d = await r.json();
  if (d.ok) applyBackground(bg);
  toast(d.ok ? 'Indstillinger gemt' : 'Kunne ikke gemme indstillinger', d.ok);
}

async function loadMC() { loadGameServers(true); }
async function mcAction(action) { gameAction('minecraft-main', action); }

// ── DISK HEALTH ──
async function loadDiskHealth() {
  const out = document.getElementById('smart-cards');
  out.innerHTML = '<div style="font-family:var(--mono);font-size:11px;color:var(--t3)">Henter SMART data...</div>';
  const data = await api('/api/smart');
  if (!data || !data.disks.length) {
    out.innerHTML = '<div class="card"><div class="ct">INGEN DISKE</div><div class="cs">Kunne ikke finde block devices.</div></div>';
    return;
  }
  let warning = '';
  if (!data.available) {
    warning = `<div class="card" style="border-color:var(--warn);margin-bottom:12px">
      <div class="ct">SMARTMONTOOLS MANGLER</div>
      <div class="cs">Installer for fulde SMART data: <span class="sbox" style="display:inline-block;margin-top:4px">sudo apt install smartmontools</span></div>
    </div>`;
  }
  out.innerHTML = warning + `<div class="grid g2">${data.disks.map(d => {
    const healthBadge = d.health === 'passed'
      ? `<span class="badge b-ok" style="margin-left:8px"><span class="bd"></span>HEALTHY</span>`
      : d.health === 'failed'
      ? `<span class="badge b-warn" style="margin-left:8px"><span class="bd"></span>FAILED</span>`
      : `<span class="badge" style="margin-left:8px;border-color:var(--t3)"><span class="bd" style="background:var(--t3)"></span>UNKNOWN</span>`;
    const rows = [
      ['Model',   d.model],
      ['Device',  d.dev],
      ['Størrelse', d.size],
      ['Type',    d.type],
      d.temp != null ? ['Temperatur', `<span style="color:${d.temp>60?'var(--danger)':d.temp>45?'var(--warn)':'var(--ok)'}">${d.temp} °C</span>`] : null,
      d.power_on_hours != null ? ['Power-on', `${d.power_on_hours}h (${Math.round(d.power_on_hours/24)} dage)`] : null,
      d.reallocated != null ? ['Reallocated sektorer', `<span style="color:${d.reallocated>0?'var(--warn)':'var(--ok)'}">${d.reallocated}</span>`] : null,
      d.available_spare != null ? ['Available spare', `${d.available_spare}%`] : null,
      d.pct_used != null ? ['NVMe brugt', `${d.pct_used}%`] : null,
    ].filter(Boolean);
    return `<div class="card">
      <div class="ct">${escapeHTML(d.model)}${healthBadge}</div>
      ${rows.map(([k,v])=>`<div class="smart-row"><span>${escapeHTML(k)}</span><span class="smart-val">${v.includes('<')?v:escapeHTML(v)}</span></div>`).join('')}
    </div>`;
  }).join('')}</div>`;
}

// ── AI ──
const AI_SYSTEM = `Du er ByteForge AI assistant på Admins hjemmeserver. Serveren kører Linux med ByteForge, Docker, NFS NAS, RAID og game servers. Svar på dansk, kort og præcist. Brug teknisk sprog.`;

function onAiEngineChange() {
  const engine = document.getElementById('ai-engine').value;
  const keyRow = document.getElementById('ai-key-row');
  const modelRow = document.getElementById('ai-model-row');
  const ollamaRow = document.getElementById('ai-ollama-row');
  keyRow.style.display = engine === 'ollama' ? 'none' : '';
  modelRow.style.display = engine === 'ollama' ? 'none' : '';
  ollamaRow.style.display = engine === 'ollama' ? '' : 'none';
  if (engine === 'openai') {
    const sel = document.getElementById('ai-model');
    sel.innerHTML = '<option value="gpt-4o">gpt-4o</option><option value="gpt-4o-mini">gpt-4o-mini</option><option value="gpt-3.5-turbo">gpt-3.5-turbo</option>';
  } else {
    const sel = document.getElementById('ai-model');
    sel.innerHTML = '<option value="claude-sonnet-4-6">claude-sonnet-4-6</option><option value="claude-opus-4-7">claude-opus-4-7</option><option value="claude-haiku-4-5-20251001">claude-haiku-4-5</option>';
  }
}

async function sendAI() {
  const inp = document.getElementById('ai-input');
  const msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  appendMsg('user', msg);
  const thinking = appendMsg('bot', '<span class="thinking">⚒ Tænker...</span>');
  const engine = document.getElementById('ai-engine')?.value || 'claude';
  const key = document.getElementById('ai-api-key')?.value.trim() || '';
  try {
    let text = '';
    if (engine === 'claude') {
      const model = document.getElementById('ai-model')?.value || 'claude-sonnet-4-6';
      const resp = await fetch('https://api.anthropic.com/v1/messages', {
        method:'POST',
        headers:{'Content-Type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true'},
        body: JSON.stringify({model, max_tokens:1000, system:AI_SYSTEM, messages:[{role:'user',content:msg}]})
      });
      const data = await resp.json();
      text = data.content?.[0]?.text || data.error?.message || 'Ingen svar';
    } else if (engine === 'openai') {
      const model = document.getElementById('ai-model')?.value || 'gpt-4o';
      const resp = await fetch('https://api.openai.com/v1/chat/completions', {
        method:'POST',
        headers:{'Content-Type':'application/json','Authorization':`Bearer ${key}`},
        body: JSON.stringify({model, max_tokens:1000, messages:[{role:'system',content:AI_SYSTEM},{role:'user',content:msg}]})
      });
      const data = await resp.json();
      text = data.choices?.[0]?.message?.content || data.error?.message || 'Ingen svar';
    } else if (engine === 'ollama') {
      const model = document.getElementById('ai-ollama-model')?.value || 'llama3';
      const resp = await fetch(BASE+'/api/ai/ollama', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({model, prompt: AI_SYSTEM + '\n\nBruger: ' + msg})
      });
      const data = await resp.json();
      text = data.response || data.error || 'Ingen svar fra Ollama';
    }
    thinking.querySelector('.bubble').innerHTML = escapeHTML(text).replace(/\n/g,'<br>');
  } catch(e) {
    thinking.querySelector('.bubble').innerHTML = 'Fejl: ' + escapeHTML(e.message);
  }
  document.getElementById('ai-msgs').scrollTop = 9999;
}

function aiQuick(msg) {
  document.getElementById('ai-input').value = msg;
  sendAI();
}

function appendMsg(role, html) {
  const div = document.createElement('div');
  div.className = 'ai-msg ' + role;
  const uname = (_authUser?.username || _authUser?.name || 'USER').toUpperCase();
  div.innerHTML = `<div class="who">${role==='user'?`👤 ${uname}`:'⚒ BYTEFORGE AI'}</div><div class="bubble">${html}</div>`;
  document.getElementById('ai-msgs').appendChild(div);
  document.getElementById('ai-msgs').scrollTop = 9999;
  return div;
}

// ── DEV TOOLS ──
function formatJSON() {
  const inp = document.getElementById('json-input').value;
  try {
    const pretty = JSON.stringify(JSON.parse(inp), null, 2);
    document.getElementById('json-out').innerHTML = `<span class="t-ok">${pretty.replace(/</g,'&lt;')}</span>`;
  } catch(e) {
    document.getElementById('json-out').innerHTML = `<span class="t-err">❌ ${e.message}</span>`;
  }
}
function clearJSON() { document.getElementById('json-input').value=''; document.getElementById('json-out').innerHTML=''; }

async function testAPI() {
  const method = document.getElementById('api-method').value;
  const url = document.getElementById('api-url').value;
  const body = document.getElementById('api-body').value;
  const out = document.getElementById('api-out');
  if (!url) { out.innerHTML = '<span class="t-err">Ingen URL</span>'; return; }
  out.innerHTML = '<span class="thinking">Sender request...</span>';
  try {
    const opts = {method, headers:{'Content-Type':'application/json'}};
    if (body && method !== 'GET') opts.body = body;
    const r = await fetch(url, opts);
    const txt = await r.text();
    let parsed; try { parsed = JSON.stringify(JSON.parse(txt), null, 2); } catch { parsed = txt; }
    out.innerHTML = `<span class="t-ok">HTTP ${r.status}</span>\n${parsed.replace(/</g,'&lt;')}`;
  } catch(e) {
    out.innerHTML = `<span class="t-err">❌ ${e.message}</span>`;
  }
}

async function loadLog() {
  const src = document.getElementById('log-source').value;
  const out = document.getElementById('log-out');
  const titles = {syslog:'/var/log/syslog', docker:'docker ps', minecraft:'minecraft-server', byteforge:'byteforge service'};
  document.getElementById('log-title').textContent = titles[src] || src;
  out.innerHTML = '<span class="thinking">Henter logs...</span>';
  try {
    let text = '';
    if (src === 'minecraft') {
      const servers = await api('/api/game-servers?logs=1');
      const mc = (servers?.servers || []).find(s => s.type?.startsWith('minecraft'));
      text = mc?.logs || 'Ingen Minecraft server fundet.';
    } else if (src === 'docker') {
      const containers = await api('/api/docker');
      text = (containers || []).map(c => `${c.name.padEnd(30)} ${c.status}`).join('\n') || 'Ingen containers kørende.';
    } else if (src === 'syslog') {
      const r = await fetch(BASE+'/api/terminal/exec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:'journalctl -n 50 --no-pager 2>/dev/null || tail -50 /var/log/syslog 2>/dev/null || echo "Ingen systemlog tilgængelig"'})});
      const d = await r.json();
      text = d.output || '';
    } else if (src === 'byteforge') {
      const r = await fetch(BASE+'/api/terminal/exec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:'journalctl -u byteforge -n 50 --no-pager 2>/dev/null || echo "Byteforge service log ikke tilgængelig"'})});
      const d = await r.json();
      text = d.output || '';
    }
    out.innerHTML = text.split('\n').filter(Boolean).map(l=>`<div>${escapeHTML(l)}</div>`).join('') || '<span style="color:var(--t3)">Ingen log output</span>';
  } catch { out.innerHTML = '<span class="t-err">Fejl ved hentning af logs</span>'; }
}

async function installPrivacy(app) {
  const n = {bitwarden:'Bitwarden',nextcloud:'Nextcloud',pihole:'Pi-hole',wireguard:'WireGuard'};
  toast('Installerer ' + (n[app]||app) + ' via Docker...');
  try {
    const r = await fetch(BASE+'/api/apps/deploy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app})});
    const d = await r.json();
    toast(d.msg||(n[app]||app)+' deployet', d.ok);
  } catch(e) { toast('Fejl: '+e.message, false); }
}

// ── MODS & PLUGINS ──
let _modsServerId = null;
let _modsServerType = null;

function openModsModal(serverId, serverName, serverType) {
  _modsServerId = serverId;
  _modsServerType = serverType;
  document.getElementById('mods-modal-title').textContent = `MODS — ${serverName}`;
  document.getElementById('mods-modal').style.display = 'flex';
  document.getElementById('mods-results').innerHTML = '<div style="font-family:var(--mono);font-size:10px;color:var(--t3)">Søg efter mods ovenfor, eller installér fra URL herunder.</div>';
  document.getElementById('mods-log').style.display = 'none';
  document.getElementById('mods-log').innerHTML = '';
  loadInstalledMods(serverId);
}

function closeModsModal() {
  document.getElementById('mods-modal').style.display = 'none';
}

async function loadInstalledMods(serverId) {
  const el = document.getElementById('mods-installed');
  const data = await api(`/api/game-servers/${encodeURIComponent(serverId)}/mods`);
  if (!data || !data.mods || !data.mods.length) {
    el.innerHTML = '<span style="color:var(--t3)">Ingen mods installeret endnu.</span>';
    return;
  }
  el.innerHTML = data.mods.map(m => `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--b)">
    <span style="color:var(--t2)">${escapeHTML(m)}</span>
    <button class="btn btn-r btn-sm" onclick="deleteMod('${escapeHTML(serverId)}','${escapeHTML(m)}')">🗑</button>
  </div>`).join('');
}

async function searchMods() {
  const q = document.getElementById('mods-search').value.trim();
  if (!q) return;
  const el = document.getElementById('mods-results');
  el.innerHTML = '<div style="font-family:var(--mono);font-size:10px;color:var(--t3)">Søger Modrinth...</div>';
  try {
    const r = await fetch(`https://api.modrinth.com/v2/search?query=${encodeURIComponent(q)}&limit=10&facets=[["project_type:mod"]]`);
    const data = await r.json();
    if (!data.hits || !data.hits.length) { el.innerHTML = '<div style="color:var(--t3);font-family:var(--mono);font-size:10px">Ingen resultater</div>'; return; }
    el.innerHTML = data.hits.map(h => `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--b)">
      <div>
        <div style="font-family:var(--display);font-size:13px;letter-spacing:1px">${escapeHTML(h.title)}</div>
        <div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:2px">${escapeHTML(h.description?.slice(0,80) || '')}...</div>
        <div style="font-family:var(--mono);font-size:9px;color:var(--o2);margin-top:2px">⬇ ${(h.downloads||0).toLocaleString()} downloads</div>
      </div>
      <button class="btn btn-o btn-sm" onclick="installModFromModrinth('${escapeHTML(h.slug)}','${escapeHTML(h.title)}')">⬇ INSTALL</button>
    </div>`).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:var(--err);font-family:var(--mono);font-size:10px">Modrinth fejl: ' + escapeHTML(e.message) + '</div>';
  }
}

async function installModFromModrinth(slug, name) {
  showModLog(`▶ Henter ${name} fra Modrinth...`);
  const r = await fetch(BASE+'/api/game-servers/mods/install', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({server_id: _modsServerId, modrinth_slug: slug})});
  const d = await r.json();
  showModLog(d.ok ? `✓ ${name} installeret` : `✗ ${d.msg}`, !d.ok);
  if (d.ok) loadInstalledMods(_modsServerId);
}

async function installModFromUrl() {
  const url = document.getElementById('mods-url').value.trim();
  if (!url) return;
  showModLog(`▶ Downloader fra ${url}...`);
  const r = await fetch(BASE+'/api/game-servers/mods/install', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({server_id: _modsServerId, url})});
  const d = await r.json();
  showModLog(d.ok ? '✓ Mod installeret' : `✗ ${d.msg}`, !d.ok);
  if (d.ok) { document.getElementById('mods-url').value = ''; loadInstalledMods(_modsServerId); }
}

async function deleteMod(serverId, filename) {
  const r = await fetch(BASE+'/api/game-servers/mods/delete', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({server_id: serverId, filename})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Slettet' : 'Fejl'), d.ok);
  if (d.ok) loadInstalledMods(serverId);
}

function showModLog(msg, isErr=false) {
  const log = document.getElementById('mods-log');
  log.style.display = 'block';
  const div = document.createElement('div');
  div.className = msg.startsWith('✓') ? 'log-ok' : isErr ? 'log-err' : '';
  div.textContent = msg;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function nasRestart() {
  toast('Genstarter NFS server...');
  try {
    const r = await fetch(BASE+'/api/nas/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'restart'})});
    const d = await r.json();
    toast(d.msg||'NFS genstartet', d.ok);
  } catch(e) { toast('Fejl: '+e.message, false); }
}

// ── BACKUP & SYNC ──
async function loadBackup() {
  const data = await api('/api/backup/jobs');
  if (!data) return;
  const jobs = data.jobs || [];
  const rp = data.restore_points || [];

  document.getElementById('bk-total').textContent = jobs.length;
  document.getElementById('bk-dest-path').textContent = data.backup_dir || '—';
  document.getElementById('bk-rp-count').textContent = rp.length;

  const lastRp = rp[0];
  if (lastRp) {
    document.getElementById('bk-last').textContent = lastRp.created
      ? new Date(lastRp.created * 1000).toLocaleString('da-DK', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})
      : '—';
    document.getElementById('bk-last-size').textContent = lastRp.size_mb + ' MB';
  } else {
    document.getElementById('bk-last').textContent = 'Aldrig';
    document.getElementById('bk-last-size').textContent = '';
  }

  const scheduleLabel = {manual:'Manuelt', daily:'Dagligt', weekly:'Ugentligt'};
  const jobsList = document.getElementById('bk-jobs-list');
  if (!jobs.length) {
    jobsList.innerHTML = `<div class="card" style="border-style:dashed;text-align:center;padding:24px">
      <div style="font-family:var(--display);font-size:18px;letter-spacing:2px;color:var(--t3)">INGEN BACKUP JOBS</div>
      <div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:8px">Tilføj et job ovenfor for at komme i gang.</div>
    </div>`;
  } else {
    jobsList.innerHTML = `<div class="card" style="padding:0;overflow:hidden">
      <table class="tbl" style="width:100%">
        <thead><tr><th>Navn</th><th>Kilde</th><th>Interval</th><th>Seneste</th><th>Størrelse</th><th></th></tr></thead>
        <tbody>${jobs.map(j => `<tr>
          <td><b>${escapeHTML(j.name)}</b></td>
          <td style="font-size:10px;color:var(--t3)">${escapeHTML(j.src)}</td>
          <td>${escapeHTML(scheduleLabel[j.schedule] || j.schedule)}</td>
          <td>${j.last_run ? j.last_run.replace('_',' ') : '<span style="color:var(--t3)">Aldrig</span>'}</td>
          <td>${j.last_size_mb ? j.last_size_mb + ' MB' : '—'}</td>
          <td style="white-space:nowrap">
            <button class="btn btn-o btn-sm" onclick="runBackup('${j.id}','${escapeHTML(j.name)}')">▶ KØR</button>
            <button class="btn btn-r btn-sm" style="margin-left:4px" onclick="deleteBackupJob('${j.id}')">🗑</button>
          </td>
        </tr>`).join('')}</tbody>
      </table>
    </div>`;
  }

  const rpList = document.getElementById('bk-restore-list');
  if (!rp.length) {
    rpList.innerHTML = '<div class="card"><div class="cs">Ingen restore points endnu. Kør et backup job for at oprette et.</div></div>';
  } else {
    rpList.innerHTML = `<div class="card" style="padding:0;overflow:hidden">
      <table class="tbl">
        <thead><tr><th>Fil</th><th>Job</th><th>Oprettet</th><th>Størrelse</th><th></th></tr></thead>
        <tbody>${rp.map(p => `<tr>
          <td style="font-size:10px">${escapeHTML(p.name)}</td>
          <td>${escapeHTML(p.job)}</td>
          <td>${new Date(p.created*1000).toLocaleString('da-DK',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}</td>
          <td>${p.size_mb} MB</td>
          <td><button class="btn btn-g btn-sm" onclick="restoreBackup('${escapeHTML(p.path)}')">⟳ GENDAN</button></td>
        </tr>`).join('')}</tbody>
      </table>
    </div>`;
  }
}

async function addBackupJob() {
  const name = document.getElementById('bk-new-name').value.trim();
  const src = document.getElementById('bk-new-src').value.trim();
  const schedule = document.getElementById('bk-new-schedule').value;
  if (!name || !src) { toast('Udfyld navn og kildesti', false); return; }
  const r = await fetch(BASE+'/api/backup/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,src,schedule})});
  const d = await r.json();
  if (d.ok) {
    document.getElementById('bk-new-name').value = '';
    document.getElementById('bk-new-src').value = '';
    toast('Job tilføjet');
    loadBackup();
  } else toast(d.msg||'Fejl', false);
}

async function runBackup(jobId, jobName) {
  const td = document.getElementById('bk-td');
  const out = document.getElementById('bk-output');
  const title = document.getElementById('bk-log-title');
  if (td) td.classList.add('on');
  if (title) title.textContent = jobName || jobId;
  if (out) out.innerHTML = '<span class="thinking">Kører backup med rsync/tar... vent venligst.</span>';
  try {
    const r = await fetch(BASE+'/api/backup/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:jobId})});
    const d = await r.json();
    if (td) td.classList.remove('on');
    if (out) out.innerHTML = `<div style="color:${d.ok?'var(--ok)':'var(--err)'}">${escapeHTML(d.msg||'Udført')}</div>`;
    toast(d.msg || (d.ok ? 'Backup fuldført' : 'Backup fejlede'), d.ok);
    loadBackup();
  } catch(e) {
    if (td) td.classList.remove('on');
    if (out) out.innerHTML = `<div style="color:var(--err)">${escapeHTML(e.message)}</div>`;
    toast('Fejl: '+e.message, false);
  }
}

async function deleteBackupJob(id) {
  if (!confirm('Slet dette backup job?')) return;
  const r = await fetch(BASE+'/api/backup/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  const d = await r.json();
  toast(d.ok ? 'Job slettet' : 'Fejl', d.ok);
  if (d.ok) loadBackup();
}

async function restoreBackup(path) {
  const dest = prompt('Gendan til mappe:', '/tmp/byteforge-restore');
  if (!dest) return;
  toast('Gendanner backup...');
  const r = await fetch(BASE+'/api/backup/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,dest})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Gendannet' : 'Fejl'), d.ok);
}

// ── REAL-TIME GRAPHS ──
const _graphData = {cpu:[], ram:[], rx:[], tx:[]};

function drawGraph(canvasId, data, color, maxValue=100) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width) return;
  canvas.width = rect.width * dpr;
  canvas.height = 80 * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = rect.width, H = 80;
  ctx.clearRect(0, 0, W, H);
  // grid
  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--b').trim() || '#242424';
  ctx.lineWidth = 1;
  [0.25, 0.5, 0.75].forEach(f => { ctx.beginPath(); ctx.moveTo(0, H*f); ctx.lineTo(W, H*f); ctx.stroke(); });
  if (data.length < 2) return;
  const step = W / (data.length - 1);
  const max = Math.max(maxValue, ...data, 1);
  // fill
  ctx.beginPath();
  data.forEach((v, i) => { const x = i*step, y = H - Math.min(v, max)/max*H; i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y); });
  ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
  ctx.fillStyle = color + '28'; ctx.fill();
  // line
  ctx.beginPath();
  data.forEach((v, i) => { const x = i*step, y = H - Math.min(v, max)/max*H; i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y); });
  ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke();
}

function formatRate(bytes) {
  const value = Number(bytes || 0);
  if (value >= 1024 * 1024) return (value / 1024 / 1024).toFixed(1) + ' MB/s';
  if (value >= 1024) return Math.round(value / 1024) + ' KB/s';
  return value + ' B/s';
}

async function updateGraphs() {
  const h = await api('/api/metrics/history');
  if (!h || !h.length) return;
  _graphData.cpu = h.map(p => p.cpu);
  _graphData.ram = h.map(p => p.ram);
  _graphData.rx = h.map(p => p.rx_bps || 0);
  _graphData.tx = h.map(p => p.tx_bps || 0);
  drawGraph('graph-cpu', _graphData.cpu, '#FF6B1A');
  drawGraph('graph-ram', _graphData.ram, '#FF9A3C');
  drawGraph('graph-net-rx', _graphData.rx, '#39D353', Math.max(..._graphData.rx, 1024));
  drawGraph('graph-net-tx', _graphData.tx, '#FFB020', Math.max(..._graphData.tx, 1024));
  const latest = h[h.length - 1] || {};
  const rxEl = document.getElementById('net-rx-now');
  const txEl = document.getElementById('net-tx-now');
  if (rxEl) rxEl.innerHTML = formatRate(latest.rx_bps).replace(' ', ' <span class="u">') + '</span>';
  if (txEl) txEl.innerHTML = formatRate(latest.tx_bps).replace(' ', ' <span class="u">') + '</span>';
}

// ── NOTIFICATIONS ──
let _notifs = [];

function toggleNotif() {
  const d = document.getElementById('notif-drop');
  d.style.display = d.style.display === 'block' ? 'none' : 'block';
}
document.addEventListener('click', e => {
  if (!e.target.closest('.notif-wrap')) document.getElementById('notif-drop').style.display = 'none';
});

function checkNotifications(sysData) {
  if (!sysData) return;
  _notifs = [];
  if (sysData.cpu > 90) _notifs.push({type:'err', msg:`CPU kritisk høj: ${sysData.cpu}%`});
  else if (sysData.cpu > 75) _notifs.push({type:'warn', msg:`CPU høj: ${sysData.cpu}%`});
  if (sysData.ram_pct > 90) _notifs.push({type:'err', msg:`RAM kritisk høj: ${sysData.ram_pct}%`});
  else if (sysData.ram_pct > 80) _notifs.push({type:'warn', msg:`RAM høj: ${sysData.ram_pct}%`});
  const badge = document.getElementById('notif-badge');
  const list = document.getElementById('notif-list');
  if (_notifs.length) {
    badge.style.display = 'flex'; badge.textContent = _notifs.length;
    list.innerHTML = _notifs.map(n => `<div class="notif-item ${n.type}"><span>${n.type==='err'?'🔴':'🟡'}</span><span>${escapeHTML(n.msg)}</span></div>`).join('');
  } else {
    badge.style.display = 'none';
    list.innerHTML = '<div class="notif-empty">Ingen alerts</div>';
  }
}

// ── APPS ──
let _allApps = [], _currentCat = 'All', _currentAppsTab = 'installed';

async function loadApps() {
  switchAppsTab('installed');
  const installedGrid = document.getElementById('apps-installed-grid');
  const storeGrid = document.getElementById('app-store-grid');
  if (installedGrid) installedGrid.innerHTML = '<div class="card"><div class="ct">INDLÆSER</div><div class="cs">Henter apps...</div></div>';
  if (storeGrid) storeGrid.innerHTML = '<div class="card"><div class="ct">INDLÆSER</div><div class="cs">Henter app catalog...</div></div>';
  const apps = await api('/api/appstore');
  if (!apps) {
    if (installedGrid) installedGrid.innerHTML = '<div class="card"><div class="ct">FEJL</div><div class="cs">Kunne ikke hente apps</div></div>';
    if (storeGrid) storeGrid.innerHTML = '<div class="card"><div class="ct">FEJL</div><div class="cs">Kunne ikke hente app catalog</div></div>';
    return;
  }
  _allApps = apps;
  renderInstalledApps(apps.filter(a => a.installed));
  renderApps(apps);
}

function switchAppsTab(tab) {
  _currentAppsTab = tab;
  document.getElementById('apps-installed-section').style.display = tab === 'installed' ? '' : 'none';
  document.getElementById('apps-store-section').style.display = tab === 'store' ? '' : 'none';
  document.getElementById('tab-installed').classList.toggle('active', tab === 'installed');
  document.getElementById('tab-store').classList.toggle('active', tab === 'store');
}

function appOpenUrl(a) {
  return a.webport ? `http://${window.location.hostname}:${a.webport}` : '';
}

function renderInstalledApps(apps) {
  const grid = document.getElementById('apps-installed-grid');
  if (!grid) return;
  if (!apps.length) {
    grid.innerHTML = `<div class="card" style="grid-column:1/-1">
      <div class="ct">INGEN APPS INSTALLERET</div>
      <div class="cs">Gå til <button class="btn btn-o btn-sm" style="display:inline-flex;margin-left:6px" onclick="switchAppsTab('store')">🛒 STORE</button> for at installere din første app.</div>
    </div>`;
    return;
  }
  grid.innerHTML = apps.map(a => {
    const running = a.status === 'running';
    const url = appOpenUrl(a);
    const statusColor = running ? 'var(--ok)' : 'var(--warn)';
    const statusLabel = running ? '● KØRENDE' : '○ STOPPET';
    const openBtn = url ? `<a class="btn btn-o app-tile-open" href="${url}" target="_blank" rel="noopener">↗ ÅBEN APP</a>` : '';
    return `<div class="app-tile" id="apptile-${escapeHTML(a.id)}">
      <div class="app-tile-icon">${escapeHTML(a.icon)}</div>
      <div class="app-tile-name">${escapeHTML(a.name)}</div>
      <div class="app-tile-status" style="color:${statusColor}">${statusLabel}</div>
      ${openBtn}
      <div class="app-tile-actions">
        <button class="btn btn-g btn-sm" onclick="appAction('${escapeHTML(a.id)}','${running?'stop':'start'}')">${running?'■ STOP':'▶ START'}</button>
        <button class="btn btn-r btn-sm" onclick="appUninstall('${escapeHTML(a.id)}')">🗑 FJERN</button>
      </div>
    </div>`;
  }).join('');
}

function filterApps(cat) {
  if (cat !== undefined) _currentCat = cat;
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-cat') === _currentCat));
  const q = (document.getElementById('store-search')?.value || '').toLowerCase();
  let apps = _allApps;
  if (_currentCat !== 'All') apps = apps.filter(a => a.category === _currentCat);
  if (q) apps = apps.filter(a => a.name.toLowerCase().includes(q) || a.desc.toLowerCase().includes(q));
  renderApps(apps);
}

function renderApps(apps) {
  const grid = document.getElementById('app-store-grid');
  if (!grid) return;
  if (!apps.length) { grid.innerHTML = '<div class="card"><div class="ct">INGEN RESULTATER</div><div class="cs">Prøv et andet søgeord eller kategori.</div></div>'; return; }
  grid.innerHTML = apps.map(a => {
    const installed = a.installed;
    const installing = a.status === 'installing';
    const running = a.status === 'running';
    const url = appOpenUrl(a);
    let statusHtml, btnHtml;
    if (installing) {
      statusHtml = `<span class="app-status" style="color:var(--o)">⟳ INSTALLERER...</span>`;
      btnHtml = `<button class="btn btn-g btn-sm" disabled>⟳ WAIT</button>`;
    } else if (installed) {
      statusHtml = `<span class="app-status" style="color:${running?'var(--ok)':'var(--warn)'}">${running?'● KØRENDE':'○ STOPPET'}</span>`;
      const openBtn = url ? `<a class="btn btn-o btn-sm" href="${url}" target="_blank" rel="noopener">↗ ÅBEN</a>` : '';
      btnHtml = `<div style="display:flex;gap:5px;flex-wrap:wrap">
        ${openBtn}
        <button class="btn btn-g btn-sm" onclick="appAction('${escapeHTML(a.id)}','${running?'stop':'start'}')">${running?'■ STOP':'▶ START'}</button>
        <button class="btn btn-r btn-sm" onclick="appUninstall('${escapeHTML(a.id)}')">🗑</button>
      </div>`;
    } else {
      statusHtml = `<span class="app-status" style="color:var(--t3)">○ IKKE INSTALLERET</span>`;
      btnHtml = `<button class="btn btn-o btn-sm" onclick="appInstall('${escapeHTML(a.id)}')">⚡ INSTALL</button>`;
    }
    return `<div class="app-card ${installed?'installed':''} ${installing?'installing':''}" id="appcard-${escapeHTML(a.id)}">
      <div class="app-icon">${escapeHTML(a.icon)}</div>
      <div>
        <div class="app-name">${escapeHTML(a.name)}</div>
        <div class="app-cat">${escapeHTML(a.category)}</div>
      </div>
      <div class="app-desc">${escapeHTML(a.desc)}</div>
      <div class="app-footer">${statusHtml}${btnHtml}</div>
    </div>`;
  }).join('');
}

// ── Install modal ──
let _installPollTimer = null;
let _installSeenLines = 0;

async function appInstall(id) {
  const app = _allApps.find(a => a.id === id);
  const name = app?.name || id;
  // Show modal
  document.getElementById('install-modal').style.display = 'flex';
  document.getElementById('install-modal-title').textContent = `INSTALLING  ${name}`;
  document.getElementById('install-log').innerHTML = '';
  document.getElementById('install-footer').style.display = 'none';
  document.getElementById('install-open-btn').style.display = 'none';
  _installSeenLines = 0;
  // Start install
  const r = await fetch(BASE+'/api/appstore/install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app:id})});
  const d = await r.json();
  if (!d.ok) {
    appendInstallLog(d.msg || 'Fejl', true);
    document.getElementById('install-footer').style.display = 'flex';
    return;
  }
  // Poll logs
  _installPollTimer = setInterval(() => pollInstallLogs(id, app), 600);
}

async function pollInstallLogs(id, app) {
  const data = await api(`/api/appstore/logs?app=${encodeURIComponent(id)}`);
  if (!data) return;
  const newLines = data.lines.slice(_installSeenLines);
  _installSeenLines = data.lines.length;
  newLines.forEach(l => appendInstallLog(l));
  if (data.done) {
    clearInterval(_installPollTimer);
    _installPollTimer = null;
    document.getElementById('install-footer').style.display = 'flex';
    if (data.ok && app?.port) {
      const openBtn = document.getElementById('install-open-btn');
      openBtn.href = appOpenUrl(app);
      openBtn.style.display = 'flex';
    }
    setTimeout(loadApps, 800);
  }
}

function appendInstallLog(line) {
  const log = document.getElementById('install-log');
  const span = document.createElement('div');
  span.className = line.startsWith('✓') ? 'log-ok' : line.startsWith('✗') ? 'log-err' : '';
  span.textContent = line;
  log.appendChild(span);
  log.scrollTop = log.scrollHeight;
}

function closeInstallModal() {
  if (_installPollTimer) { clearInterval(_installPollTimer); _installPollTimer = null; }
  document.getElementById('install-modal').style.display = 'none';
}

async function appUninstall(id) {
  const app = _allApps.find(a => a.id === id);
  toast(`Afinstallerer ${app?.name || id}...`);
  const r = await fetch(BASE+'/api/appstore/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app:id})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Afinstalleret' : 'Fejl'), d.ok);
  if (d.ok) setTimeout(loadApps, 800);
}

async function appAction(id, action) {
  const r = await fetch(BASE+'/api/docker/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({container:`byteforge-${id}`,action})});
  const d = await r.json();
  toast(d.msg||'Udført', d.ok);
  setTimeout(loadApps, 800);
}

// ── WEB TERMINAL ──
let _termHistory = [], _termHistoryIdx = -1;

async function initTerminal() {
  const out = document.getElementById('term-output');
  document.getElementById('term-input')?.focus();
  if (out._loaded) return;
  out._loaded = true;
  out.innerHTML = '';

  // Header banner
  const banner = [
    '╔══════════════════════════════════════════════════╗',
    '║          BYTEFORGE WEB TERMINAL                  ║',
    '║  Kør kommandoer direkte på serveren              ║',
    '╚══════════════════════════════════════════════════╝',
  ];
  banner.forEach(l => appendTermLine(l, 'color:var(--o)'));
  appendTermLine('', '');

  // Fetch system info
  const hw = await api('/api/hardware');
  const sys = await api('/api/system');
  if (hw) {
    const osLine = hw.platform === 'Linux'
      ? `OS       : ${hw.os_name}${hw.kernel ? ` (${hw.kernel})` : ''}`
      : hw.platform === 'Darwin'
      ? `OS       : ${hw.os_name}`
      : `OS       : ${hw.os_name}`;
    const lines = [
      osLine,
      `Platform : ${hw.platform}`,
      `Hostname : ${hw.hostname}`,
      `CPU      : ${hw.cpu_model} (${hw.cpu_cores} tråde)`,
      `GPU      : ${hw.gpu}`,
    ];
    if (sys) {
      lines.push(`RAM      : ${sys.ram_used_mb} MB / ${sys.ram_total_mb} MB (${sys.ram_pct}%)`);
      lines.push(`CPU Load : ${sys.cpu}%`);
      lines.push(`Uptime   : ${sys.uptime}`);
    }
    lines.forEach(l => appendTermLine(l, 'color:var(--t2)'));
  }
  appendTermLine('', '');
  appendTermLine('Skriv en kommando og tryk Enter. Pil op/ned = historik.', 'color:var(--t3)');
  appendTermLine('─'.repeat(52), 'color:var(--b2)');
}

async function handleTermKey(e) {
  const input = e.target;
  if (e.key === 'Enter') {
    const cmd = input.value.trim();
    if (!cmd) return;
    _termHistory.unshift(cmd); _termHistoryIdx = -1;
    input.value = '';
    appendTermLine(`$ ${cmd}`, 'color:var(--o)');
    try {
      const r = await fetch(BASE+'/api/terminal/exec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd})});
      const d = await r.json();
      const lines = (d.output || '').split('\n');
      lines.forEach(l => appendTermLine(l, d.ok ? '' : 'color:var(--err)'));
    } catch(err) {
      appendTermLine('Fejl: ' + err.message, 'color:var(--err)');
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    _termHistoryIdx = Math.min(_termHistoryIdx + 1, _termHistory.length - 1);
    input.value = _termHistory[_termHistoryIdx] || '';
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    _termHistoryIdx = Math.max(_termHistoryIdx - 1, -1);
    input.value = _termHistoryIdx >= 0 ? _termHistory[_termHistoryIdx] : '';
  }
}

function appendTermLine(text, style='') {
  const out = document.getElementById('term-output');
  const div = document.createElement('div');
  div.className = 'term-out-line';
  if (style) div.style.cssText = style;
  div.textContent = text;
  out.appendChild(div);
  out.scrollTop = out.scrollHeight;
}

function quickCmd(cmd) {
  const input = document.getElementById('term-input');
  if (input) { input.value = cmd; handleTermKey({key:'Enter', target:input, preventDefault:()=>{}}); }
}

function clearTerm() {
  const out = document.getElementById('term-output');
  out._loaded = false;
  out.innerHTML = '';
  initTerminal();
}

// ── INIT ──
let _tickerTimer = null;

async function startApp() {
  if (_tickerTimer) clearInterval(_tickerTimer);
  await updateTicker();
  _tickerTimer = setInterval(updateTicker, 15000);
  loadSystem();
  api('/api/users').then(d => {
    if (!d?.settings) return;
    applyTheme(d.settings.theme || 'forge-dark');
    applyLanguage(d.settings.language || 'da');
    if (d.settings.background) applyBackground(d.settings.background);
  });
  api('/api/game-servers').then(d => { if (d?.types) { window._serverTypes = d.types; renderGamePicker(); } });
  updateAuthPanel();
}

async function boot() {
  const d = await authStatus();
  if (d.setup_required) {
    showLogin('Create the ADMIN password to finish ByteForge setup.', true);
    return;
  }
  if (!d.authenticated) {
    showLogin();
    return;
  }
  _authUser = d.user;
  hideLogin();
  startApp();
}

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.getElementById('login-screen') && !document.getElementById('login-screen').classList.contains('hidden')) {
    login();
  }
});

// ══════════════════════════════════════════════════════════
// FORGEUI STUDIO
// ══════════════════════════════════════════════════════════
const DISPLAY_FONTS = [
  {name:'Bebas Neue', css:"'Bebas Neue',sans-serif", label:'BEBAS NEUE'},
  {name:'Orbitron', css:"'Orbitron',sans-serif", label:'ORBITRON'},
  {name:'Rajdhani', css:"'Rajdhani',sans-serif", label:'RAJDHANI'},
  {name:'Russo One', css:"'Russo One',sans-serif", label:'RUSSO ONE'},
];
const MONO_FONTS = [
  {name:'DM Mono', css:"'DM Mono',monospace", label:'DM MONO'},
  {name:'JetBrains Mono', css:"'JetBrains Mono',monospace", label:'JETBRAINS'},
  {name:'Space Mono', css:"'Space Mono',monospace", label:'SPACE MONO'},
  {name:'Share Tech Mono', css:"'Share Tech Mono',monospace", label:'SHARE TECH'},
];
let _studioState = {};

function loadStudio() {
  buildFontPicker('studio-fonts-display', DISPLAY_FONTS, 'displayFont', '--display');
  buildFontPicker('studio-fonts-mono', MONO_FONTS, 'monoFont', '--mono');
  loadStudioState();
}

function buildFontPicker(containerId, fonts, stateKey, cssVar) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const currentFont = getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim();
  // Load Google Fonts
  fonts.forEach(f => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(f.name.replace(/ /g,'+'))}&display=swap`;
    document.head.appendChild(link);
  });
  el.innerHTML = fonts.map(f => `
    <div class="studio-font-card ${currentFont.includes(f.name)?'active':''}" onclick="studioSetFont('${cssVar}','${f.css}','${containerId}',this)">
      <div style="font-family:${f.css};font-size:20px;letter-spacing:2px;color:var(--t)">${f.label}</div>
      <div class="studio-font-card-name">${f.name}</div>
    </div>`).join('');
}

function studioSetFont(cssVar, fontCss, containerId, el) {
  document.documentElement.style.setProperty(cssVar, fontCss);
  document.querySelectorAll(`#${containerId} .studio-font-card`).forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

function studioTab(tab) {
  document.querySelectorAll('.studio-nav-item').forEach(n => n.classList.toggle('active', n.dataset.tab === tab));
  document.querySelectorAll('.studio-tab').forEach(t => t.classList.toggle('active', t.id === `studio-tab-${tab}`));
}

function studioApplyPreset(theme) {
  applyTheme(theme);
  document.querySelectorAll('.studio-preset').forEach(p => p.classList.toggle('active', p.dataset.theme === theme));
  document.getElementById('spv-theme-name').textContent = theme.replace(/-/g,' ').toUpperCase();
}

function studioSetAccent(primary, secondary) {
  document.documentElement.style.setProperty('--o', primary);
  document.documentElement.style.setProperty('--o2', secondary);
  document.documentElement.style.setProperty('--o3', primary + '1f');
  const p = document.getElementById('studio-accent-picker');
  const p2 = document.getElementById('studio-accent2-picker');
  if (p) p.value = primary;
  if (p2) p2.value = secondary;
}

function studioSetAccentFromPicker(val) {
  studioSetAccent(val, val + 'aa');
}

function studioSetVar(cssVar, val) {
  document.documentElement.style.setProperty(cssVar, val);
}

function studioSetEffect(type, val) {
  val = parseFloat(val);
  const root = document.documentElement;
  switch(type) {
    case 'glow':
      root.style.setProperty('--glow', val);
      document.getElementById('sv-glow').textContent = val;
      document.body.classList.toggle('studio-glow', val > 0);
      break;
    case 'blur':
      root.style.setProperty('--blur', val+'px');
      document.getElementById('sv-blur').textContent = val+'px';
      document.body.classList.toggle('studio-blur', val > 0);
      break;
    case 'radius':
      root.style.setProperty('--radius', val+'px');
      document.getElementById('sv-radius').textContent = val+'px';
      document.body.classList.toggle('studio-radius', val > 0);
      break;
    case 'opacity':
      root.style.setProperty('--card-alpha', val/100);
      document.getElementById('sv-opacity').textContent = val+'%';
      break;
    case 'border':
      document.getElementById('sv-border').textContent = val > 1.5 ? 'bright' : val < 0.5 ? 'dim' : 'normal';
      document.querySelectorAll('.card').forEach(c => c.style.borderColor = val > 0 ? '' : 'transparent');
      break;
    case 'spacing':
      root.style.setProperty('--ls', val+'px');
      document.getElementById('sv-spacing').textContent = val+'px';
      break;
    case 'scale':
      root.style.fontSize = (val/100 * 16) + 'px';
      document.getElementById('sv-scale').textContent = val+'%';
      break;
  }
}

function studioToggle(type, on) {
  switch(type) {
    case 'animations': document.body.classList.toggle('studio-no-anim', !on); break;
    case 'grid': document.body.classList.toggle('no-grid', !on); break;
    case 'scanlines': document.body.classList.toggle('studio-scanlines', on); break;
    case 'compact': document.body.classList.toggle('studio-compact', on); break;
    case 'wide': document.getElementById('sidebar').style.width = on ? '260px' : ''; break;
    case 'ticker': document.getElementById('sys-ticker').style.display = on ? '' : 'none'; break;
  }
}

function loadStudioState() {
  const saved = localStorage.getItem('byteforge-studio');
  if (!saved) return;
  try {
    const s = JSON.parse(saved);
    if (s.theme) { applyTheme(s.theme); const sel = document.getElementById('set-theme'); if(sel) sel.value = s.theme; }
    if (s.accent) studioSetAccent(s.accent, s.accent2 || s.accent);
    if (s.glow) { document.getElementById('sl-glow').value = s.glow; studioSetEffect('glow', s.glow); }
    if (s.blur) { document.getElementById('sl-blur').value = s.blur; studioSetEffect('blur', s.blur); }
    if (s.radius) { document.getElementById('sl-radius').value = s.radius; studioSetEffect('radius', s.radius); }
    if (s.opacity) { document.getElementById('sl-opacity').value = s.opacity; studioSetEffect('opacity', s.opacity); }
    if (s.scale) { document.getElementById('sl-scale').value = s.scale; studioSetEffect('scale', s.scale); }
  } catch(e) {}
}

function studioSave() {
  const state = {
    theme: window._currentTheme || 'forge-dark',
    accent: getComputedStyle(document.documentElement).getPropertyValue('--o').trim(),
    accent2: getComputedStyle(document.documentElement).getPropertyValue('--o2').trim(),
    glow: document.getElementById('sl-glow')?.value,
    blur: document.getElementById('sl-blur')?.value,
    radius: document.getElementById('sl-radius')?.value,
    opacity: document.getElementById('sl-opacity')?.value,
    scale: document.getElementById('sl-scale')?.value,
  };
  localStorage.setItem('byteforge-studio', JSON.stringify(state));
  toast('Studio design gemt!');
}

function studioReset() {
  localStorage.removeItem('byteforge-studio');
  applyTheme('forge-dark');
  ['glow','blur','radius','spacing'].forEach(t => { const sl = document.getElementById('sl-'+t); if(sl){sl.value=0;studioSetEffect(t,0);} });
  ['opacity'].forEach(t => { const sl = document.getElementById('sl-'+t); if(sl){sl.value=100;studioSetEffect(t,100);} });
  ['scale'].forEach(t => { const sl = document.getElementById('sl-'+t); if(sl){sl.value=100;studioSetEffect(t,100);} });
  document.documentElement.removeAttribute('style');
  document.body.className = document.body.className.replace(/studio-\S+/g,'').trim();
  toast('Design nulstillet');
}

function studioExport() {
  const css = `:root{--o:${getComputedStyle(document.documentElement).getPropertyValue('--o').trim()};--o2:${getComputedStyle(document.documentElement).getPropertyValue('--o2').trim()};--radius:${getComputedStyle(document.documentElement).getPropertyValue('--radius').trim()};--blur:${getComputedStyle(document.documentElement).getPropertyValue('--blur').trim()};--glow:${getComputedStyle(document.documentElement).getPropertyValue('--glow').trim()};}`;
  navigator.clipboard?.writeText(css).then(() => toast('CSS kopieret til udklipsholder!'));
}

// ══════════════════════════════════════════════════════════
// DASHBOARD EDITOR
// ══════════════════════════════════════════════════════════
const DASH_WIDGETS = [
  {id:'cpu',     name:'CPU',          icon:'🖥',  span:1, color:'var(--o)'},
  {id:'ram',     name:'RAM',          icon:'💾',  span:1, color:'var(--o2)'},
  {id:'temp',    name:'Temperature',  icon:'🌡',  span:1, color:'var(--warn)'},
  {id:'uptime',  name:'Uptime',       icon:'⏱',  span:1, color:'var(--ok)'},
  {id:'network', name:'Network',      icon:'📡',  span:2, color:'var(--o)'},
  {id:'docker',  name:'Docker',       icon:'▣',  span:2, color:'var(--o2)'},
  {id:'storage', name:'Storage',      icon:'🗄',  span:2, color:'var(--warn)'},
  {id:'game',    name:'Game Servers', icon:'🎮',  span:2, color:'var(--ok)'},
  {id:'nas',     name:'NAS',          icon:'💽',  span:1, color:'var(--o)'},
  {id:'notes',   name:'Notes',        icon:'📝',  span:2, color:'var(--t2)'},
  {id:'clock',   name:'Clock',        icon:'🕐',  span:1, color:'var(--o)'},
  {id:'logs',    name:'System Logs',  icon:'📋',  span:4, color:'var(--t3)'},
  {id:'weather', name:'Weather',      icon:'🌤',  span:1, color:'var(--o2)'},
  {id:'ai',      name:'AI Chat',      icon:'🤖',  span:2, color:'var(--o)'},
  {id:'terminal',name:'Terminal',     icon:'⌨',  span:4, color:'var(--ok)'},
];
let _dashLayout = []; // [{widgetId, span}] in order
let _dashDragIdx = null;

function loadDashEditor() {
  const saved = localStorage.getItem('byteforge-dashboard');
  if (saved) { try { _dashLayout = JSON.parse(saved); } catch(e) { _dashLayout = []; } }
  buildWidgetPalette();
  renderDashCanvas();
  setTimeout(dashRefreshLiveData, 300);
}

function buildWidgetPalette() {
  const el = document.getElementById('dash-widget-list');
  if (!el) return;
  el.innerHTML = DASH_WIDGETS.map(w => {
    const inGrid = _dashLayout.some(d => d.widgetId === w.id);
    return `<div class="dash-widget-chip ${inGrid?'in-grid':''}" id="chip-${w.id}"
      onclick="dashAddWidget('${w.id}')" title="${inGrid?'Remove':'Add'} ${w.name}">
      <span class="dash-widget-chip-icon">${w.icon}</span>
      <span>${w.name}</span>
    </div>`;
  }).join('');
}

function dashAddWidget(id) {
  const idx = _dashLayout.findIndex(w => w.widgetId === id);
  if (idx >= 0) {
    _dashLayout.splice(idx, 1);
  } else {
    const def = DASH_WIDGETS.find(w => w.id === id);
    _dashLayout.push({widgetId: id, span: def?.span || 1});
  }
  buildWidgetPalette();
  renderDashCanvas();
}

function renderDashCanvas() {
  const canvas = document.getElementById('dash-canvas');
  const hint = document.getElementById('dash-empty-hint');
  if (!canvas) return;
  if (hint) hint.style.display = _dashLayout.length ? 'none' : 'flex';
  canvas.innerHTML = _dashLayout.map((item, idx) => {
    const def = DASH_WIDGETS.find(w => w.id === item.widgetId);
    if (!def) return '';
    const span = item.span || def.span || 1;
    const content = dashWidgetContent(def, item);
    return `<div class="dash-widget-card" data-idx="${idx}" data-span="${span}"
      draggable="true"
      ondragstart="dashCardDragStart(event,${idx})"
      ondragover="dashCardDragOver(event,${idx})"
      ondragleave="this.classList.remove('drag-target')"
      ondrop="dashCardDrop(event,${idx})">
      <button class="dwc-remove" onclick="dashRemoveWidget(${idx})" title="Remove">✕</button>
      <div class="dwc-header">
        <span class="dwc-icon">${def.icon}</span>
        <span class="dwc-name">${def.name}</span>
      </div>
      ${content}
      <div class="dwc-resize" onclick="dashCycleSpan(${idx})" title="Resize: ${span}/${span<4?span+1:1}">⟺ ${span}</div>
    </div>`;
  }).join('');
}

function dashWidgetContent(def, item) {
  const previews = {
    cpu:      `<div class="dwc-value" style="color:${def.color}" id="dw-cpu">—%</div><div class="dwc-bar"><div class="dwc-bar-fill" id="dwb-cpu" style="width:0%;background:${def.color}"></div></div>`,
    ram:      `<div class="dwc-value" style="color:${def.color}" id="dw-ram">—%</div><div class="dwc-bar"><div class="dwc-bar-fill" id="dwb-ram" style="width:0%;background:${def.color}"></div></div>`,
    temp:     `<div class="dwc-value" style="color:${def.color}" id="dw-temp">—°C</div>`,
    uptime:   `<div class="dwc-value" style="font-size:18px;color:${def.color}" id="dw-uptime">—</div>`,
    network:  `<div style="display:flex;gap:16px"><div><div class="dwc-sub">↓ IN</div><div class="dwc-value" style="font-size:18px;color:${def.color}" id="dw-netrx">—</div></div><div><div class="dwc-sub">↑ OUT</div><div class="dwc-value" style="font-size:18px;color:${def.color}" id="dw-nettx">—</div></div></div>`,
    docker:   `<div class="dwc-value" style="color:${def.color}" id="dw-docker">—</div><div class="dwc-sub">containers running</div>`,
    storage:  `<div class="dwc-value" style="font-size:20px;color:${def.color}" id="dw-storage">—</div><div class="dwc-sub">root disk used</div>`,
    game:     `<div class="dwc-value" style="color:${def.color}" id="dw-game">—</div><div class="dwc-sub">servers configured</div>`,
    nas:      `<div class="dwc-value" style="font-size:16px;color:${def.color}" id="dw-nas">—</div>`,
    clock:    `<div class="dwc-value" style="font-size:22px;color:${def.color}" id="dw-clock">—</div>`,
    notes:    `<textarea id="dw-notes" style="width:100%;flex:1;background:var(--bg);border:1px solid var(--b);color:var(--t);font-family:var(--mono);font-size:10px;padding:6px;resize:none;min-height:60px" placeholder="Your notes...">${localStorage.getItem('dash-notes')||''}</textarea>`,
    logs:     `<div id="dw-logs" style="font-family:var(--mono);font-size:9px;color:var(--t3);line-height:1.6;max-height:80px;overflow:hidden">Loading...</div>`,
    weather:  `<div class="dwc-value" style="color:${def.color}">🌤 —°C</div><div class="dwc-sub">Ingen weather API konfigureret</div>`,
    ai:       `<div class="dwc-value" style="font-size:14px;color:${def.color}">🤖 AI ASSISTANT</div><div class="dwc-sub" style="cursor:pointer;color:var(--o)" onclick="nav('ai',document.querySelector('[onclick*=nav__ai]'))">→ Åben AI chat</div>`,
    terminal: `<div style="background:var(--bg);border:1px solid var(--b);padding:8px;font-family:var(--mono);font-size:9px;color:var(--ok);line-height:1.6;min-height:60px">byteforge $ <span style="animation:blink 1s infinite">█</span></div>`,
  };
  return previews[def.id] || `<div class="dwc-sub">${def.name}</div>`;
}

function dashCardDragStart(e, idx) {
  _dashDragIdx = idx;
  e.dataTransfer.effectAllowed = 'move';
  setTimeout(() => { const el = document.querySelector(`[data-idx="${idx}"]`); if(el) el.classList.add('dragging'); }, 0);
}
function dashCardDragOver(e, idx) {
  e.preventDefault();
  if (_dashDragIdx === null || _dashDragIdx === idx) return;
  document.querySelectorAll('.dash-widget-card').forEach(c => c.classList.remove('drag-target'));
  document.querySelector(`[data-idx="${idx}"]`)?.classList.add('drag-target');
}
function dashCardDrop(e, targetIdx) {
  e.preventDefault();
  document.querySelectorAll('.dash-widget-card').forEach(c => c.classList.remove('drag-target','dragging'));
  if (_dashDragIdx === null || _dashDragIdx === targetIdx) { _dashDragIdx = null; return; }
  const item = _dashLayout.splice(_dashDragIdx, 1)[0];
  _dashLayout.splice(targetIdx, 0, item);
  _dashDragIdx = null;
  renderDashCanvas();
  dashRefreshLiveData();
}
function dashDropOnCanvas(e) {
  e.preventDefault();
  document.querySelectorAll('.dash-widget-card').forEach(c => c.classList.remove('drag-target','dragging'));
  _dashDragIdx = null;
}

function dashRemoveWidget(idx) {
  _dashLayout.splice(idx, 1);
  buildWidgetPalette();
  renderDashCanvas();
}

function dashCycleSpan(idx) {
  const item = _dashLayout[idx];
  if (!item) return;
  item.span = (item.span || 1) >= 4 ? 1 : (item.span || 1) + 1;
  renderDashCanvas();
  dashRefreshLiveData();
}

async function dashRefreshLiveData() {
  const sys = await api('/api/system');
  if (sys) {
    const setEl = (id, val) => { const el = document.getElementById(id); if(el) el.textContent = val; };
    const setW = (id, w) => { const el = document.getElementById(id); if(el) el.style.width = w+'%'; };
    setEl('dw-cpu', sys.cpu+'%'); setW('dwb-cpu', sys.cpu);
    setEl('dw-ram', sys.ram_pct+'%'); setW('dwb-ram', sys.ram_pct);
    setEl('dw-temp', sys.temp+'°C');
    setEl('dw-uptime', sys.uptime);
  }
  const docker = await api('/api/docker');
  if (docker) { const el = document.getElementById('dw-docker'); if(el) el.textContent = docker.filter(c=>c.status.includes('Up')).length+' / '+docker.length; }
  const disks = await api('/api/disks');
  if (disks?.length) { const el = document.getElementById('dw-storage'); if(el) el.textContent = disks[0].pct+'% ('+disks[0].used+'G / '+disks[0].total+'G)'; }
  const cfg = await api('/api/game-servers');
  if (cfg) { const el = document.getElementById('dw-game'); if(el) el.textContent = cfg.servers?.length || 0; }
  const clockEl = document.getElementById('dw-clock');
  if (clockEl) clockEl.textContent = new Date().toLocaleTimeString('da-DK',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const notesEl = document.getElementById('dw-notes');
  if (notesEl) notesEl.onblur = () => localStorage.setItem('dash-notes', notesEl.value);
}

function dashSave() {
  localStorage.setItem('byteforge-dashboard', JSON.stringify(_dashLayout));
  toast(`Dashboard gemt — ${_dashLayout.length} widgets`);
}

function dashClear() { _dashLayout = []; buildWidgetPalette(); renderDashCanvas(); }

function dashPreset(name) {
  const presets = {
    minimal: ['cpu','ram','temp','uptime'].map(id => ({widgetId:id, span: DASH_WIDGETS.find(w=>w.id===id)?.span||1})),
    full: ['cpu','ram','temp','uptime','network','docker','storage','game','nas','logs'].map(id => ({widgetId:id, span: DASH_WIDGETS.find(w=>w.id===id)?.span||1})),
    gaming: ['cpu','ram','game','docker','network','terminal'].map(id => ({widgetId:id, span: DASH_WIDGETS.find(w=>w.id===id)?.span||1})),
  };
  _dashLayout = presets[name] || [];
  buildWidgetPalette();
  renderDashCanvas();
  setTimeout(dashRefreshLiveData, 200);
  toast(`"${name}" preset indlæst`);
}

boot();
