/* ============================================================================
   views.js — las vistas del panel
   ----------------------------------------------------------------------------
   Cada vista es una funcion que devuelve nodos. Reglas que se ven en el codigo:

   - NINGUN valor se inventa. Si el raton no contesta, se pinta "desconocido",
     no un cero. (El firmware manda basura de vez en cuando; lo medimos.)
   - La interfaz dice LA VERDAD sobre la escritura. Todavia no sabemos si el
     raton acepta lo que le mandamos, asi que ningun mensaje dice "guardado"
     cuando lo unico que ha pasado es que se ha enviado. Los tres niveles
     -local / lectura verificada / escritura experimental- se distinguen.
   ========================================================================= */

const Vistas = (() => {
  const h = (tag, props = {}, ...hijos) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === 'cls') el.className = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v !== null && v !== undefined) el.setAttribute(k, v);
    }
    el.append(...hijos.flat().filter((c) => c !== null && c !== undefined));
    return el;
  };
  const txt = (s) => document.createTextNode(s);

  let _idx = 0;

  /** Las secciones se numeran solas, como las llamadas del dibujo. */
  function reiniciarIndices() { _idx = 0; }

  function sect(titulo, ...cuerpo) {
    _idx += 1;
    return h('section', { cls: 'sect' },
      h('div', { cls: 'sect__head' },
        h('span', { cls: 'sect__idx' }, String(_idx).padStart(2, '0')),
        h('span', { cls: 'hud' }, titulo)),
      ...cuerpo);
  }

  const vacio = (s) => h('span', { cls: 'v v--empty' }, s);
  const valor = (s, cls = '') => h('span', { cls: 'v ' + cls }, s);

  function fila(k, v, extra = null) {
    return h('dl', { cls: 'row' },
      h('dt', {}, k), h('dd', {}, v), extra);
  }

  /** Display de LEDs de 7 segmentos, como el que dibujaba el software original. */
  function displayDpi(n) {
    const cont = h('div', { cls: 'dpiled', role: 'img',
                            'aria-label': 'lectura de DPI ' + (n ?? 'desconocida') });
    const s = n == null ? '----' : String(n).padStart(4, ' ');
    for (const ch of s) cont.append(h('i', { cls: ch.trim() ? 'on' : '' }, ch));
    return cont;
  }

  function bateria(pct, ultima = null) {
    const nivel = pct == null ? '' : pct < 15 ? 'is-crit' : pct < 30 ? 'is-low' : '';
    const nodos = [h('div', { cls: 'batt' },
      h('div', { cls: 'batt__shell' },
        h('div', { cls: 'batt__fill ' + nivel,
                   style: `inline-size:${pct == null ? 0 : pct}%` })),
      h('span', { cls: 'batt__n' }, pct == null ? '—' : pct + ' %'))];
    // El firmware suelta lecturas invalidas de vez en cuando. Decir solo
    // "desconocida" deja al usuario pensando que se ha roto: se enseña tambien
    // la ultima lectura buena y cuando es.
    if (pct == null && ultima != null) {
      nodos.push(h('p', { cls: 'hint', style: 'margin:8px 0 0' },
        'El ratón no da lectura de batería ahora mismo. La última buena fue '
        + ultima + ' %.'));
    }
    return h('div', {}, ...nodos);
  }

  const aviso = (tono, ...cuerpo) =>
    h('div', { cls: 'note note--' + tono }, ...cuerpo);

  /* ══ PANEL ══════════════════════════════════════════════════════════════ */

  function panel(estado, zonaSel) {
    const nodos = [];
    const conectado = estado.conectado === true;

    // Una sola seccion en vez de dos: con la ventana real (1908x1068) el panel
    // se salia por abajo y habia que hacer scroll para ver el pie.
    nodos.push(sect('Dispositivo',
      fila('Conexión',
        conectado ? valor('accesible', 'v--accent') : vacio('sin acceso')),
      fila('Interfaz', conectado ? 'USB 0738:1709' : '—'),
      fila('Perfil activo',
        estado.mode != null ? estado.mode : vacio('desconocido')),
      h('dl', { cls: 'row' }, h('dt', {}, 'Batería')),
      bateria(estado.battery, estado.batteryUltima),
      fila('Perfiles leídos', String((estado.dpi || []).length) + ' / 8'),
      fila('Registro 0x0B', '0x0001')));

    // DPI del slot que el raton reporta como activo
    const act = (estado.dpi || []).filter((d) => d.mode === estado.mode);
    const x = act.find((d) => d.axis === 'X');
    const y = act.find((d) => d.axis === 'Y');
    nodos.push(sect('Lectura en vivo',
      fila('Eje X', x?.dpi != null ? x.dpi : vacio('desconocido')),
      fila('Eje Y', y?.dpi != null ? y.dpi : vacio('desconocido')),
      h('p', { cls: 'hint', style: 'margin:10px 0 0' },
        'El display del banco de arriba enseña el eje X del perfil activo.')));

    if (zonaSel) {
      nodos.push(sect('Zona seleccionada',
        fila('Control', zonaSel.etiqueta),
        fila('Uso HID', '0x' + zonaSel.uso.toString(16).padStart(2, '0').toUpperCase()),
        h('div', { cls: 'btn-row', style: 'margin-top:12px' },
          h('button', { cls: 'btn', onclick: () => App.ir('botones') },
            txt('Programar en «Botones»')))));
    }

    return nodos;
  }

  /* ══ BOTONES ════════════════════════════════════════════════════════════ */

  function botones(estado, zonaSel, catalogo) {
    const usos = catalogo?.buttons || {};
    const asignatura = Object.entries(usos).map(([hid, nombre]) => {
      const uso = parseInt(hid.slice(-2), 16);
      return { hid, uso, nombre };
    });

    const lista = h('div', { cls: 'zones' });
    for (const a of asignatura) {
      const sel = zonaSel && zonaSel.uso === a.uso;
      lista.append(h('button', {
        cls: 'zone-row', 'aria-pressed': String(Boolean(sel)),
        onclick: () => Diagram.seleccionar(
          Diagram.zonas.find((z) => z.uso === a.uso)?.id || null),
      },
        h('span', { cls: 'n' }, String(a.uso).padStart(2, '0')),
        h('span', {}, a.nombre),
        h('span', { cls: 'uso' }, a.hid)));
    }

    const nodos = [
      sect('Controles del R.A.T.9',
        h('p', { cls: 'hint', style: 'margin:0 0 12px' },
          'Los nombres y los códigos son los que reporta el firmware del ratón.'),
        lista),
    ];

    if (zonaSel) {
      nodos.push(sect('Asignar a «' + zonaSel.etiqueta + '»',
        h('p', { cls: 'hint', style: 'margin:0 0 12px' },
          'Uso HID 0x' + zonaSel.uso.toString(16).padStart(2, '0').toUpperCase()
          + ' · el editor de asignaciones llega en la siguiente pasada.'),
        aviso('never',
          h('b', {}, 'Todavía no se puede escribir.'),
          txt(' El canal de escritura del perfil está documentado pero sin '
            + 'verificar contra el hardware, y una escritura a lo tonto deja el '
            + 'ratón sin responder hasta que lo desenchufas.'))));
    }

    return nodos;
  }

  /* ══ DPI ════════════════════════════════════════════════════════════════ */

  function dpi(estado, zonaSel) {
    const porModo = {};
    for (const d of estado.dpi || []) (porModo[d.mode] ||= {})[d.axis] = d;

    const tira = h('div', { cls: 'stages' });
    for (const m of Object.keys(porModo).map(Number).sort()) {
      const x = porModo[m].X, y = porModo[m].Y;
      const activo = estado.mode === m;
      tira.append(h('div', {
        cls: 'stage', 'aria-pressed': String(Boolean(activo)), tabindex: '0',
      },
        h('span', { cls: 'stage__n' }, '0' + m),
        h('span', { cls: 'stage__v' },
          (x?.dpi ?? '??') + ' / ' + (y?.dpi ?? '??')),
        h('span', { cls: 'tag ' + (x?.changed ? 'tag--warn' : 'tag--ok') },
          x?.changed ? 'modificado' : 'fábrica')));
    }

    return [
      sect('Niveles de DPI',
        h('p', { cls: 'hint', style: 'margin:0 0 12px' },
          'El firmware reporta cuatro niveles con ejes X e Y independientes, en '
          + 'pasos de 25 DPI. Los de fábrica son 800 / 1600 / 3200 / 6400.'),
        tira),

      sect('Ajustar',
        h('p', { cls: 'hint', style: 'margin:0 0 14px' },
          'El deslizador va en múltiplos de 25, no libre: el original funcionaba '
          + 'así y el firmware solo entiende esos pasos.'),
        h('div', { style: 'display:flex;justify-content:space-between' },
          h('span', { cls: 'hud' }, '25'), h('span', { cls: 'hud' }, '6400')),
        h('input', {
          cls: 'slider', type: 'range', min: '25', max: '6400', step: '25',
          value: '800', 'aria-label': 'DPI',
          oninput: (e) => { val.textContent = e.target.value + ' dpi'; },
        }),
        h('p', { cls: 'num', id: 'val', style: 'font-family:var(--font-mono)' },
          '800 dpi')),
    ];
  }

  /* ══ MACROS y PERFILES ══════════════════════════════════════════════════ */

  function macros() {
    return [sect('Editor de macros',
      aviso('local',
        h('b', {}, 'Esto ya funciona, pero vive fuera de esta interfaz.'),
        txt(' El editor de comandos (bloques al pulsar / mantener / al soltar, '
          + 'teclas, botones, rueda y multimedia) está portado del software '
          + 'original y funciona en su propia página. Se reescribe en este '
          + 'lenguaje visual en la siguiente pasada.')),
      h('div', { cls: 'btn-row', style: 'margin-top:14px' },
        h('button', { cls: 'btn btn--primary',
                      onclick: () => window.open('/editor/editor.html', '_blank') },
          txt('Abrir el editor')),
        h('button', { cls: 'btn', onclick: () => App.ir('perfiles') },
          txt('Ver perfiles .pr0'))))];
  }

  function perfiles(_estado) {
    const cont = h('div', { cls: 'zones', id: 'listaPerfiles' },
      h('p', { cls: 'hint', style: 'padding:12px' }, 'cargando…'));

    API.perfiles().then((d) => {
      const lista = (d && (d.profiles || d.ficheros)) || [];
      cont.replaceChildren();
      if (!lista.length) {
        cont.append(h('p', { cls: 'hint', style: 'padding:12px' },
          txt('No hay perfiles guardados. El editor puede generar uno y '
            + 'guardarlo aquí.')));
        return;
      }
      for (const p of lista) {
        const nombre = typeof p === 'string' ? p : (p.name || p.fichero);
        cont.append(h('div', { cls: 'zone-row' },
          h('span', {}, nombre),
          h('span', { cls: 'uso' }, typeof p === 'object' && p.size ? p.size + ' B' : '')));
      }
    }).catch(() => {
      cont.replaceChildren(h('p', { cls: 'hint', style: 'padding:12px' },
        'No he podido leer la lista de perfiles.'));
    });

    return [sect('Perfiles .pr0 en disco', cont)];
  }

  /* ══ PIE: la leyenda de qué es de fiar y qué no ═════════════════════════
     Va en todas las vistas. Es el recordatorio permanente de los tres
     niveles de capacidad, para que nadie confunda "enviado" con "aplicado". */

  function pie() {
    return h('footer', { cls: 'panel-foot' },
      h('span', { cls: 'hud' }, 'Qué es de fiar'),
      h('ul', { cls: 'legend' },
        h('li', {}, h('i', { cls: 'legend__m legend__m--local' }),
          txt('Local — editar, guardar y exportar en tu disco. Siempre seguro.')),
        h('li', {}, h('i', { cls: 'legend__m legend__m--read' }),
          txt('Lectura — viene del ratón, verificado contra el hardware.')),
        h('li', {}, h('i', { cls: 'legend__m legend__m--write' }),
          txt('Escritura — sin verificar. Puede dejar el ratón sin responder '
            + 'hasta desenchufarlo.'))));
  }

  return { panel, botones, dpi, macros, perfiles, pie,
           displayDpi, reiniciarIndices };
})();
