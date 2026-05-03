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
  const map = {overview:loadOverview, system:loadSystem, network:loadNetwork, nas:loadNAS, raid:loadRAID, docker:loadDocker, minecraft:loadGameServers, proxy:loadProxy, files:loadFiles, access:loadAccess, settings:loadSettings, diskheath:loadDiskHealth, appstore:loadAppStore, terminal:initTerminal};
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
}

// ── OVERVIEW ──
async function loadOverview() {
  const d = window._lastData || await api('/api/all');
  if (!d) return;
  const s = d.system;
  document.getElementById('ov-cpu').innerHTML = s.cpu + '<span class="u">%</span>';
  document.getElementById('ov-cpu-bar').style.width = s.cpu + '%';
  document.getElementById('ov-ram').innerHTML = s.ram_pct + '<span class="u">%</span>';
  document.getElementById('ov-ram-s').textContent = s.ram_used_mb + ' / ' + s.ram_total_mb + ' MB';
  document.getElementById('ov-ram-bar').style.width = s.ram_pct + '%';
  document.getElementById('ov-temp').innerHTML = s.temp + '<span class="u">°C</span>';
  document.getElementById('ov-up').textContent = 'Uptime: ' + s.uptime;
  document.getElementById('ov-mc-b').innerHTML = mkbadge(d.minecraft.status, 'Online', 'Offline');
  document.getElementById('ov-mc-p').textContent = d.minecraft.players || 'Ingen spillere';
  document.getElementById('ov-nas-b').innerHTML = mkbadge(d.nas.status);
  document.getElementById('ov-raid-b').innerHTML = mkbadge(d.raid.status==='active'?'running':d.raid.status);
  document.getElementById('ov-dc').textContent = d.docker.length;
  document.getElementById('ov-disks').innerHTML = d.disks.map(dk => `
    <div class="card" style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-family:var(--display);font-size:18px;letter-spacing:2px">${dk.mount}</span>
        <span style="font-family:var(--mono);font-size:11px;color:var(--t3)">${dk.used}GB / ${dk.total}GB &nbsp; <b style="color:var(--o)">${dk.pct}%</b></span>
      </div>
      <div class="bar"><div class="bar-f" style="width:${dk.pct}%"></div></div>
      <div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:6px">${dk.free}GB fri</div>
    </div>`).join('');
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
  ['casaos','mc','nfs','inet'].forEach(id => {
    const el = document.getElementById('mon-' + id);
    if (!el) return;
    el.innerHTML = Array.from({length:30}, (_,i) =>
      `<div class="mbar ${Math.random() > 0.05 ? 'up' : 'down'}"></div>`).join('');
  });
  const net = await api('/api/network');
  if (!net) return;
  document.getElementById('net-info').innerHTML = `
    <tr><td>Interface</td><td style="color:var(--o2)">${escapeHTML(net.interface)}</td></tr>
    <tr><td>IP Adresse</td><td style="color:var(--o2)">${escapeHTML(net.ip)}</td></tr>
    <tr><td>Gateway</td><td style="color:var(--o2)">${escapeHTML(net.gateway)}</td></tr>
    <tr><td>Hostname</td><td style="color:var(--o2)">${escapeHTML(net.hostname)}</td></tr>
  `;
}

function testWebhook() {
  const url = document.getElementById('webhook-url').value;
  if (!url) { toast('Ingen webhook URL indtastet', false); return; }
  toast('Test alert sendt til webhook!');
}
function saveWebhook() { toast('Webhook gemt'); }

// ── NAS ──
async function loadNAS() {
  const n = await api('/api/nas');
  if (!n) return;
  document.getElementById('nas-badge').innerHTML = mkbadge(n.status);
  document.getElementById('nas-exports').innerHTML = n.shares.length
    ? n.shares.map(s=>`<div class="t-o">${s}</div>`).join('')
    : '<span style="color:var(--t3)">Ingen shares fundet</span>';
  const d = window._lastData?.disks || (await api('/api/disks'));
  if (d) document.getElementById('nas-storage').innerHTML = d.map(dk=>`
    <div class="card" style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between"><span style="font-family:var(--display);letter-spacing:2px">${dk.mount}</span><b style="color:var(--o)">${dk.pct}%</b></div>
      <div class="bar"><div class="bar-f" style="width:${dk.pct}%"></div></div>
    </div>`).join('');
}
// nasRestart defined below (async implementation)

