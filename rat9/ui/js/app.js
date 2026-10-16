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

  /* ── figura del banco: esquema, producto o las dos capas ─────────────── */

  let figura = 'esquema';

  function pintarFigura() {
    const esEsquema = figura === 'esquema';
    const conCapa = figura === 'superpuesto';
    const conGiro = figura === 'giro';
    $('#deviceFrame').classList.toggle('hidden', !esEsquema);
    $('#deviceFigure').classList.toggle('hidden', esEsquema || conGiro);
    $('#deviceCapa').classList.toggle('hidden', !conCapa);
    $('#deviceGiro').classList.toggle('hidden', !conGiro);
    giroAuto(conGiro);
    // La leyenda numerada es del ESQUEMA: los números señalan zonas del dibujo,
    // y sobre la imagen no hay zonas. Enseñarla ahí sería un número sin nada a
    // lo que apuntar.
    $('#numb').classList.toggle('hidden', !esEsquema);
    for (const b of document.querySelectorAll('[data-figura]')) {
      b.setAttribute('aria-pressed', String(b.dataset.figura === figura));
    }
  }

  /* ── visor de GIRO ─────────────────────────────────────────────────────────
     24 fotogramas REALES del aparato, extraídos del instalador del software
     original. No es un modelo 3D inventado: es exactamente lo que hacía el
     software de Mad Catz, que tampoco era 3D sino una ruleta de sprites.

     OJO: los fotogramas NO están en el repositorio (son material gráfico ajeno).
     Los saca tools/preparar-giro.sh de una copia local del instalador; si no
     están, el botón no se ofrece y la app funciona igual. */
  const GIRO_N = 24;
  const GIRO_PX_FOTO = 14;      // 24 x 14 = 336 px de arrastre por vuelta
  const GIRO_MS = 220;          // una vuelta sola cada ~5 s
  let giroFoto = 0;
  let giroTimer = null;
  let giroArrastre = null;
  let giroListo = false;

  function giroPinta() {
    const n = String(giroFoto + 1).padStart(2, '0');
    $('#giroImg').src = 'assets/giro/' + n + '.webp';
    $('#giroCaja').setAttribute('aria-valuenow', String(giroFoto));
    $('#giroPista').style.inlineSize = ((giroFoto + 1) / GIRO_N * 100) + '%';
  }

  function giroGira(pasos) {
    giroFoto = ((giroFoto + pasos) % GIRO_N + GIRO_N) % GIRO_N;
    giroPinta();
  }

  function giroAuto(activo) {
    if (giroTimer) { clearInterval(giroTimer); giroTimer = null; }
    if (!activo || !giroListo) return;
    // Si el sistema pide menos movimiento, no gira sola: se queda quieta.
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    giroTimer = setInterval(() => { if (giroArrastre === null) giroGira(1); },
                            GIRO_MS);
  }

  async function comprobarGiro() {
    // ¿Están los fotogramas del giro? Si no, el botón no se ofrece: un botón que
    // lleva a una imagen rota es peor que no tener el botón.
    if (!$('#giroImg')) return;
    try {
      const r = await fetch('assets/giro/01.webp', { method: 'HEAD' });
      giroListo = r.ok;
    } catch { giroListo = false; }
    if (giroListo) {
      giroPinta();
    } else {
      $('#btnGiro').hidden = true;
      $('#deviceGiro').classList.add('hidden');
    }
  }

  function conectarGiro() {
    const caja = $('#giroCaja');
    if (!caja) return;
    caja.addEventListener('pointerdown', (e) => {
      giroArrastre = e.clientX;
      caja.setPointerCapture(e.pointerId);
    });
    caja.addEventListener('pointermove', (e) => {
      if (giroArrastre === null) return;
      const d = Math.round((giroArrastre - e.clientX) / GIRO_PX_FOTO);
      if (d !== 0) {
        giroGira(d);
        giroArrastre += d * GIRO_PX_FOTO;
      }
    });
    for (const ev of ['pointerup', 'pointercancel', 'pointerleave']) {
      caja.addEventListener(ev, () => { giroArrastre = null; });
    }
    caja.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') { giroGira(1); e.preventDefault(); }
      if (e.key === 'ArrowLeft') { giroGira(-1); e.preventDefault(); }
    });
  }

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
    const te = $('#titleEstado');
    if (te) {
      te.textContent = conectado
        ? 'accesible · perfil ' + (estado.mode ?? '?')
        : 'sin acceso';
    }
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
    Vistas.reiniciarIndices();
    const nodos = (RENDER[vista] || RENDER.panel)();
    $('#panel').replaceChildren(...nodos, Vistas.pie());
  }

  /** El display de DPI del banco: el eje X del perfil activo. */
  function pintarLectura() {
    const cont = $('#stageLed');
    if (!cont) return;
    const act = (estado.dpi || []).filter((d) => d.mode === estado.mode);
    const v = act.find((d) => d.axis === 'X')?.dpi ?? null;
    const s = v == null ? '----' : String(v).padStart(4, ' ');
    cont.replaceChildren(...[...s].map((ch) => {
      const i = document.createElement('i');
      if (ch.trim()) i.className = 'on';
      i.textContent = ch;
      return i;
    }));
    cont.setAttribute('aria-label', 'lectura de DPI ' + (v ?? 'desconocida'));
  }

  /** Cambia de seccion. */
  function ir(nueva) {
    if (!RENDER[nueva]) return;
    vista = nueva;
    // La figura se elige segun para que estas: el producto para MIRAR el
    // dispositivo, el esquema (con sus zonas clicables) para TRABAJAR en el.
    // El boton del banco lo puede cambiar; esto es solo el valor por defecto.
    figura = nueva === 'panel' ? 'original' : 'esquema';
    for (const b of document.querySelectorAll('.rail-item')) {
      const activa = b.dataset.view === nueva;
      if (activa) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    }
    pintarVista();
    pintarFigura();
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
    pintarLectura();
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
    for (const b of document.querySelectorAll('[data-figura]')) {
      b.addEventListener('click', () => { figura = b.dataset.figura; pintarFigura(); });
    }
    conectarGiro();
    await comprobarGiro();
    // Vista inicial por parametro: ?vista=giro. Va DESPUES de comprobarGiro() para
    // que el boton ya sepa si los fotogramas estan; si no estan, no se ofrece y esto
    // no hace nada raro. OJO: el valor definitivo se fija al final de arrancar(),
    // porque alli estaba la linea que pisaba esto (figura = 'original'|'esquema').
    const vista0 = ['esquema', 'original', 'superpuesto', 'giro']
      .includes(new URLSearchParams(location.search).get('vista'))
      ? new URLSearchParams(location.search).get('vista') : null;
    pintarFigura();

    Diagram.on((tipo, id) => {
      if (tipo !== 'seleccion') return;
      zonaSel = id ? Diagram.porId(id) : null;
      pintarVista();
    });

    try {
      const zonas = await Diagram.cargar($('#deviceFrame'));
      $('#deviceMsg')?.remove();
      pintarLeyenda(zonas);
      // la capa que va encima de la ilustración. Es un extra: si falla, el
      // esquema sigue en pie y la app no se queda sin diagrama.
      try {
        await Diagram.cargarCapa($('#deviceCapa'));
      } catch (e) {
        console.warn('sin capa para la ilustración:', e.message);
      }
      console.info('diagrama cargado:', zonas.length, 'zonas');
    } catch (e) {
      $('#deviceFrame').innerHTML =
        '<p class="hint">no he podido cargar el diagrama: ' + e.message + '</p>';
    }

    try { catalogo = await API.catalogo(); } catch { catalogo = null; }

    await refrescar();
    pintarVista();
    // Arrancamos en el Panel: su figura por defecto es el render del producto.
    // Si la URL trae ?vista=, MANDA ESO: sirve para abrir la app en una vista
    // concreta sin tener que pulsar el boton (y para poder comprobarla).
    figura = vista0 || (vista === 'panel' ? 'original' : 'esquema');
    pintarFigura();

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
