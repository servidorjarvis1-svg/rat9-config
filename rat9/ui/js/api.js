/* ============================================================================
   api.js — hablante con el servidor local
   ----------------------------------------------------------------------------
   Todo lo que la interfaz sabe del ratón pasa por aquí. Dos reglas:

   1. NUNCA se inventa un valor. Si el ratón no contesta, el valor es null y
      quien lo pinte tiene que decir "desconocido". El firmware suelta basura
      de vez en cuando (lo comprobamos: la batería dio un valor inválido en una
      de ocho lecturas), así que tratar un hueco como cero sería mentir.
   2. Nada de escritura silenciosa. Las funciones que tocan el ratón
      (`enviarPerfil`) devuelven lo que el servidor diga, y la interfaz lo
      cuenta tal cual: enviado ≠ confirmado.
   ========================================================================= */

const API = (() => {
  async function pedir(ruta, opciones) {
    const r = await fetch(ruta, opciones);
    const tipo = r.headers.get('content-type') || '';
    const cuerpo = tipo.includes('json') ? await r.json() : await r.text();
    if (!r.ok) {
      const detalle = (cuerpo && cuerpo.error) || r.statusText;
      throw new Error(`${ruta}: ${detalle} (HTTP ${r.status})`);
    }
    return cuerpo;
  }

  const cache = { estado: null, catalogo: null };

  /** Estado vacío explícito: nada de inventar ceros. */
  const SIN_ESTADO = (error = null) => ({
    conectado: false, mode: null, battery: null, dpi: [], error,
  });

  return {
    /** Estado en vivo del ratón. `conectado:false` es un estado válido, no un error. */
    async estado({ refrescar = false } = {}) {
      if (!refrescar && cache.estado) return cache.estado;
      try {
        const s = await pedir('/api/state');
        // Se normaliza aqui y no en cada vista: el JSON del servidor usa
        // `connected` y cada vista lo llamaba de una forma. Ese desajuste hizo
        // que la cabecera dijera "sin acceso" mientras el panel mostraba
        // bateria y DPI. Una sola puerta de entrada, un solo vocabulario.
        cache.estado = {
          conectado: s.connected === true,
          mode: s.mode ?? null,
          battery: s.battery ?? null,
          dpi: Array.isArray(s.dpi) ? s.dpi : [],
          error: null,
        };
        return cache.estado;
      } catch (e) {
        // el servidor puede estar caído: se devuelve un estado vacío explícito
        return SIN_ESTADO(String(e.message || e));
      }
    },

    async catalogo() {
      if (cache.catalogo) return cache.catalogo;
      cache.catalogo = await pedir('/api/catalog');
      return cache.catalogo;
    },

    async teclas() {
      return pedir('/api/keys');
    },

    /** Perfiles .pr0 guardados en el servidor. */
    async perfiles() {
      return pedir('/api/profiles');
    },

    /** Relee un .pr0 y devuelve su estructura (para comprobar el ida y vuelta). */
    async parsear(xml) {
      return pedir('/api/parse?xml=' + encodeURIComponent(xml));
    },

    /** Empaqueta sin escribir nada en el ratón. Siempre seguro. */
    async empaquetar(xml) {
      return pedir('/api/pack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ xml }),
      });
    },

    /**
     * ESCRIBE en el ratón. No está verificado y puede dejar el ratón sin
     * responder hasta desenchufarlo. Devuelve lo que responda el servidor;
     * que responda 200 NO significa que el ratón lo haya aceptado.
     */
    async enviarPerfil(xml, { confirmar = false } = {}) {
      return pedir('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ xml, confirmar }),
      });
    },

    invalidar() { cache.estado = null; },
  };
})();
