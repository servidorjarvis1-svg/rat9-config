/* ============================================================================
   app.js — arranque, navegacion y estado
   ----------------------------------------------------------------------------
   Un solo estado y un solo sentido del flujo:

       API  ->  App.estado  ->  vista activa  ->  panel + diagrama

   El diagrama avisa cuando se selecciona una zona; la vista activa decide que
   hacer con eso. Nada de dos copias del estado que se puedan desincronizar.
   ========================================================================= */

const App = (() => {
  const REFRESCO_MS = 3000;

  let estado = { conectado: false };
  let catalogo = null;
  let vista = 'panel';
  let zonaSel = null;
  let ultimaBateria = null;
  let temporizador = null;

  const $ = (s) => document.querySelector(s);

  /* ── avisos ───────────────────────────────────────────────────────────── */

  function aviso(texto, tono = '') {
    const t = document.createElement('div');
    t.className = 'toast' + (tono ? ' toast--' + tono : '');
    t.textContent = texto;
    $('#toasts').append(t);
    setTimeout(() => t.remove(), 4200);
  }

  /* ── cabecera y pie ───────────────────────────────────────────────────── */

  function pintarCabecera() {
    const conectado = estado.conectado === true;
    // Un solo texto de bateria para los dos sitios. Antes la cabecera ponia "—"
    // y el rail "?? %", y parecia que se contradecian.
    const bat = estado.battery != null ? estado.battery + ' %' : '—';
    $('#dot').className = 'dot ' + (conectado ? 'dot--on' : 'dot--off');
    $('#conn').textContent = conectado ? 'conectado' : 'sin acceso';
    $('#mode').textContent = estado.mode != null ? estado.mode : '—';
    $('#battHead').textContent = bat;
    $('#railFoot').textContent = conectado
      ? 'perfil ' + (estado.mode ?? '?') + ' · ' + bat
      : 'ratón no accesible';
  }

  /* ── vistas ───────────────────────────────────────────────────────────── */

  const RENDER = {
    panel:    () => Vistas.panel(estado, zonaSel),
    botones:  () => Vistas.botones(estado, zonaSel, catalogo),
    dpi:      () => Vistas.dpi(estado, zonaSel),
    macros:   () => Vistas.macros(),
    perfiles: () => Vistas.perfiles(estado),
  };

  function pintarVista() {
    const nodos = (RENDER[vista] || RENDER.panel)();
    $('#panel').replaceChildren(...nodos, Vistas.pie());
  }

  /** Cambia de seccion. */
  function ir(nueva) {
    if (!RENDER[nueva]) return;
    vista = nueva;
    for (const b of document.querySelectorAll('.rail-item')) {
      const activa = b.dataset.view === nueva;
      if (activa) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    }
    pintarVista();
  }

  /* ── ciclo de estado ──────────────────────────────────────────────────── */

  async function refrescar() {
    const antes = estado.conectado;
    estado = await API.estado({ refrescar: true });
    // La bateria se lee mal de vez en cuando (firmware). Se guarda la ultima
    // lectura buena para poder decir "ahora no, pero hace un momento sí".
    if (estado.battery != null) ultimaBateria = estado.battery;
    estado.batteryUltima = ultimaBateria;
    pintarCabecera();
    // solo se repinta la vista si el dato ha cambiado de verdad: repintar cada
    // 3 s sin motivo tiraria el foco del teclado y el scroll del panel
    const huella = JSON.stringify([estado.conectado, estado.mode,
                                   estado.battery, estado.dpi]);
    if (huella !== refrescar._ultima) {
      refrescar._ultima = huella;
      pintarVista();
    }
    if (antes !== estado.conectado && estado.conectado) aviso('Ratón accesible', 'ok');
    if (antes === true && estado.conectado === false) {
      aviso('Se ha perdido el acceso al ratón', 'warn');
    }
  }

  /** Leyenda de las llamadas: el número es el uso HID. Al pulsar una, se
   *  selecciona la zona — el mismo hilo que va del dibujo a las vistas. */
  function pintarLeyenda(zonas) {
    const ol = $('#numb');
    if (!ol) return;
    const filas = zonas.slice().sort((a, b) => a.uso - b.uso).map((z) => {
      const li = document.createElement('li');
      li.style.cursor = 'pointer';
      const b = document.createElement('b');
      b.textContent = String(z.uso).padStart(2, '0');
      li.append(b, document.createTextNode(z.etiqueta));
      li.addEventListener('click', () => Diagram.seleccionar(z.id));
      li.addEventListener('mouseenter', () => z.el.classList.add('sel'));
      li.addEventListener('mouseleave', () => {
        if (Diagram.seleccion !== z.id) z.el.classList.remove('sel');
      });
      return li;
    });
    ol.replaceChildren(...filas);
  }

  /* ── arranque ─────────────────────────────────────────────────────────── */

  async function arrancar() {
    for (const b of document.querySelectorAll('.rail-item')) {
      b.addEventListener('click', () => ir(b.dataset.view));
    }

    Diagram.on((tipo, id) => {
      if (tipo !== 'seleccion') return;
      zonaSel = id ? Diagram.porId(id) : null;
      pintarVista();
    });

    try {
      const zonas = await Diagram.cargar($('#deviceFrame'));
      $('#deviceMsg')?.remove();
      pintarLeyenda(zonas);
      console.info('diagrama cargado:', zonas.length, 'zonas');
    } catch (e) {
      $('#deviceFrame').innerHTML =
        '<p class="hint">no he podido cargar el diagrama: ' + e.message + '</p>';
    }

    try { catalogo = await API.catalogo(); } catch { catalogo = null; }

    await refrescar();
    pintarVista();

    temporizador = setInterval(refrescar, REFRESCO_MS);
    // con la pestaña oculta no se consulta: cero trabajo de fondo
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { clearInterval(temporizador); temporizador = null; }
      else if (!temporizador) { refrescar(); temporizador = setInterval(refrescar, REFRESCO_MS); }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', arrancar);
  } else {
    arrancar();
  }

  return { ir, aviso, get estado() { return estado; },
           get vista() { return vista; } };
})();
