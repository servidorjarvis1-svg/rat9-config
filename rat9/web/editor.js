/* rat9-config — editor de macros */
'use strict';
const $ = id => document.getElementById(id);
const get = u => fetch(u).then(r => r.json());
const post = (u, b) => fetch(u, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(b)
}).then(r => r.json());

let CAT = null, KEYS = null, MKEYS = null, HKEYS = null, FACTORY = {};
let cmds = [], sel = 0, dirty = false;

const DEV_PAGE = { key: 7, mousebtn: 9, wheel: 1, hotkey: 12 };
const KIND_LABEL = { key: 'Tecla', mousebtn: 'Ratón', wheel: 'Rueda',
                     hotkey: 'Multimedia' };

// ---------------------------------------------------------------- arranque
async function init() {
  [CAT, KEYS, MKEYS, HKEYS] = await Promise.all([
    get('/api/catalog'), get('/api/keys'),
    get('/api/buttons'), get('/api/hotkeys')
  ]);
  buildTargets();
  buildButtonGrid();
  renderList();
  refresh();
  setInterval(refresh, 5000);
}

function buildTargets() {
  const kind = $('kind');
  function fill(opts) {
    $('target').innerHTML = opts.map(o =>
      `<option value="${o.v}"${o.state ? '' : ' selected'}>${o.n}</option>`).join('');
  }
  function refreshTargets() {
    const k = kind.value;
    if (k === 'key')
      fill(Object.entries(MKEYS).map(([u, n]) => ({ v: u, n })));
    else if (k === 'mousebtn')
      fill([1, 2, 3, 4, 5].map(i => ({
        v: i, n: { 1: 'Izquierdo', 2: 'Derecho', 3: 'Central',
                   4: 'X1 (atrás)', 5: 'X2 (adelante)' }[i] })));
    else if (k === 'wheel')
      fill([{ v: 1, n: 'Arriba' }, { v: 255, n: 'Abajo' }]);
    else
      fill(Object.entries(HKEYS).map(([u, n]) => ({ v: u, n })));
    $('state').parentElement.style.display =
      (k === 'wheel' || k === 'hotkey') ? 'none' : '';
  }
  kind.onchange = refreshTargets;
  refreshTargets();
}

function buildButtonGrid() {
  $('btn').innerHTML = Object.entries(CAT.buttons).map(([h, n]) =>
    `<option value="${h}">${n}</option>`).join('');
  $('btngrid').innerHTML = Object.entries(CAT.buttons).map(([h, n]) =>
    `<div class="bcell" data-h="${h}">${n}</div>`).join('');
}

// ---------------------------------------------------------------- estado
async function refresh() {
  try {
    const s = await get('/api/state');
    if (s.connected) {
      $('dot').className = 'dot on';
      $('conn').textContent = 'RAT.9 conectado';
      $('prof').textContent = s.mode ?? '—';
      $('batt').textContent = s.battery != null ? s.battery + '%' : '—';
      if (s.dpi) {
        FACTORY = Object.fromEntries(s.dpi.map(d => [d.mode, d.factory]));
        renderDpi(s);
      }
    } else {
      $('dot').className = 'dot off';
      $('conn').textContent = 'sin acceso (¿sin root?)';
      renderDpi({});
    }
  } catch {
    $('dot').className = 'dot wait';
    $('conn').textContent = 'servidor caído';
  }
}

function renderDpi(s) {
  const tb = document.querySelector('#dpitable tbody');
  if (!s.dpi || !s.dpi.length) {
    tb.innerHTML = '<tr><td colspan="4" class="muted">sin acceso</td></tr>';
    return;
  }
  const rows = {};
  s.dpi.forEach(d => ((rows[d.mode] ||= { mode: d.mode })[d.axis] = d));
  tb.innerHTML = Object.values(rows).map(r => {
    const x = r.X || {}, y = r.Y || {};
    const chg = x.changed || y.changed;
    return `<tr><td>${r.mode}${s.mode === r.mode ? ' ●' : ''}</td>
      <td>${x.dpi ?? '—'}</td><td>${y.dpi ?? '—'}</td>
      <td><span class="tag ${chg ? 'changed' : 'factory'}">${
        chg ? 'modificado' : 'fábrica'}</span></td></tr>`;
  }).join('');
}

