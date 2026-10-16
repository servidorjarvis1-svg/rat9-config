/* ============================================================================
   diagram.js — el ratón como diagrama interactivo
   ----------------------------------------------------------------------------
   El SVG se genera con tools/gen-mouse-svg.py y trae 11 zonas, cada una con el
   uso HID REAL que reporta el firmware (`data-usage`, 1..11 segun
   schema.RAT9_BUTTONS).

   Tres cosas que hace y no son obvias:
   - Se le quita el <style> interno al SVG. Los colores y los estados los pone
     la hoja de la app, para que el ratón no sea un dibujo aparte con su propia
     paleta. Ademas, en SVG los atributos de presentacion (fill="...") tienen
     MENOS prioridad que una regla CSS, asi que la hoja puede repintarlo entero.
   - La seleccion es unidireccional de verdad: pulsar una zona avisa a la vista
     activa, y la vista puede pedir que se resalte una zona. Un solo estado.
   - Accesible por teclado: cada zona es un boton con tabindex y aria-label, y
     Enter/Espacio la activan. Escape quita la seleccion.
   ========================================================================= */

const Diagram = (() => {
  let svg = null;
  let zonas = [];
  let seleccion = null;
  const oyentes = new Set();

  /** Carga el SVG y lo deja interactivo dentro de `contenedor`. */
  async function cargar(contenedor) {
    const r = await fetch('/ui/diagram-mouse.svg');
    if (!r.ok) throw new Error('no he podido cargar el diagrama (HTTP ' + r.status + ')');

    const doc = new DOMParser().parseFromString(await r.text(), 'image/svg+xml');
    if (doc.querySelector('parsererror')) throw new Error('el SVG no es válido');
    svg = doc.documentElement;

    // sin tamano fijo: manda el CSS, y asi escala sin deformarse
    svg.removeAttribute('width');
    svg.removeAttribute('height');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    // la paleta la pone la app, no el dibujo
    svg.querySelector('style')?.remove();

    zonas = [...svg.querySelectorAll('.z')].map((el) => ({
      id: el.dataset.zone,
      uso: Number(el.dataset.usage),
      etiqueta: el.getAttribute('aria-label') || el.dataset.zone,
      el,
    }));

    for (const z of zonas) {
      z.el.setAttribute('tabindex', '0');
      z.el.addEventListener('click', () => seleccionar(z.id));
      z.el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          seleccionar(z.id);
        }
      });
      z.el.addEventListener('focus', () => emitir('foco', z.id));
    }

    svg.addEventListener('keydown', (e) => { if (e.key === 'Escape') seleccionar(null); });

    contenedor.replaceChildren(svg);
    emitir('cargado', null);
    return zonas;
  }

  function porId(id) { return zonas.find((z) => z.id === id) || null; }

  /** Selecciona una zona (o la quita con null) y avisa a quien escuche. */
  function seleccionar(id) {
    if (id && !porId(id)) return;
    seleccion = id;
    for (const z of zonas) z.el.classList.toggle('sel', z.id === id);
    svg?.classList.toggle('sel-mode', Boolean(id));
    emitir('seleccion', id);
  }

  function emitir(tipo, dato) {
    for (const fn of oyentes) fn(tipo, dato);
  }

  return {
    cargar,
    seleccionar,
    porId,
    get zonas() { return zonas; },
    get seleccion() { return seleccion; },
    /** Suscribe a 'cargado' | 'seleccion' | 'foco'. */
    on(fn) { oyentes.add(fn); return () => oyentes.delete(fn); },
  };
})();