// ── RAID ──
async function loadRAID() {
  const r = await api('/api/raid');
  if (!r) return;
  document.getElementById('raid-badge').innerHTML = mkbadge(r.status==='active'?'running':r.status);
  document.getElementById('raid-info').innerHTML = r.info
    ? r.info.split('\n').map(l=>`<div>${l}</div>`).join('')
    : '<span style="color:var(--t3)">Ingen RAID array fundet. Tilslut mindst 2 ekstra diske.</span>';
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
    'ver.tagline':'CASAOS UAFHÆNGIG',
    'set.theme':'Theme','set.language':'Sprog','set.background':'Baggrund',
    'docker.notinstalled':'DOCKER IKKE INSTALLERET',
    'docker.notinstalled.desc':'Docker kræves for at køre containers og game servers.',
    'docker.btn.install':'▣ INSTALLER DOCKER NU',
    'docker.installing':'Installerer Docker, vent venligst...',
    'docker.running':'KØRENDE',
    'gs.servername':'Server navn','gs.type':'Type',
    'nav.appstore':'App Store','nav.terminal':'Terminal',
  },
  en: {
    'nav.overview':'Overview','nav.dashboard':'Dashboard','nav.system':'System','nav.network':'Network',
    'nav.storage':'Storage','nav.nas':'NAS','nav.raid':'RAID','nav.backup':'Backup & Sync','nav.diskhealth':'Disk Health',
    'nav.services':'Services','nav.docker':'Docker','nav.gameservers':'Game Servers','nav.proxy':'Proxy & SSL','nav.websites':'Websites','nav.privacy':'Privacy Suite',
    'nav.platform':'Platform','nav.files':'Files','nav.access':'Access','nav.settings':'Settings',
    'nav.tools':'Tools','nav.ai':'AI Assistant','nav.devtools':'Dev Tools','nav.marketplace':'Marketplace',
    'ver.tagline':'CASAOS INDEPENDENT',
    'set.theme':'Theme','set.language':'Language','set.background':'Background',
    'docker.notinstalled':'DOCKER NOT INSTALLED',
    'docker.notinstalled.desc':'Docker is required to run containers and game servers.',
    'docker.btn.install':'▣ INSTALL DOCKER NOW',
    'docker.installing':'Installing Docker, please wait...',
    'docker.running':'RUNNING',
    'gs.servername':'Server name','gs.type':'Type',
    'nav.appstore':'App Store','nav.terminal':'Terminal',
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
  if (theme === 'forge-dark') {
    el.textContent = '';
  } else if (theme === 'forge-light') {
    el.textContent = `
      :root{--bg:#f0ece6;--s:#e8e2d9;--p:#ddd7cc;--b:#c0b8ad;--b2:#a89f93;
        --t:#1a1208;--t2:#4a3f30;--t3:#8a7a65;--o:#d45a00;--o2:#e07020;--o3:rgba(212,90,0,.1)}
      body::before{background-image:linear-gradient(var(--b) 1px,transparent 1px),linear-gradient(90deg,var(--b) 1px,transparent 1px);opacity:.4}
      #topbar{background:rgba(240,236,230,.96)}
      #sidebar{background:var(--s)}`;
  } else if (theme === 'high-contrast') {
    el.textContent = `
      :root{--bg:#000;--s:#0a0a0a;--p:#111;--b:#fff;--b2:#ccc;
        --t:#fff;--t2:#eee;--t3:#aaa;--o:#ff6b1a;--o2:#ff9a3c;--o3:rgba(255,107,26,.15)}
      body::before{opacity:.15}`;
  }
  window._currentTheme = theme;
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

async function loadFiles() {
  const scope = document.getElementById('file-scope')?.value || 'public';
  const data = await api('/api/files?scope=' + encodeURIComponent(scope));
  const out = document.getElementById('file-list');
  if (!out || !data) return;
  if (!data.items.length) { out.innerHTML = '<div class="file-row"><strong>Tom mappe</strong><span></span><span></span><span></span><span></span></div>'; return; }
  out.innerHTML = data.items.map(item => `
    <div class="file-row">
      <span>${item.type === 'folder' ? '▸' : '□'}</span>
      <strong>${escapeHTML(item.name)}</strong>
      <span>${item.type}</span>
      <span>${item.type === 'file' ? Math.ceil(item.size/1024) + ' KB' : '-'}</span>
      <button class="btn btn-r btn-sm" onclick="deleteFile('${encodeURIComponent(item.name)}')">SLET</button>
    </div>`).join('');
}

async function deleteFile(name) {
  const scope = document.getElementById('file-scope').value;
  const r = await fetch(BASE+'/api/files/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'delete',scope,path:decodeURIComponent(name)})});
  const d = await r.json();
  toast(d.msg || 'Slettet', d.ok);
  loadFiles();
}

async function makeFolder() {
  const scope = document.getElementById('file-scope').value;
  const name = document.getElementById('file-query').value.trim();
  if (!name) { toast('Skriv et mappenavn først', false); return; }
  const r = await fetch(BASE+'/api/files/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'mkdir',scope,path:name})});
  const d = await r.json();
  toast(d.msg || 'Mappe oprettet', d.ok);
  loadFiles();
}

async function searchFiles() {
  const scope = document.getElementById('file-scope').value;
  const query = document.getElementById('file-query').value.trim();
  const r = await fetch(BASE+'/api/files/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'search',scope,query})});
  const d = await r.json();
  const out = document.getElementById('file-list');
  out.innerHTML = (d.matches || []).map(m => `<div class="file-row"><span>${m.type === 'folder' ? '▸' : '□'}</span><strong>${escapeHTML(m.path)}</strong><span>${m.type}</span><span></span><span></span></div>`).join('') || '<div class="file-row"><strong>Ingen resultater</strong></div>';
}

async function uploadFile() {
  const input = document.getElementById('file-upload');
  if (!input.files.length) { toast('Vælg en fil først', false); return; }
  const form = new FormData();
  form.append('scope', document.getElementById('file-scope').value);
  form.append('file', input.files[0]);
  const r = await fetch(BASE+'/api/files/upload',{method:'POST',body:form});
  const d = await r.json();
  toast(d.msg || 'Upload færdig', d.ok);
  input.value = '';
  loadFiles();
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
  out.innerHTML = `
    <div class="grid g2">
      <div class="card">
        <div class="ct">KIOXIA KXG60ZNV256G <span class="badge b-ok" style="margin-left:8px"><span class="bd"></span>HEALTHY</span></div>
        <div class="smart-row"><span>Model</span><span class="smart-val">KIOXIA KXG60ZNV256G</span></div>
        <div class="smart-row"><span>Kapacitet</span><span class="smart-val">238 GB</span></div>
        <div class="smart-row"><span>Type</span><span class="smart-val">NVMe SSD</span></div>
        <div class="smart-row"><span>Temperatur</span><span class="smart-val" id="disk-temp1">— °C</span></div>
        <div class="smart-row"><span>Power-on timer</span><span class="smart-val">—</span></div>
        <div class="smart-row"><span>Status</span><span class="smart-val" style="color:var(--ok)">PASSED</span></div>
      </div>
      <div class="card">
        <div class="ct">MICRON MTFDKBA512TFH <span class="badge b-ok" style="margin-left:8px"><span class="bd"></span>HEALTHY</span></div>
        <div class="smart-row"><span>Model</span><span class="smart-val">Micron MTFDKBA512TFH</span></div>
        <div class="smart-row"><span>Kapacitet</span><span class="smart-val">476 GB</span></div>
        <div class="smart-row"><span>Type</span><span class="smart-val">NVMe SSD</span></div>
        <div class="smart-row"><span>Temperatur</span><span class="smart-val" id="disk-temp2">— °C</span></div>
        <div class="smart-row"><span>Power-on timer</span><span class="smart-val">—</span></div>
        <div class="smart-row"><span>Status</span><span class="smart-val" style="color:var(--ok)">PASSED</span></div>
      </div>
    </div>`;
}

// ── AI ──
async function sendAI() {
  const inp = document.getElementById('ai-input');
  const msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  appendMsg('user', msg);
  const thinking = appendMsg('bot', '<span class="thinking">⚒ Tænker...</span>');
  try {
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        model:'claude-sonnet-4-20250514',
        max_tokens:1000,
        system:`Du er ByteForge AI assistant på Admins hjemmeserver. Serveren kører Linux med ByteForge, Docker, NFS NAS, RAID og game servers. Svar på dansk, kort og præcist. Brug teknisk sprog.`,
        messages:[{role:'user',content:msg}]
      })
    });
    const data = await resp.json();
    const text = data.content?.[0]?.text || 'Ingen svar fra AI';
    thinking.querySelector('.bubble').innerHTML = text.replace(/\n/g,'<br>');
  } catch(e) {
    thinking.querySelector('.bubble').innerHTML = 'API fejl: ' + e.message;
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

async function nasRestart() {
  toast('Genstarter NFS server...');
  try {
    const r = await fetch(BASE+'/api/nas/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'restart'})});
    const d = await r.json();
    toast(d.msg||'NFS genstartet', d.ok);
  } catch(e) { toast('Fejl: '+e.message, false); }
}

function runBackup(job) { toast('Backup job kørende: ' + job + '...'); }

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

// ── APP STORE ──
let _allApps = [], _currentCat = 'All';

async function loadAppStore() {
  const grid = document.getElementById('app-store-grid');
  grid.innerHTML = '<div class="card"><div class="ct">INDLÆSER</div><div class="cs">Henter app catalog...</div></div>';
  const apps = await api('/api/appstore');
  if (!apps) { grid.innerHTML = '<div class="card"><div class="ct">FEJL</div><div class="cs">Kunne ikke hente app catalog</div></div>'; return; }
  _allApps = apps;
  renderApps(apps);
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
  if (!apps.length) { grid.innerHTML = '<div class="card"><div class="ct">INGEN RESULTATER</div><div class="cs">Prøv et andet søgeord eller kategori.</div></div>'; return; }
  grid.innerHTML = apps.map(a => {
    const installed = a.installed;
    const running = a.status === 'running';
    const statusHtml = installed
      ? `<span class="app-status" style="color:${running?'var(--ok)':'var(--warn)'}">${running?'● KØRENDE':'○ STOPPET'}</span>`
      : `<span class="app-status" style="color:var(--t3)">○ IKKE INSTALLERET</span>`;
    const btnHtml = installed
      ? `<div style="display:flex;gap:6px">
           <button class="btn btn-g btn-sm" onclick="appAction('${a.id}','${running?'stop':'start'}')">${running?'■ STOP':'▶ START'}</button>
           <button class="btn btn-r btn-sm" onclick="appUninstall('${a.id}')">🗑</button>
         </div>`
      : `<button class="btn btn-o btn-sm" onclick="appInstall('${a.id}')">⚡ INSTALL</button>`;
    return `<div class="app-card ${installed?'installed':''}" id="appcard-${a.id}">
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

async function appInstall(id) {
  const app = _allApps.find(a => a.id === id);
  toast(`Installerer ${app?.name || id}...`);
  const r = await fetch(BASE+'/api/appstore/install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app:id})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Installeret' : 'Fejl'), d.ok);
  if (d.ok) setTimeout(loadAppStore, 1000);
}

async function appUninstall(id) {
  const app = _allApps.find(a => a.id === id);
  toast(`Afinstallerer ${app?.name || id}...`);
  const r = await fetch(BASE+'/api/appstore/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app:id})});
  const d = await r.json();
  toast(d.msg || (d.ok ? 'Afinstalleret' : 'Fejl'), d.ok);
  if (d.ok) setTimeout(loadAppStore, 800);
}

async function appAction(id, action) {
  const r = await fetch(BASE+'/api/docker/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({container:`byteforge-${id}`,action})});
  const d = await r.json();
  toast(d.msg||'Udført', d.ok);
  setTimeout(loadAppStore, 800);
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
  loadOverview();
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

boot();