// ---------------------------------------------------------------- macros
function cur() { return cmds[sel]; }

function renderList() {
  $('cmdlist').innerHTML = cmds.length ? cmds.map((c, i) => {
    const n = c.blocks.reduce((a, b) => a + b.actions.length, 0);
    return `<li class="${i === sel ? 'sel' : ''}" data-i="${i}">
      ${esc(c.name)}<span class="cnt">${n}</span></li>`;
  }).join('') : '<li class="muted">Sin macros.</li>';
  $('cmdlist').querySelectorAll('li[data-i]').forEach(li => {
    li.onclick = () => { sel = +li.dataset.i; renderList(); renderActions(); };
  });
  const c = cur();
  $('cmdname').textContent = c ? '— ' + c.name : '';
  renderActions();
}

function renderActions() {
  const c = cur();
  const tb = document.querySelector('#acts tbody');
  if (!c) { tb.innerHTML = '<tr><td colspan="6" class="muted">Crea una macro.</td></tr>'; return; }
  const b = +$('blk').value;
  const blk = c.blocks[b] || { type: $('blk').value, closed: false, actions: [] };
  c.blocks[b] = blk;
  $('closed').checked = !!blk.closed;
  if (!blk.actions.length) {
    tb.innerHTML = '<tr><td colspan="6" class="muted">Sin acciones en este bloque.</td></tr>';
    return;
  }
  tb.innerHTML = blk.actions.map((a, i) => `
    <tr class="${a.paused ? 'paused' : ''}" data-i="${i}">
      <td>${i + 1}</td>
      <td>${KIND_LABEL[a.device === 'keyboard' ? 'key' :
                        a.device === 'hotkey' ? 'hotkey' :
                        a.page === 1 ? 'wheel' : 'mousebtn']}</td>
      <td>${labelOf(a)}</td>
      <td>${stateOf(a)}</td>
      <td>${a.time ? a.time + ' ms' : '—'}</td>
      <td><span class="x" data-del="${i}" title="Eliminar">✕</span></td>
    </tr>`).join('');
  tb.querySelectorAll('[data-del]').forEach(x => {
    x.onclick = () => {
      blk.actions.splice(+x.dataset.del, 1); dirty = true;
      renderActions(); renderList();
    };
  });
  tb.querySelectorAll('tr[data-i]').forEach(tr => {
    tr.ondblclick = () => { const a = blk.actions[+tr.dataset.i];
      a.paused = !a.paused; renderActions(); };
  });
}

function labelOf(a) {
  const u = a.usage;
  if (a.device === 'keyboard') return MKEYS[u] || ('uso ' + u);
  if (a.device === 'hotkey') return HKEYS[u] || ('uso ' + u);
  if (a.page === 1) return a.value === 1 ? 'Arriba' : 'Abajo';
  return { 1: 'Izquierdo', 2: 'Derecho', 3: 'Central',
           4: 'X1 (atrás)', 5: 'X2 (adelante)' }[u] || ('botón ' + u);
}
function stateOf(a) {
  if (a.device === 'hotkey') return '—';
  if (a.page === 1 && a.device === 'mouse') return '—';
  return a.value === 1 ? 'Pulsar' : 'Soltar';
}
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---------------------------------------------------------------- acciones
$('addact').onclick = () => {
  const c = cur(); if (!c) return;
  const kind = $('kind').value;
  const usage = +$('target').value;
  const time = +$('delay').value || 0;
  let a;
  if (kind === 'key')
    a = { device: 'keyboard', page: 7, usage, value: +$('state').value, time };
  else if (kind === 'mousebtn')
    a = { device: 'mouse', page: 9, usage, value: +$('state').value, time };
  else if (kind === 'wheel')
    a = { device: 'mouse', page: 1, usage: 0x38,
          value: $('target').value === '1' ? 1 : 0xFF, time };
  else
    a = { device: 'hotkey', page: 12, usage, value: 1, time };
  const b = +$('blk').value;
  (c.blocks[b] ||= { type: $('blk').value, closed: false, actions: [] }).actions.push(a);
  dirty = true; renderActions(); renderList();
};
$('blk').onchange = renderActions;
$('closed').onchange = () => {
  const c = cur(); if (!c) return;
  const b = +$('blk').value;
  (c.blocks[b] ||= { type: $('blk').value, closed: false, actions: [] })
    .closed = $('closed').checked;
  dirty = true;
};

