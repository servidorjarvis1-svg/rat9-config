/* ============================================================================
   diagram.js — el ratón como diagrama interactivo
   ----------------------------------------------------------------------------
   Se dibuja en DOS capas, generadas del MISMO fichero fuente
   (tools/gen-mouse-svg.py), así que no pueden desincronizarse:

     1. `diagram-mouse.svg`   el esquema, con su propia paleta. La capa con la
        que se trabaja: geometría exacta y zonas clicables.
     2. `diagram-overlay.svg` la misma geometría, pero ya TRANSFORMADA a la caja
        donde ha caído el ratón dentro del render realista, y con paleta de
        plano translúcido. Se apila encima de la imagen y encaja sola.

   Pedirle al modelo de imagen que respetara nuestra geometría NO funcionó
   (probado dos veces: la mueve). Medir dónde ha caído SU ratón y ajustar la
   nuestra, sí. De ahí las dos capas en vez de una imagen sola.

   Cada zona lleva el uso HID REAL que reporta el firmware (`data-usage`, 1..11
   según schema.RAT9_BUTTONS).

   Tres cosas que hace y no son obvias:
   - Se le quita el <style> interno a cada SVG. La paleta la pone la app, para
     que el ratón no sea un dibujo aparte. Además, en SVG los atributos de
     presentación (fill="…") tienen MENOS prioridad que una regla CSS, así que
     la hoja puede repintarlo entero.
   - La selección es un único estado que se refleja en TODAS las capas a la vez.
   - Accesible por teclado: cada zona es un botón con tabindex y aria-label, y
     Enter/Espacio la activan. Escape quita la selección.
   ========================================================================= */

const Diagram = (() => {
  /** id -> { id, uso, etiqueta, els: [un elemento por capa] } */
  const zonas = new Map();
  let seleccion = null;
  const oyentes = new Set();

  function emitir(tipo, dato) {
    for (const fn of oyentes) fn(tipo, dato);
  }

  async function traer(ruta) {
    const r = await fetch(ruta);
    if (!r.ok) throw new Error(`${ruta} (HTTP ${r.status})`);
    const doc = new DOMParser().parseFromString(await r.text(), 'image/svg+xml');
    if (doc.querySelector('parsererror')) throw new Error(`${ruta}: SVG inválido`);
    const s = doc.documentElement;
    // sin tamaño fijo: manda el CSS, y así escala sin deformarse
    s.removeAttribute('width');
    s.removeAttribute('height');
    s.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    s.querySelector('style')?.remove();
    return s;
  }

  /** Engancha las zonas de un SVG al registro común. */
  function registrar(s) {
    for (const el of s.querySelectorAll('.z')) {
      const id = el.dataset.zone;
      let z = zonas.get(id);
      if (!z) {
        z = { id, uso: Number(el.dataset.usage),
              etiqueta: el.getAttribute('aria-label') || id, els: [] };
        zonas.set(id, z);
      }
      z.els.push(el);
      el.setAttribute('tabindex', '0');
      el.addEventListener('click', () => seleccionar(id));
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          seleccionar(id);
        }
      });
      el.addEventListener('focus', () => emitir('foco', id));
    }
    s.addEventListener('keydown', (e) => { if (e.key === 'Escape') seleccionar(null); });
  }

  /** Capa 1: el esquema. */
  async function cargar(contenedor) {
    const svg = await traer('/ui/diagram-mouse.svg');
    registrar(svg);
    contenedor.replaceChildren(svg);
    comprobarTamano(svg);
    emitir('cargado', null);
    return lista();
  }

  /** Capa 2: el plano translúcido que va ENCIMA del render. */
  async function cargarCapa(contenedor) {
    const capa = await traer('/ui/diagram-overlay.svg');
    registrar(capa);
    contenedor.replaceChildren(capa);
    // si ya había una zona seleccionada en el esquema, se refleja en la capa
    if (seleccion) {
      for (const el of zonas.get(seleccion)?.els || []) el.classList.add('sel');
      capa.classList.add('sel-mode');
    }
    return lista();
  }

  /** Guarda contra el fallo mudo que ya nos comimos una vez: si el SVG acaba
   *  con tamaño 0 (un choque de nombres de clase, una contención, un porcentaje
   *  sin resolver) el ratón simplemente NO APARECE y el navegador no dice nada. */
  function comprobarTamano(s) {
    requestAnimationFrame(() => {
      // Si el contenedor está OCULTO a propósito (la vista activa es otra), medir
      // 0x0 es lo correcto y no hay nada roto. Sin este filtro, arrancar la app en
      // la vista Giro escupía un error falso que hacía perder el tiempo buscando
      // un fallo inexistente.
      const caja = s.closest('.hidden') || (s.parentElement
        && s.parentElement.closest('.hidden'));
      if (caja) return;
      const r = s.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) {
        console.error('el diagrama ha quedado en '
          + `${Math.round(r.width)}x${Math.round(r.height)} px: no se verá. `
          + 'Revisa el CSS del contenedor (tamaño, contención, clases repetidas).');
      }
    });
  }

  function lista() { return [...zonas.values()]; }
  function porId(id) { return zonas.get(id) || null; }

  /** Selecciona una zona (o la quita con null) en TODAS las capas. */
  function seleccionar(id) {
    if (id && !zonas.has(id)) return;
    seleccion = id;
    for (const [zid, z] of zonas) {
      for (const el of z.els) el.classList.toggle('sel', zid === id);
    }
    for (const s of document.querySelectorAll('svg.mouse-diagram')) {
      s.classList.toggle('sel-mode', Boolean(id));
    }
    emitir('seleccion', id);
  }

  return {
    cargar, cargarCapa, seleccionar, porId,
    get zonas() { return lista(); },
    get seleccion() { return seleccion; },
    /** Suscribe a 'cargado' | 'seleccion' | 'foco'. */
    on(fn) { oyentes.add(fn); return () => oyentes.delete(fn); },
  };
})();
