/* isaac-ui front-end (jQuery 3.7).
   Conventions for maintainers:
   - DOM/query/render via jQuery ($('#x').html()/.val()/.addClass()…).
   - AJAX via the getJSON()/postJSON() helpers below (thin $.ajax wrappers, awaitable).
   - Inline onclick="fn(...)" in generated markup call the global fns defined here.
   - A few spots stay vanilla on purpose (commented): clipboard fallback, file download,
     and getBoundingClientRect for the fixed-position hover popover. */

let auto = true, timer = null;
const esc = s => (s == null ? "" : String(s)).replace(/[&<>"]/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---- AJAX helpers (awaitable; jqXHR is Promise-like in jQuery 3) ----
const getJSON = url => $.ajax({ url, dataType: 'json', cache: false });
function postJSON(url, body) {
  const o = { url, method: 'POST', dataType: 'json', cache: false };
  if (body !== undefined) { o.contentType = 'application/json'; o.data = JSON.stringify(body); }
  return $.ajax(o);
}

function toast(msg, kind) {
  $('<div>', { 'class': 'toast ' + (kind || ''), text: msg })
    .appendTo('#toasts').delay(4000).fadeOut(200, function () { $(this).remove(); });
}
function stClass(r) {
  if (r.phase === 'Running' && r.ready) return ['ok', 'Running'];
  if (r.phase === 'Failed' || r.phase === 'CrashLoopBackOff') return ['bad', r.phase];
  if (r.phase === 'Running' && !r.ready) return ['wait', 'Not ready'];
  if (r.phase === '-' || !r.phase) return ['mut', 'Pending'];
  return ['wait', r.phase];
}

async function refresh() {
  try {
    const [items, g] = await Promise.all([getJSON('/api/instances'), getJSON('/api/gpu')]);
    render(items); renderGpu(g);
    $('#updated').text('updated ' + new Date().toLocaleTimeString());
  } catch (e) { toast('refresh failed', 'err'); }
  loadCollect();   // per-pod collection verification (fail-soft, real-time)
}

// ---- per-pod collection verification panel (network, real-time) ----
async function loadCollect() {
  let d;
  try { d = await getJSON('/api/metrics/verify'); }
  catch (e) { d = { available: false, reason: 'request failed' }; }
  renderCollect(d);
}
function renderCollect(d) {
  const $el = $('#collectBody'), $st = $('#collectStatus');
  if (!d || !d.available) {
    $st.html('<span class="cdot bad"></span>Prometheus unreachable');
    $el.html('<div class="hint">Prometheus 연결 안됨 — 수집 검증 불가. (수집기가 안 돌아도 인스턴스는 정상 동작합니다.)'
      + (d && d.reason ? ' <span class="mono" style="font-size:11px;color:var(--mut)">' + esc(d.reason) + '</span>' : '') + '</div>');
    return;
  }
  const all = d.podsTotal > 0 && d.podsUp === d.podsTotal;
  $st.html('<span class="cdot ' + (all ? 'ok' : (d.podsUp > 0 ? 'warn' : 'bad')) + '"></span>' + d.podsUp + '/' + d.podsTotal + ' pods scraped &middot; up=1');
  if (!d.pods || !d.pods.length) {
    $el.html('<div class="hint">수집 대상 pod이 아직 없습니다 — 인스턴스 생성 후 몇 분 뒤 자동으로 나타납니다.</div>'); return;
  }
  $el.html('<table class="ctab"><thead><tr><th>pod</th><th>owner</th><th>scrape</th>'
    + '<th class="num">samples</th><th class="num">↑ tx</th><th class="num">↓ rx</th></tr></thead><tbody>'
    + d.pods.map(p => '<tr><td class="mono pn">' + esc(p.pod) + '</td><td>' + esc(p.owner || '-') + '</td>'
      + '<td>' + (p.up === 1 ? '<span class="cdot ok"></span>up' : (p.up === 0 ? '<span class="cdot bad"></span>down' : '<span class="cdot warn"></span>?')) + '</td>'
      + '<td class="num mono">' + (p.samples != null ? p.samples : '-') + '</td>'
      + '<td class="num mono">' + (p.txBps != null ? fmtBps(p.txBps) : '-') + '</td>'
      + '<td class="num mono">' + (p.rxBps != null ? fmtBps(p.rxBps) : '-') + '</td></tr>').join('')
    + '</tbody></table><div class="chint">updated ' + new Date(d.ts * 1000).toLocaleTimeString()
    + ' · auto-refresh · up=1 + samples&gt;0 + tx/rx 흐르면 정상 수집</div>');
}

let _gpu = null;   // last /api/gpu payload (ban-modal pickers read node/UUID lists from it)
function renderGpu(g) {
  _gpu = g;
  const $el = $('#gpu');
  if (!g || !g.nodes) { $el.empty(); return; }
  if (!g.nodes.length) {
    $el.html('<div class="gpuhead"><span class="warn">No GPUs recognized by the cluster — GPU Operator may be disabled on the other nodes.</span></div>');
    return;
  }
  const t = g.totals;
  const head = '<div class="gpuhead">'
    + '<span class="ghl">You can launch <b>' + g.launchable + '</b> more instance' + (g.launchable === 1 ? '' : 's') + '</span>'
    + '<span class="gsub">cluster GPUs: ' + t.free + ' free / ' + t.total + ' total'
    + (g.usageKnown ? '' : ' · usage needs cluster pods:list RBAC') + '</span></div>';
  const legend = '<div class="legend">'
    + '<span><span class="pip used"></span>this UI</span>'
    + '<span><span class="pip ext"></span>other workloads</span>'
    + '<span><span class="pip ban"></span>banned</span>'
    + '<span><span class="pip denied"></span>product-denied</span>'
    + '<span><span class="pip free"></span>free</span>'
    + '<span><span class="pip free mig"></span>MIG-partitioned (expand for slices)</span></div>';
  const cards = g.nodes.map(n => {
    const gb = n.gpuBans || [];
    // under DRA every UUID ban is schedule-time enforced (CEL) -> always show all
    const nban = (g.banAsUsed || g.draEnabled) ? gb.length : gb.filter(b => !b.applied).length;
    const banCls = g.banAsUsed ? 'usedban' : 'ban';
    const nden = n.deniedGpus || 0;
    const dev = n.devices || [];
    const stCls = { ui: 'used', ext: 'ext', banned: (g.banAsUsed ? 'usedban' : 'ban'), denied: 'denied', free: 'free' };
    const dta = (st, model, uuid, mig, migu) => 'data-node="' + esc(n.node) + '" data-model="' + esc(model || 'GPU')
      + '" data-state="' + st + '" data-uuid="' + esc(uuid || '') + '"'
      + (mig ? (' data-mig="' + mig + '" data-migused="' + (migu || 0) + '"') : '');
    let pips = '';
    if (dev.length) {
      // DRA-exact: one pip per PHYSICAL GPU, colored by state; MIG-sliced GPUs carry an
      // inner dot; partitions are listed in the detail below. Hover reveals the popover.
      pips = dev.map(d => {
        const mig = d.mig && d.mig.length, migu = mig ? d.mig.filter(m => m.used).length : 0;
        return '<span class="pip ' + (stCls[d.state] || 'free') + (mig ? ' mig' : '') + '" '
          + dta(d.state, d.product, d.uuid, d.mig && d.mig.length, migu) + '></span>';
      }).join('');
    } else {
      // legacy: used splits into this UI (blue) vs other cluster workloads (purple)
      const nui = Math.min(n.uiUsed || 0, n.used), next = n.used - nui;
      for (let i = 0; i < n.total; i++) {
        let st, cls;
        if (i < nui) { st = 'ui'; cls = 'used'; }
        else if (i < nui + next) { st = 'ext'; cls = 'ext'; }
        else if (i < n.used + nban) { st = 'banned'; cls = banCls; }
        else if (i < n.used + nban + nden) { st = 'denied'; cls = 'denied'; }
        else { st = 'free'; cls = 'free'; }
        pips += '<span class="pip ' + cls + '" ' + dta(st, n.product) + '></span>';
      }
    }
    // MIG breakdown: parent GPU stays one pip, its slices shown as sub-elements
    const migHtml = dev.filter(d => d.mig && d.mig.length).map(d => {
      const inUse = d.mig.filter(m => m.used).length;
      const rows = d.mig.map(m => {
        const lbl = m.name.indexOf(d.name + '-mig-') === 0 ? m.name.slice((d.name + '-mig-').length) : m.name;
        return '<div class="migp' + (m.used ? ' u' : '') + '">'
          + '<span class="mgi">' + esc(lbl) + '</span> ' + esc((m.uuid || '').slice(0, 18)) + '&hellip; '
          + (m.used ? ('in use' + (m.owner === 'ui' ? ' (this UI)' : ' (other)')) : 'free') + '</div>';
      }).join('');
      return '<details class="gc-mig"><summary>' + esc(d.product) + ' · MIG ' + d.mig.length
        + ' partitions (' + inUse + ' in use)</summary>' + rows + '</details>';
    }).join('');
    const badge = n.nvenc ? '' : '<span class="nob" title="no hardware encoder">no NVENC</span>';
    const off = n.allowed ? '' : '<span class="nob" title="not in instance node set">off-target</span>';
    const ban = n.banned ? '<span class="banb" title="' + esc((n.banReasons || []).join('; ')) + '">BANNED</span>' : '';
    const deny = n.denied ? '<span class="banb" title="' + esc(n.deniedReason || '') + '">INCOMPATIBLE</span>' : '';
    const uuids = gb.length ? '<details class="gc-bans"><summary>' + (g.banAsUsed ? 'reserved' : 'banned') + ' (' + gb.length + ')</summary>' + gb.map(b =>
      esc((b.uuid || '').slice(0, 20)) + '&hellip;' + (b.reason ? ' — ' + esc(b.reason) : '')
      + (g.draEnabled ? ' (enforced)' : (b.applied ? ' (applied)' : ' (pending)'))).join('<br>') + '</details>' : '';
    const blocked = n.banned || n.denied;
    const sel = n.allowed && !blocked && (n.draExact || n.nvenc);
    return '<div class="gcard' + (sel ? ' on' : '') + (blocked ? ' banned' : '') + '">'
      + '<div class="gc-h"><span class="gc-n">' + esc(n.node) + '</span>' + ban + deny + badge + off + '</div>'
      + '<div class="gc-p">' + esc(n.product) + '</div>'
      + '<div class="pips">' + pips + '</div>'
      + '<div class="gc-f">' + (g.usageKnown ? (n.free + ' free / ' + n.total) : (n.total + ' total')) + '</div>'
      + (n.extUsed ? '<div class="gc-ext">' + n.extUsed + ' in use by other workloads</div>' : '')
      + migHtml + uuids + '</div>';
  }).join('');
  $el.html(head + '<div class="gcards">' + cards + '</div>' + legend);
}

const stat = (l, n, k) => '<div class="stat ' + k + '"><div class="n">' + n + '</div><div class="l">' + l + '</div></div>';
function render(items) {
  const tot = items.length, run = items.filter(i => i.phase === 'Running' && i.ready).length,
    wait = items.filter(i => !(i.phase === 'Running' && i.ready) && i.phase !== 'Failed').length,
    bad = items.filter(i => i.phase === 'Failed').length;
  $('#stats').html(stat('Total', tot, '') + stat('Running', run, 'r') + stat('Pending', wait, 'w') + stat('Failed', bad, 'b'));
  if (!items.length) {
    $('#rows').html('<tr><td colspan="7" class="empty">No instances. Click “+ New instance”.</td></tr>');
    return;
  }
  $('#rows').html(items.map(r => {
    const [c, t] = stClass(r);
    let ip = esc(r.ip);
    if (r.ip && r.ip !== '-' && r.adv !== r.ip) ip += ' <span class="tag">syncing</span>';
    else if (r.ip && r.ip !== '-') ip += ' <button class="copy" onclick="copy(this,\'' + esc(r.ip) + '\')">copy</button>';
    return '<tr>'
      + '<td><div class="nm">' + esc(r.name) + '</div>' + (r.owner ? '<div class="sub">' + esc(r.owner) + '</div>' : '') + '</td>'
      + '<td><span class="st ' + c + '"><span class="dot"></span>' + esc(t) + (r.restarts ? ' · ' + r.restarts + '↻' : '') + '</span></td>'
      + '<td class="mono">' + esc(r.age || '-') + '</td>'
      + '<td class="mono">' + esc(r.node) + '</td>'
      + '<td class="mono" style="font-size:12px">' + esc(r.gpu) + '</td>'
      + '<td class="mono">' + ip + '</td>'
      + '<td><div class="row-actions">'
      + '<button onclick="openDrawer(\'' + esc(r.name) + '\')">Details</button>'
      + (r.vscode ? '<button class="vs" onclick="window.open(\'' + esc(r.vscode) + '\',\'_blank\')" title="open bundled VSCode (password in Details)">VSCode</button>' : '')
      + '<button class="danger" onclick="doDelete(\'' + esc(r.name) + '\')">Delete</button>'
      + '</div></td></tr>';
  }).join(''));
}

// ---- clipboard copy with inline confirmation ----
function copy(btn, t) {
  // call as copy(this, value) from a button; copy(value) also works (no inline flip).
  if (typeof t === 'undefined') { t = btn; btn = null; }
  const ok = () => { toast('copied ' + t, 'ok'); if (btn) flashCopied(btn); },
    fail = () => toast('copy failed — ' + t, 'err');
  // navigator.clipboard exists only in secure contexts (https/localhost); this UI is
  // served over plain http on the LAN, so fall back to a hidden textarea + execCommand.
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(t).then(ok, () => { legacyCopy(t) ? ok() : fail(); });
    return;
  }
  legacyCopy(t) ? ok() : fail();
}
function flashCopied(btn) {
  const $b = $(btn), old = $b.data('lbl') || $b.text();
  $b.data('lbl', old); clearTimeout($b.data('t'));
  $b.text('copied ✓').addClass('done');
  $b.data('t', setTimeout(() => { $b.text(old).removeClass('done').removeData('lbl'); }, 1300));
}
function legacyCopy(t) {
  // vanilla by necessity: execCommand needs a real focused/selected element in the DOM
  const ta = document.createElement('textarea');
  ta.value = t; ta.setAttribute('readonly', '');
  ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
  document.body.appendChild(ta); ta.focus(); ta.select();
  let done = false;
  try { done = document.execCommand('copy'); } catch (e) {}
  document.body.removeChild(ta);
  return done;
}

// ---- GPU pip hover popover (semi-transparent status card after a short dwell) ----
const GP_DWELL = 700;   // ms to hover before the popover appears (tune to taste)
const GP_STATE = {
  ui: ['in use · this UI', 'used'], ext: ['in use · other workload', 'ext'],
  banned: ['banned', 'ban'], denied: ['product-denied · no NVENC', 'denied'], free: ['idle · free', 'free']
};
function showGpop(pip) {
  const d = pip.dataset, s = GP_STATE[d.state] || ['', ''];
  let rows = '';
  if (d.uuid) rows += '<div class="gp-row"><span>UUID</span><b>' + esc(d.uuid.slice(0, 20)) + '…</b></div>';
  if (d.mig) rows += '<div class="gp-row"><span>MIG</span><b>' + esc(d.mig) + ' partitions · ' + esc(d.migused || '0') + ' in use</b></div>';
  let $p = $('#gpop');
  if (!$p.length) $p = $('<div id="gpop" class="gpop"></div>').appendTo('body');
  $p.html('<div class="gp-node">' + esc(d.node) + '</div><div class="gp-m">' + esc(d.model) + '</div>'
    + '<div class="gp-s"><span class="d ' + s[1] + '"></span>' + esc(s[0]) + '</div>' + rows).addClass('on');
  // vanilla rect: popover is position:fixed, so it needs viewport coords (not $.offset())
  const r = pip.getBoundingClientRect(), pw = $p.outerWidth(), ph = $p.outerHeight();
  let left = r.left + r.width / 2 - pw / 2, top = r.top - ph - 8;
  if (top < 8) top = r.bottom + 8;                          // flip below if near the top
  left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
  $p.css({ left: left + 'px', top: top + 'px' });
}
function hideGpop() { $('#gpop').removeClass('on'); }
function initGpop() {
  if (initGpop._done) return; initGpop._done = true;
  let t = null;
  $(document)
    .on('pointerover', '.pip[data-node]', function () {
      if ($(this).closest('.legend').length) return;
      const pip = this; clearTimeout(t); t = setTimeout(() => showGpop(pip), GP_DWELL);
    })
    .on('pointerout', '.pip[data-node]', function () { clearTimeout(t); hideGpop(); });
  $(window).on('scroll', () => { clearTimeout(t); hideGpop(); });
}

// ---- instance detail drawer ----
async function openDrawer(name) {
  $('#scrim, #drawer').addClass('on');
  $('#dTitle').html('<span class="st mut"><span class="dot"></span></span>' + esc(name));
  $('#dBody').html('<div class="empty">loading…</div>');
  let d;
  try { d = await getJSON('/api/instance?name=' + encodeURIComponent(name)); }
  catch (e) { $('#dBody').html('<div class="empty">not found</div>'); return; }
  if (d._error) { $('#dBody').html('<div class="empty">not found</div>'); return; }
  const [c, t] = stClass(d);
  $('#dTitle').html('<span class="st ' + c + '"><span class="dot"></span></span>' + esc(d.name));
  const kv = o => Object.entries(o).map(([k, v]) => '<div class="k">' + k + '</div><div class="v">' + esc(v || '-') + '</div>').join('');
  let html = '<div class="kv">' + kv({
    'status': t + (d.restarts ? '  (' + d.restarts + ' restarts)' : ''),
    'created': d.created, 'age': d.age, 'owner': d.owner, 'created by': d.createdBy,
  }) + '</div>';
  if (d.description) html += '<div class="sect">Description</div><div style="font-size:13px;white-space:pre-wrap">' + esc(d.description) + '</div>';
  html += '<div class="sect">Runtime</div><div class="kv">' + kv({
    'node': d.node, 'gpu': d.gpu, 'gpu UUID': d.gpuUUID || '-', 'image': d.image, 'pod': d.podName, 'pod IP': d.podIP,
    'stream IP': d.streamIP, 'advertised': d.advertised,
  }) + '</div>';
  if (d.ports && d.ports.length) html += '<div class="sect">Ports</div><div class="kv">'
    + d.ports.map(p => '<div class="k">' + esc(p.name) + '</div><div class="v">' + p.port + '/' + p.protocol + '</div>').join('') + '</div>';
  if (d.codeServerURL) {
    html += '<div class="sect">VSCode (code-server)</div>'
      + '<div class="vscode">'
      + '<a class="vsbtn" href="' + esc(d.codeServerURL) + '" target="_blank" rel="noopener">Open VSCode ↗</a>'
      + (d.codeServerPassword
        ? '<div class="vspw">password <code>' + esc(d.codeServerPassword) + '</code>'
        + '<button class="copy" onclick="copy(this,\'' + esc(d.codeServerPassword) + '\')">copy</button></div>'
        : '')
      + (d.workspaceDir ? '<div class="hint">editing <code>' + esc(d.workspaceDir) + '</code> · shared live with the sim</div>' : '')
      + '</div>';
  }
  html += '<div class="sect">Recent events</div>';
  html += (d.events && d.events.length) ? d.events.slice().reverse().map(e =>
    '<div class="ev ' + esc(e.type) + '"><span class="r">' + esc(e.reason) + '</span> <span style="color:var(--mut)">' + esc(e.time) + '</span>'
    + '<div class="m">' + esc(e.message) + '</div></div>').join('')
    : '<div class="hint">no events</div>';
  $('#dBody').html(html);
}
function closeDrawer() { $('#scrim, #drawer').removeClass('on'); }

// ---- GPU bans modal ----
function openBans() { $('#banModal').addClass('on'); banFormSync(); loadBans(); }
function closeBans() { $('#banModal').removeClass('on'); }
function banFormSync() {
  const k = $('#bKind').val();
  $('#bfNode').toggle(k === 'node' || k === 'gpu');
  $('#bfProduct').toggle(k === 'product');
  $('#bfUuid').toggle(k === 'gpu');
  $('#bHint').text(k === 'gpu'
    ? 'With DRA (default): enforced at schedule time — the UUID goes into every new instance’s ResourceClaim CEL deny-list. Without DRA it is display-only unless you exclude the UUID node-side and press “applied”.'
    : k === 'product' ? 'case-insensitive substring, matched per GPU against the DRA productName attribute (A100 hits NVIDIA A100-PCIE-40GB); node labels are not used'
      : 'node is removed from every new instance’s nodeAffinity');
  banFillPickers();
}
function banFillPickers() {
  // datalists from the live DRA inventory (/api/gpu devices) - pick, don't type
  if (!_gpu || !_gpu.nodes) return;
  $('#nodeList').html(_gpu.nodes.map(n => '<option value="' + esc(n.node) + '">' + esc(n.product) + '</option>').join(''));
  const ps = {};
  _gpu.nodes.forEach(n => (n.devices || []).forEach(d => { if (d.product) ps[d.product] = 1; }));
  $('#productList').html(Object.keys(ps).sort().map(p => '<option value="' + esc(p) + '"></option>').join(''));
  const node = $('#bNode').val().trim(), rows = [];
  _gpu.nodes.forEach(n => {
    if (node && n.node !== node) return;
    (n.devices || []).forEach(d => {
      rows.push('<option value="' + esc(d.uuid) + '">' + esc(d.product || '?') + ' · ' + esc(n.node)
        + (d.banned ? ' · already banned' : '') + (d.denied ? ' · product-denied' : '') + '</option>');
    });
  });
  $('#uuidList').html(rows.join(''));
}
async function loadBans() {
  const d = await getJSON('/api/bans');
  const $el = $('#banList');
  if (!d.ok) { $el.html('<div class="hint">ban store unavailable (' + esc(d.store) + ')</div>'); return; }
  if (!d.bans.length) { $el.html('<div class="hint">no bans · store: ' + esc(d.store) + '</div>'); return; }
  $el.html(d.bans.map(b => {
    const tgt = b.kind === 'node' ? b.node : b.kind === 'product' ? b.product : b.node + ' · ' + b.uuid + (b.index != null && b.index !== '' ? ' (#' + b.index + ')' : '');
    const ap = b.kind === 'gpu' ? (b.applied
      ? '<span class="applied">applied</span><button onclick="banApplied(\'' + b.id + '\',false)">undo</button>'
      : '<span class="pending">pending</span><button onclick="banApplied(\'' + b.id + '\',true)" title="node-side device-plugin exclusion done">applied</button>') : '';
    return '<div class="banrow"><span class="bk">' + esc(b.kind) + '</span><span class="bt">' + esc(tgt)
      + (b.reason ? '<br><span class="br">' + esc(b.reason) + '</span>' : '') + '</span>' + ap
      + '<button class="danger" onclick="doUnban(\'' + b.id + '\')">remove</button></div>';
  }).join(''));
}
async function submitBan() {
  const body = {
    kind: $('#bKind').val(), node: $('#bNode').val().trim(), product: $('#bProduct').val().trim(),
    uuid: $('#bUuid').val().trim(), index: $('#bIndex').val().trim(), reason: $('#bReason').val().trim()
  };
  $('#bGo').prop('disabled', true);
  const r = await postJSON('/api/ban', body);
  $('#bGo').prop('disabled', false);
  toast(r.msg || (r.ok ? 'banned' : 'failed'), r.ok ? 'ok' : 'err');
  if (r.ok) {
    $('#bNode, #bProduct, #bUuid, #bIndex, #bReason').val('');
    loadBans(); refresh();
  }
}
async function doUnban(id) {
  const r = await postJSON('/api/unban', { id });
  toast(r.msg || 'removed', r.ok ? 'ok' : 'err'); loadBans(); refresh();
}
async function banApplied(id, applied) {
  const r = await postJSON('/api/ban-applied', { id, applied });
  toast(r.msg || 'updated', r.ok ? 'ok' : 'err'); loadBans(); refresh();
}

// ---- metrics dashboard (network) ----
let _metrics = null, _metricsWindow = 3600;
function openMetrics() { $('#metricsModal').addClass('on'); loadMetrics(_metricsWindow); }
function closeMetrics() { $('#metricsModal').removeClass('on'); }
function fmtBps(b) {
  const u = ['B/s', 'KB/s', 'MB/s', 'GB/s']; let i = 0; b = +b || 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return (b < 10 && i > 0 ? b.toFixed(1) : Math.round(b)) + ' ' + u[i];
}
async function loadMetrics(w) {
  _metricsWindow = w;
  $('#metricsModal .mrange button[data-w]').each(function () { $(this).toggleClass('on', +this.dataset.w === w); });
  $('#metricsBody').html('<div class="empty">loading…</div>');
  let d;
  try { d = await getJSON('/api/metrics?window=' + w); }
  catch (e) { d = { available: false, reason: 'request failed' }; }
  _metrics = d; renderMetrics(d);
}
function sparkline(tx, rx) {
  const W = 300, H = 64, p = 4, all = tx.concat(rx);
  if (!all.length) return '<div class="hint">no data in window</div>';
  const ts = all.map(a => a[0]), t0 = Math.min.apply(null, ts), t1 = Math.max.apply(null, ts);
  const max = Math.max(1, Math.max.apply(null, all.map(a => a[1])));
  const X = t => p + (t1 > t0 ? (t - t0) / (t1 - t0) : 0) * (W - 2 * p), Y = v => H - p - (v / max) * (H - 2 * p);
  const d = pts => pts.length ? 'M' + pts.map(a => X(a[0]).toFixed(1) + ' ' + Y(a[1]).toFixed(1)).join(' L ') : '';
  return '<svg class="spark" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">'
    + '<path class="l-tx" d="' + d(tx) + '"/><path class="l-rx" d="' + d(rx) + '"/></svg>'
    + '<div class="mc-leg"><span class="lt">↑ tx</span><span class="lr">↓ rx</span>'
    + '<span class="mut">peak ' + fmtBps(max) + '</span></div>';
}
function renderMetrics(d) {
  const $el = $('#metricsBody');
  if (!d || !d.available) {
    $el.html('<div class="hint">메트릭을 불러올 수 없습니다 — Prometheus 미연결 또는 수집 데이터 없음. (수집기가 안 돌아도 인스턴스는 정상 동작합니다.)'
      + (d && d.reason ? '<br><span class="mono" style="font-size:11px;color:var(--mut)">' + esc(d.reason) + '</span>' : '') + '</div>');
    return;
  }
  if (!d.instances || !d.instances.length) {
    $el.html('<div class="hint">아직 수집된 데이터가 없습니다 — 인스턴스 생성 후 몇 분 뒤 다시 확인하세요.</div>'); return;
  }
  $el.html('<div class="mcards">' + d.instances.map(m => {
    const lt = m.tx.length ? m.tx[m.tx.length - 1][1] : 0, lr = m.rx.length ? m.rx[m.rx.length - 1][1] : 0;
    return '<div class="mcard"><div class="mc-h"><span class="mc-n">' + esc(m.app) + '</span>'
      + (m.owner ? '<span class="mc-o">' + esc(m.owner) + '</span>' : '') + '</div>'
      + '<div class="mc-now">↑ ' + fmtBps(lt) + ' &middot; ↓ ' + fmtBps(lr) + '</div>'
      + sparkline(m.tx, m.rx) + '</div>';
  }).join('') + '</div>');
}
function exportMetrics(fmt) {
  if (!_metrics || !_metrics.available || !_metrics.instances || !_metrics.instances.length) { toast('no data to export', 'err'); return; }
  let blob, name;
  if (fmt === 'json') { blob = new Blob([JSON.stringify(_metrics, null, 2)], { type: 'application/json' }); name = 'isaac-metrics.json'; }
  else {
    const rows = [['timestamp_iso', 'app', 'owner', 'tx_bytes_per_s', 'rx_bytes_per_s']];
    _metrics.instances.forEach(m => {
      const rx = {}; m.rx.forEach(pt => rx[pt[0]] = pt[1]);
      m.tx.forEach(pt => rows.push([new Date(pt[0] * 1000).toISOString(), m.app, m.owner || '', pt[1], rx[pt[0]] != null ? rx[pt[0]] : '']));
    });
    const csv = rows.map(r => r.map(c => { c = String(c); return /[",\n]/.test(c) ? '"' + c.replace(/"/g, '""') + '"' : c; }).join(',')).join('\n');
    blob = new Blob([csv], { type: 'text/csv;charset=utf-8' }); name = 'isaac-metrics.csv';
  }
  // vanilla: programmatic download via a transient <a download> + object URL
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  toast('exported ' + name, 'ok');
}

// ---- scene load history (which USD stage stressed which GPU) ----
function openScenes() { $('#sceneModal').addClass('on'); loadScenes(); }
function closeScenes() { $('#sceneModal').removeClass('on'); }
const pct = v => v == null ? '-' : (+v).toFixed(0) + '%';
const gib = v => v == null ? '-' : ((+v) / 1024).toFixed(1) + ' GiB';
async function loadScenes() {
  let d;
  try { d = await getJSON('/api/scenes'); }
  catch (e) { d = { available: false }; }
  const $agg = $('#sceneAgg'), $ses = $('#sceneSessions');
  if (!d || !d.available) { $agg.html('<div class="hint">scene store unavailable</div>'); $ses.empty(); return; }
  $agg.html(d.byScene.length ? '<table class="ctab"><thead><tr><th>scene</th><th>GPU model</th>'
    + '<th class="num">runs</th><th class="num">util avg</th><th class="num">util p95</th>'
    + '<th class="num">util max</th><th class="num">NVENC max</th><th class="num">VRAM max</th></tr></thead><tbody>'
    + d.byScene.map(a => '<tr><td class="mono pn" title="' + esc(a.stage) + '">' + esc(a.stageShort) + '</td>'
      + '<td class="mono">' + esc(a.gpuModel) + '</td><td class="num mono">' + a.n + '</td>'
      + '<td class="num mono">' + pct(a.utilAvg) + '</td><td class="num mono">' + pct(a.utilP95) + '</td>'
      + '<td class="num mono">' + pct(a.utilMax) + '</td><td class="num mono">' + pct(a.encMax) + '</td>'
      + '<td class="num mono">' + gib(a.fbMaxMiB) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="hint">아직 기록 없음 — 6.0+ 이미지 인스턴스에서 USD를 열면 자동 기록됩니다.</div>');
  $ses.html(d.sessions.length ? '<table class="ctab"><thead><tr><th>scene</th><th>instance</th><th>GPU</th>'
    + '<th class="num">util avg/max</th><th class="num">VRAM max</th><th>start</th><th></th></tr></thead><tbody>'
    + d.sessions.slice(0, 30).map(s => {
      const st = s.stats || {};
      return '<tr><td class="mono pn" title="' + esc(s.stage) + '">' + esc(s.stageShort) + '</td>'
        + '<td class="mono">' + esc(s.instance) + '</td><td class="mono" style="font-size:11px">' + esc(s.gpuModel || '-') + '</td>'
        + '<td class="num mono">' + pct(st.utilAvg) + ' / ' + pct(st.utilMax) + '</td>'
        + '<td class="num mono">' + gib(st.fbMaxMiB) + '</td>'
        + '<td class="mono" style="font-size:11px">' + esc((s.start || '').replace('T', ' ').replace('Z', '')) + '</td>'
        + '<td>' + (s.open ? '<span class="tag">open</span>' : '') + '</td></tr>';
    }).join('') + '</tbody></table>'
    : '<div class="hint">no sessions</div>');
}

// ---- create instance modal ----
function openCreate() { $('#modal').addClass('on'); $('#mName').trigger('focus'); loadImages(); }
function closeCreate() { $('#modal').removeClass('on'); }
const shortImg = ref => esc((ref || '').split('/').pop());   // 10.38.../dt-saas/isaac-sim:6.0 -> isaac-sim:6.0
async function loadImages() {
  let d;
  try { d = await getJSON('/api/images'); }
  catch (e) { d = { available: false, reason: 'request failed' }; }
  if (!d || !d.available) {
    $('#mImage').html('<option value="">' + shortImg(d && d.default || 'default') + ' (default)</option>');
    $('#mImageHint').text('registry unreachable — default image only' + (d && d.reason ? ' · ' + d.reason : ''));
    return;
  }
  $('#mImage').html(d.images.map(i => '<option value="' + esc(i.image) + '"' + (i.image === d.default ? ' selected' : '')
    + ' title="' + esc(i.image) + '">' + shortImg(i.image) + (i.image === d.default ? ' · default' : '') + '</option>').join(''));
  $('#mImageHint').text(d.images.length + ' image(s) · source: ' + d.source);
}
async function submitCreate() {
  const name = $('#mName').val().trim();
  if (!name) { toast('enter a name', 'err'); return; }
  $('#mGo').prop('disabled', true);
  const body = { name, owner: $('#mOwner').val().trim(), description: $('#mDesc').val().trim(), image: $('#mImage').val() };
  const r = await postJSON('/api/create', body);
  $('#mGo').prop('disabled', false);
  if (r.ok) { toast(r.msg, 'ok'); $('#mName, #mOwner, #mDesc').val(''); closeCreate(); refresh(); }
  else toast(r.msg || 'create failed', 'err');
}
async function doDelete(name) {
  if (!confirm('Delete instance "' + name + '"? This removes its Deployment and Service.')) return;
  const r = await postJSON('/api/delete', { name });
  toast(r.msg || 'deleted', r.ok ? 'ok' : 'err'); refresh();
}
async function doPrune() {
  const r = await postJSON('/api/prune');
  toast(r.msg || 'pruned', r.ok ? 'ok' : 'err'); refresh();
}

// ---- boot ----
function tick() { clearInterval(timer); timer = setInterval(refresh, 10000); }
$(function () {
  $('#live').on('click', function () {
    auto = !auto;
    $('#live').toggleClass('off', !auto);
    $('#liveTxt').text(auto ? 'live · 10s' : 'paused');
    if (auto) tick(); else clearInterval(timer);
  });
  $(document).on('keydown', e => {
    if (e.key === 'Escape') { closeDrawer(); closeCreate(); closeBans(); closeMetrics(); closeScenes(); }
  });
  initGpop();
  refresh(); tick();
});