$('add').onclick = () => {
  cmds.push({ name: 'Macro ' + (cmds.length + 1),
              blocks: [ { type: 'press', closed: false, actions: [] },
                        { type: 'repeat', closed: false, actions: [] },
                        { type: 'release', closed: false, actions: [] } ] });
  sel = cmds.length - 1; dirty = true; renderList();
};
$('ren').onclick = () => {
  const c = cur(); if (!c) return;
  const n = prompt('Nombre de la macro:', c.name);
  if (n) { c.name = n; dirty = true; renderList(); }
};
$('del').onclick = () => {
  if (!cur()) return;
  cmds.splice(sel, 1); sel = Math.max(0, sel - 1); dirty = true; renderList();
};
document.querySelectorAll('.bcell').forEach(c => {
  c.onclick = () => {
    document.querySelectorAll('.bcell').forEach(x => x.classList.remove('on'));
    c.classList.add('on');
    $('btn').value = c.dataset.h;
  };
});

// ---------------------------------------------------------------- salida
async function build() {
  const spec = { name: 'Linux', short: 'L',
                 commands: cmds.map((c, i) => ({
                   name: c.name, guid: guid(i + 1),
                   blocks: c.blocks.filter(b => b.actions.length)
                     .map(b => ({ type: b.type, closed: b.closed,
                                  actions: b.actions.filter(a => !a.paused) }))
                     .filter(b => b.actions.length)
                 })) };
  return post('/api/build', spec);
}
function guid(n) {
  const h = n.toString(16).padStart(8, '0') + '0000000000000000000000000000';
  return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
}

$('regen').onclick = async () => {
  if (!cmds.length) { msg('Crea al menos una macro.', 'err'); return; }
  const r = await build();
  if (r.error) return msg(r.error, 'err');
  $('preview').textContent = r.xml;
  msg(`${r.pack.block_count} bloques de 16 bytes listos.`, 'ok');
  dirty = false;
};
$('copy').onclick = () => {
  const t = $('preview').textContent;
  if (t) navigator.clipboard.writeText(t);
};
$('dl').onclick = () => {
  const t = $('preview').textContent;
  if (!t) return;
  const b = new Blob([t], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b); a.download = 'perfil.pr0'; a.click();
};
$('toRaw').onclick = async () => {
  const r = await build();
  if (r.error) return rawmsg(r.error, 'err');
  $('raw').value = r.xml; countRaw();
};
$('fromRaw').onclick = async () => {
  const xml = $('raw').value;
  if (!xml.trim()) return rawmsg('Vacío.', 'err');
  const r = await get('/api/parse?xml=' + encodeURIComponent(xml));
  if (r.error) return rawmsg(r.error, 'err');
  cmds = r.commands.map((c, i) => ({
    name: c.name, guid: c.guid,
    blocks: [0, 1, 2].map(bi => {
      const b = c.blocks.find(x => x.type === ['press','repeat','release'][bi]);
      return b || { type: ['press','repeat','release'][bi], closed: false,
                    actions: [] };
    })
  }));
  sel = 0; dirty = true; renderList();
  rawmsg(`${cmds.length} macros cargadas.`, 'ok');
};
$('schema').onclick = async () => {
  const s = await get('/api/schema');
  $('raw').value = s.schema_pr0; countRaw();
};
$('raw').oninput = countRaw;
function countRaw() {
  const t = $('raw').value;
  $('rc').textContent = t.length;
  $('rb').textContent = t.length * 2 + 10;
  $('rk').textContent = Math.ceil((t.length * 2 + 10) / 16);
}
const msg = (t, c) => { $('msg').textContent = t; $('msg').className = 'msg ' + c; };
const rawmsg = (t, c) => { $('rawmsg').textContent = t;
                            $('rawmsg').className = 'msg ' + c; };

// ---------------------------------------------------------------- tabs
document.querySelectorAll('.tab').forEach(t => {
  t.onclick = () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    ['macro', 'dpi', 'raw'].forEach(n =>
      $('tab-' + n).classList.toggle('hidden', n !== t.dataset.tab));
  };
});

init();
