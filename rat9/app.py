#!/usr/bin/env python3
"""
rat9.app — ventana nativa (GTK4 + libadwaita) con la UI web embebida.

Usa WebKitGTK 6.0 (WebView de la API GTK4) y sirve la interfaz + la API
HTTP en el mismo proceso, en un ThreadingHTTPServer aparte del bucle GTK:

  /usr/bin/python3 -m rat9.app            ventana normal
  /usr/bin/python3 -m rat9.app --max      maximizada
  /usr/bin/python3 -m rat9.app --win 900x600
  /usr/bin/python3 -m rat9.app --dev      consola web en stdout + devtools

Requiere el intérprete del sistema (el que tiene PyGObject gir):
  /usr/bin/python3 -> import gi OK
"""
from __future__ import annotations

import argparse
import sys
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
from gi.repository import WebKit, Adw, Gio, GLib, Gtk

from rat9.server import Handler   # Handler HTTP con /ui/ y /api/*


def parse_and_size(argv):
    p = argparse.ArgumentParser(prog='rat9')
    p.add_argument('--max', action='store_true', help='abrir maximizado')
    p.add_argument('--win', metavar='WxH', help='tamaño inicial, p.ej. 900x600')
    p.add_argument('--port', type=int, default=8766, help='puerto local (default 8766)')
    p.add_argument('--dev', action='store_true',
                   help='console.log en stdout + devtools al arrancar')
    # Abrir en una vista concreta: esquema, original, superpuesto o giro. Sirve para
    # comprobar una vista sin tener que pulsar el boton (y para dejar la app como
    # quieras al arrancar).
    p.add_argument('--vista', choices=['esquema', 'original', 'superpuesto', 'giro'],
                   help='vista con la que arranca la app')
    a = p.parse_args(argv)
    w, h = (1180, 780)
    if a.win:
        try:
            w, h = (int(x) for x in a.win.lower().split('x'))
        except ValueError:
            p.error('--win necesita formato WxH, p.ej. --win 900x600')
    return a, (w, h)


class Rat9App(Gtk.Application):
    def __init__(self, opts, size):
        super().__init__(application_id='es.rat9.config',
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.opts = opts
        self.size = size          # (w, h)
        self.win = None
        self.wv = None
        self.httpd = None
        self.port = None
        self._reloads = 0

    # ---- servidor local (hilo aparte; nunca toca el bucle GTK) -----------
    def start_server(self):
        # puertos: el pedido y los 9 siguientes
        srv, port = None, None
        from http.server import ThreadingHTTPServer

        class DaemonHTTPServer(ThreadingHTTPServer):
            # CRÍTICO: los request-threads no-daemon cuelgan el exit del
            # proceso si una petición queda atascada (p.ej. USB lento).
            daemon_threads = True
            allow_reuse_address = True

        for port in range(self.opts.port, self.opts.port + 10):
            try:
                srv = DaemonHTTPServer(('127.0.0.1', port), Handler)
                break
            except OSError:
                continue
        if srv is None:
            raise RuntimeError('no hay puerto libre para la UI')
        self.srv = srv
        self.port = port
        # el ThreadingHTTPServer vive en ESTE hilo y cada petición es otro hilo:
        # un read/write USB (o ratón no conectado) lento no congela a GTK.
        self.httpd = threading.Thread(target=self._serve, daemon=True)
        self.httpd.start()

    def _serve(self):
        try:
            self.srv.serve_forever()
        finally:
            self.srv.server_close()

    def stop_server(self):
        if getattr(self, 'srv', None) is not None:
            # shutdown() bloquea hasta que el hilo del serve_forever salga:
            # hacerlo desde el bucle GTK haría ticks congelados; hilo aparte.
            threading.Thread(target=self._shutdown_httpd, daemon=True).start()

    def _shutdown_httpd(self):
        self.srv.shutdown()
        self.srv.server_close()

    # ---- ciclo GTK -------------------------------------------------------
    def do_activate(self):
        self.start_server()
        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_title('rat9-config')
        w, h = self.size
        self.win.set_default_size(w, h)
        if self.opts.max:
            self.win.maximize()   # el compositor decide el rectángulo final

        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        tv.add_top_bar(hb)

        st = WebKit.Settings()
        st.set_allow_universal_access_from_file_urls(False)  # servimos por http
        st.set_enable_developer_extras(True)                 # menú → Inspeccionar
        st.set_enable_write_console_messages_to_stdout(bool(self.opts.dev))
        st.set_enable_page_cache(True)
        st.set_enable_html5_local_storage(True)
        st.set_enable_smooth_scrolling(True)
        st.set_enable_javascript_markup(True)
        st.set_javascript_can_open_windows_automatically(False)

        self.wv = WebKit.WebView(settings=st)
        # CLAVE para llenar y redimensionar con el tiling:
        self.wv.set_hexpand(True)
        self.wv.set_vexpand(True)
        self.wv.set_size_request(560, 360)   # mínimo razonable, no pisa al WM

        ucm = self.wv.get_user_content_manager()
        ucm.register_script_message_handler('rat9')  # web -> python
        ucm.connect('script-message-received', lambda u, v: self.on_message(v))

        self.wv.connect('load-changed', self.on_load_changed)
        self.wv.connect('load-failed', self.on_load_failed)
        self.wv.connect('decide-policy', self.on_decide_policy)
        self.wv.connect('web-process-terminated', self.on_webproc_dead)
        _url = 'http://127.0.0.1:%d/ui/index.html' % self.port
        if self.opts.vista:
            _url += '?vista=' + self.opts.vista
        self.wv.load_uri(_url)
        print('rat9-config: %s' % _url)

        tv.set_content(self.wv)
        self.win.set_content(tv)
        self.win.connect('close-request', self.on_close)
        self.win.present()

        if self.opts.dev:
            # devtools acoplados cuando la página esté lista
            self.wv.connect('ready-to-show', lambda *a:
                            self.wv.get_inspector().show())

    # ---- señales ---------------------------------------------------------
    def on_load_changed(self, wv, event):
        if event in (WebKit.LoadEvent.STARTED, WebKit.LoadEvent.FINISHED):
            print('load: %s %s' % (event.value_name, wv.get_uri()))

    def on_load_failed(self, wv, event, uri, error):
        print('load FAILED: %s (%s)' % (uri, error), file=sys.stderr)
        return False  # deja que WebKit muestre su página de error

    def on_decide_policy(self, wv, decision, dtype):
        """Links externos fuera de la app; todo lo local, dentro."""
        t = WebKit.PolicyDecisionType
        try:
            if dtype == t.RESPONSE:
                decision.use()
                return True
            action = decision.get_navigation_action()
            uri = action.get_request().get_uri()
        except Exception:
            decision.use()
            return True
        local = uri.startswith('http://127.0.0.1') or uri.startswith('http://localhost')
        if not local:
            print('enlace externo -> navegador:', uri)
            Gio.AppInfo.launch_default_for_uri_async(uri, None, None, None, None)
            decision.ignore()
            return True
        decision.use()
        return True

    def on_webproc_dead(self, wv, reason):
        # un crash del web process deja la ventana muerta: un reload una vez
        self._reloads += 1
        print('web process terminado (%s), reload #%d' % (reason.value_name, self._reloads),
              file=sys.stderr)
        if self._reloads <= 2:
            GLib.timeout_add(300, wv.reload)

    def on_message(self, value):
        try:
            print('web: %s' % str(value.to_string()))
        except Exception:
            pass

    def on_close(self, *a):
        self.stop_server()
        return False  # la ventana cierra igualmente

    def do_shutdown(self):
        # app.quit() (señales/Ctrl+C/pkill) pasa por aquí
        self.stop_server()
        Gtk.Application.do_shutdown(self)


def main(argv=None):
    opts, (w, h) = parse_and_size(sys.argv[1:] if argv is None else argv)
    app = Rat9App(opts, (w, h))
    # terminación limpia al recibir SIGINT (Ctrl+C del terminal) y SIGTERM
    # (pkill / cierre de sesión): por defecto PyGObject muere por la señal
    # y el app exit code queda -15/-2.
    import signal
    try:
        gi.require_version('GLibUnix', '2.0')
        from gi.repository import GLibUnix
        add_sig = GLibUnix.signal_add
    except (ValueError, ImportError):
        add_sig = GLib.unix_signal_add  # API deprecada pero funcional
    add_sig(GLib.PRIORITY_DEFAULT, signal.SIGINT, app.quit)
    add_sig(GLib.PRIORITY_DEFAULT, signal.SIGTERM, app.quit)
    try:
        return app.run([])   # [] : las opciones ya las comió argparse
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())