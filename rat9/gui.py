#!/usr/bin/env python3
"""
rat9-config — aplicación NATIVA GTK4 para el Mad Catz R.A.T.9 (0738:1709).

Usa la capa de protocolo verificada (rat9.protocol) y el parser .pr0 (rat9.pr0).

    python3 -m rat9.gui

Solo lectura funciona sin root; con las reglas udev (99-rat9.rules) tampoco
hace falta.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rat9 import pr0                                      # noqa: E402
from rat9.protocol import Rat9, Rat9Error, FACTORY_DPI, N_MODES  # noqa: E402
from rat9.schema import (RAT9_BUTTONS, HOTKEYS,            # noqa: E402
                         BLOCK_PRESS, BLOCK_REPEAT, BLOCK_RELEASE,
                         SCHEMA_PR0)

HERE = Path(__file__).parent

KEY_NAMES = {int(k): v for k, v in
             json.loads((HERE / "web" / "keys.json").read_text()).items()}
MOUSE_NAMES = {1: "Izquierdo", 2: "Derecho", 3: "Central",
               4: "X1 (atrás)", 5: "X2 (adelante)"}
BLOCK_LABELS = {BLOCK_PRESS: "Al pulsar", BLOCK_REPEAT: "Mantener (bucle)",
                BLOCK_RELEASE: "Al soltar"}


# =============================================================================
# Modelo
# =============================================================================

class Action:
    """Un evento de entrada dentro de una macro."""

    def __init__(self, device="keyboard", page=0x7, usage=0, value=1, time=0):
        self.device, self.page = device, page
        self.usage, self.value, self.time = usage, value, time

    def label(self) -> str:
        if self.device == "keyboard":
            return KEY_NAMES.get(self.usage, f"uso {self.usage}")
        if self.device == "hotkey":
            return HOTKEYS.get(self.usage, f"uso {self.usage}")
        if self.page == 1:
            return "Rueda " + ("arriba" if self.value == 1 else "abajo")
        return MOUSE_NAMES.get(self.usage, f"botón {self.usage}")

    def state(self) -> str:
        if self.device == "hotkey" or self.page == 1:
            return "—"
        return "▼ pulsar" if self.value else "▲ soltar"

    def to_node(self):
        if self.device == "keyboard":
            return pr0.key_action(self.usage, self.value == 1, self.time)
        if self.device == "hotkey":
            return pr0.hotkey_action(self.usage, self.time)
        if self.page == 1:
            return pr0.wheel_action(self.value == 1, self.time)
        return pr0.mouse_action(self.usage, self.value == 1, self.time)


class Block:
    def __init__(self, btype=BLOCK_PRESS):
        self.btype, self.closed, self.actions = btype, False, []


class Macro:
    def __init__(self, name="Nueva macro"):
        self.name = name
        self.blocks = [Block(BLOCK_PRESS), Block(BLOCK_REPEAT),
                       Block(BLOCK_RELEASE)]

    def count(self):
        return sum(len(b.actions) for b in self.blocks)

    def to_node(self, idx: int):
        blocks = [b for b in self.blocks if b.actions][:3]
        return pr0.command(
            self.name, f"{idx:08x}-0000-0000-0000-000000000000",
            *[pr0.block([a.to_node() for a in b.actions], b.btype, b.closed)
              for b in blocks])


# =============================================================================
# Helpers de widgets
# =============================================================================

def heading(text):
    return Gtk.Label(label=text, css_classes=["heading"], xalign=0)


def dim(text, wrap=False):
    return Gtk.Label(label=text, css_classes=["dim-label"], xalign=0,
                     wrap=wrap)


def gap(n=10):
    return Gtk.Separator(margin_top=n, margin_bottom=n)


def clear_box(box):
    """Gtk.Box no tiene remove_all(): hay que vaciarlo a mano."""
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def empty_row(text):
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    l = dim(text, wrap=True)
    l.set_margin_top(12); l.set_margin_bottom(12); l.set_margin_start(14)
    l.set_margin_end(14)
    row.set_child(l)
    return row


def draw_circle(area, cr, w, h, rgba):
    r = min(w, h) / 2 - 2
    cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
    cr.arc(w / 2, h / 2, r, 0, 2 * 3.14159265)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.22)
    cr.set_line_width(2)
    cr.arc(w / 2, h / 2, r, 0, 2 * 3.14159265)
    cr.stroke()


# =============================================================================
# Ventana
# =============================================================================

class Rat9Window(Adw.ApplicationWindow):
    TABS = ("Macros", "DPI", "Ajustes", "Perfil .pr0")

    def __init__(self, app):
        super().__init__(application=app, title="rat9-config")
        self.macros = []
        self.sel = 0
        self.blk = 0
        self.assigned = {}
        self.dev = None
        self.state = {"mode": None, "battery": None, "dpi": []}

        self._load_style()
        self._size_to_monitor()
        self._build()
        self._poll()
        GLib.timeout_add_seconds(4, self._tick)

    # ------------------------------------------------------------- estilo
    def _load_style(self):
        prov = Gtk.CssProvider()
        prov.load_from_path(str(HERE / "style.css"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _size_to_monitor(self):
        """Hyprland impone su propio tamano; pedimos que quepa el monitor."""
        try:
            g = Gdk.Display.get_default().get_primary_monitor().get_geometry()
            self.set_size_request(min(1200, g.width - 40),
                                  min(900, g.height - 40))
        except Exception:
            self.set_size_request(1200, 850)

    # ------------------------------------------------------------- layout
    def _build(self):
        self.add_css_class("rat9")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        head.set_margin_top(14); head.set_margin_bottom(4)
        head.set_margin_start(20); head.set_margin_end(20)
        head.append(Gtk.Label(label="rat9-config", css_classes=["app-title"]))
        self.status = Gtk.Label(label="Conectando…", css_classes=["status"],
                                xalign=1, hexpand=True)
        head.append(self.status)
        root.append(head)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.add_css_class("tabbar")
        bar.set_margin_start(14); bar.set_margin_end(14)
        bar.set_margin_bottom(8)
        self.tab_btns = []
        for name in self.TABS:
            b = Gtk.ToggleButton(label=name)
            b.connect("toggled", self._on_tab, name)
            bar.append(b)
            self.tab_btns.append(b)
        root.append(bar)

        self.stack = Gtk.Stack()
        self.stack.add_named(self._page_macros(), "Macros")
        self.stack.add_named(self._page_dpi(), "DPI")
        self.stack.add_named(self._page_settings(), "Ajustes")
        self.stack.add_named(self._page_raw(), "Perfil .pr0")
        self.stack.set_visible_child_name("Macros")
        self.tab_btns[0].set_active(True)
        root.append(self.stack)
        self.set_content(root)

    def _on_tab(self, btn, name):
        if not btn.get_active():
            return
        self.stack.set_visible_child_name(name)
        for b in self.tab_btns:
            if b is not btn and b.get_active():
                b.set_active(False)

    # ------------------------------------------------------------ macros
    def _page_macros(self):
        # Hyprland fuerza la ventana a ~949 px de ancho: tres columnas no
        # caben, asi que se apilan verticalmente con scroll.
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_start(12); outer.set_margin_end(12)
        outer.set_margin_bottom(12)
        outer.set_size_request(-1, -1)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.add_css_class("panel")
        left.set_margin_top(6); left.set_margin_bottom(6)
        left.set_margin_end(0)
        left.append(heading("Macros"))
        b = Gtk.Button(label="+ Nueva", css_classes=["suggested-action"])
        b.connect("clicked", lambda *_: self._new_macro())
        left.append(b)
        self.macro_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.macro_list.add_css_class("boxed-list")
        self.macro_list.connect("row-selected", self._on_row)
        sw = Gtk.ScrolledWindow(); sw.set_vexpand(True)
        sw.set_child(self.macro_list); left.append(sw)
        b2 = Gtk.Button(label="Renombrar")
        b2.connect("clicked", lambda *_: self._rename())
        left.append(b2)
        b3 = Gtk.Button(label="Eliminar", css_classes=["destructive-action"])
        b3.connect("clicked", lambda *_: self._del_macro())
        left.append(b3)
        outer.append(left)

        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mid.add_css_class("panel")
        mid.set_margin_top(6); mid.set_margin_bottom(6)
        mid.set_margin_start(0); mid.set_margin_end(0)
        mid.set_hexpand(True)
        self.cmd_title = heading("—")
        mid.append(self.cmd_title)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.append(dim("Bloque"))
        self.blk_combo = Gtk.DropDown.new_from_strings(
            list(BLOCK_LABELS.values()))
        self.blk_combo.connect("notify::selected", self._on_blk)
        row.append(self.blk_combo)
        self.closed_chk = Gtk.CheckButton(label="Cerrado")
        self.closed_chk.set_tooltip_text(
            "Termina la macro aunque sueltes antes")
        self.closed_chk.connect("toggled", self._on_closed)
        row.append(self.closed_chk)
        mid.append(row)

        add = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.kind = Gtk.DropDown.new_from_strings(
            ["Tecla", "Botón", "Rueda", "Multimedia"])
        self.kind.connect("notify::selected", lambda *_: self._fill_targets())
        add.append(self.kind)
        self.target = Gtk.DropDown()
        self.target.set_hexpand(True)
        add.append(self.target)
        self.state_sel = Gtk.DropDown.new_from_strings(["▼", "▲"])
        self.state_sel.set_tooltip_text("Pulsar / soltar")
        add.append(self.state_sel)
        self.delay = Gtk.SpinButton.new_with_range(0, 60000, 10)
        self.delay.set_tooltip_text("Espera antes de la acción (ms)")
        self.delay.set_value(0)
        add.append(self.delay)
        addb = Gtk.Button(label="Añadir", css_classes=["suggested-action"])
        addb.connect("clicked", lambda *_: self._add_action())
        add.append(addb)
        mid.append(add)

        self.act_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.act_list.add_css_class("boxed-list")
        sw2 = Gtk.ScrolledWindow(); sw2.set_vexpand(True)
        sw2.set_child(self.act_list); mid.append(sw2)
        self.act_hint = dim("", wrap=True)
        mid.append(self.act_hint)
        outer.append(mid)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right.add_css_class("panel")
        right.set_margin_top(6); right.set_margin_bottom(6)
        right.set_margin_start(0)
        right.append(heading("Botones del R.A.T.9"))
        self.btn_rows = {}
        for hid, name in RAT9_BUTTONS.items():
            r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            r.append(Gtk.Label(label=name, css_classes=["caption"],
                               xalign=0, hexpand=True))
            d = Gtk.DropDown()
            d.set_tooltip_text(f"Asignar macro a {name}")
            d.connect("notify::selected",
                      lambda w, h=hid: self._assign(h, w.get_selected()))
            r.append(d)
            self.btn_rows[hid] = d
            right.append(r)
        right.append(gap())
        right.append(heading("Perfil .pr0"))
        self.preview = Gtk.TextView()
        self.preview.set_monospace(True)
        self.preview.set_editable(False)
        pv = Gtk.ScrolledWindow(); pv.set_vexpand(True)
        pv.set_child(self.preview); right.append(pv)
        self.blocks_lbl = dim("", wrap=True)
        right.append(self.blocks_lbl)
        sb = Gtk.Button(label="Guardar .pr0", css_classes=["suggested-action"])
        sb.connect("clicked", lambda *_: self._save())
        right.append(sb)
        cb = Gtk.Button(label="Copiar")
        cb.connect("clicked", lambda *_: self._copy())
        right.append(cb)
        outer.append(right)
        scroller.set_child(outer)

        self._fill_targets()
        self._refresh_buttons()
        return scroller

    # ---------------------------------------------------------------- DPI
    def _page_dpi(self):
        wrap = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(18); box.set_margin_bottom(18)
        box.set_margin_start(20); box.set_margin_end(20)
        box.set_size_request(800, -1)
        box.append(heading("Resolución por perfil"))
        self.dpi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                               spacing=2)
        box.append(self.dpi_box)
        box.append(gap(14))
        box.append(dim("Cada uno de los cuatro perfiles guarda su propio DPI. "
                       "Valores de fábrica: 800 / 1600 / 3200 / 6400.",
                       wrap=True))
        wrap.set_child(box)
        return wrap

    # ------------------------------------------------------------ ajustes
    def _page_settings(self):
        wrap = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(18); box.set_margin_bottom(18)
        box.set_margin_start(20); box.set_margin_end(20)
        box.set_size_request(800, -1)

        box.append(heading("Batería"))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.batt_lbl = Gtk.Label(label="—", css_classes=["big-number"])
        row.append(self.batt_lbl)
        self.batt_bar = Gtk.LevelBar()
        self.batt_bar.set_min_value(0); self.batt_bar.set_max_value(100)
        self.batt_bar.set_hexpand(True)
        self.batt_bar.set_valign(Gtk.Align.CENTER)
        row.append(self.batt_bar)
        box.append(row)
        self.batt_hint = dim("")
        box.append(self.batt_hint)

        box.append(gap(14))
        box.append(heading("Iluminación"))
        led = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.led_btns = []
        for color, name in (("#ff3b30", "Rojo"), ("#ff9f0a", "Naranja"),
                            ("#ffd60a", "Amarillo"), ("#3ddc97", "Verde"),
                            ("#64d2ff", "Cian"), ("#4d8dff", "Azul"),
                            ("#bf5af2", "Morado"), ("#ffffff", "Blanco")):
            t = Gtk.ToggleButton()
            da = Gtk.DrawingArea()
            da.set_content_width(30); da.set_content_height(30)
            rgba = Gdk.RGBA(); rgba.parse(color)
            da.set_draw_func(draw_circle, rgba)
            t.set_child(da)
            t.set_tooltip_text(name)
            t.connect("toggled", self._on_led, name)
            led.append(t)
            self.led_btns.append(t)
        box.append(led)
        self.led_hint = dim("", wrap=True)
        box.append(self.led_hint)

        box.append(gap(14))
        box.append(heading("Velocidad"))
        r1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        r1.append(dim("DPI"))
        self.dpi_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 200, 6400, 100)
        self.dpi_scale.set_hexpand(True); self.dpi_scale.set_value(800)
        self.dpi_scale.connect("value-changed", lambda w: self.dpi_lbl.set_text(
            f"{int(w.get_value())} dpi"))
        r1.append(self.dpi_scale)
        self.dpi_lbl = dim("800 dpi")
        r1.append(self.dpi_lbl)
        box.append(r1)

        r2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        r2.append(dim("Sensibilidad"))
        self.sens_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 1, 30, 1)
        self.sens_scale.set_hexpand(True); self.sens_scale.set_value(15)
        self.sens_scale.connect("value-changed",
                                lambda w: self.sens_lbl.set_text(
                                    str(int(w.get_value()))))
        r2.append(self.sens_scale)
        self.sens_lbl = dim("15")
        r2.append(self.sens_lbl)
        box.append(r2)
        box.append(dim("El DPI se configura dentro del ratón; la sensibilidad "
                       "y el color quedan en el perfil.", wrap=True))

        box.append(gap(14))
        box.append(heading("Dispositivo"))
        self.info = dim("", wrap=True)
        self.info.set_selectable(True)
        box.append(self.info)
        wrap.set_child(box)
        return wrap

    # ----------------------------------------------------------- perfil
    def _page_raw(self):
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wrap.set_margin_top(18); wrap.set_margin_bottom(18)
        wrap.set_margin_start(20); wrap.set_margin_end(20)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, fn in (("Ver generado", self._show_generated),
                          ("Analizar texto", self._analyze),
                          ("Validar", self._validate),
                          ("Ver esquema", self._show_schema)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda *_, f=fn: f())
            row.append(b)
        wrap.append(row)
        self.raw_view = Gtk.TextView()
        self.raw_view.set_monospace(True)
        sw = Gtk.ScrolledWindow(); sw.set_vexpand(True)
        sw.set_child(self.raw_view); wrap.append(sw)
        self.raw_stats = dim("")
        wrap.append(self.raw_stats)
        return wrap

    # ------------------------------------------------------------- datos
    def _fill_targets(self):
        k = self.kind.get_selected()
        if k == 0:
            items = [(u, n) for u, n in KEY_NAMES.items()]
        elif k == 1:
            items = [(u, n) for u, n in MOUSE_NAMES.items()]
        elif k == 2:
            items = [(1, "Arriba"), (255, "Abajo")]
        else:
            items = [(u, n) for u, n in HOTKEYS.items()]
        self._items = items
        self.target.set_model(Gtk.StringList.new([n for _, n in items]))
        self.state_sel.set_sensitive(k in (0, 1))

    def _on_blk(self, *_):
        self.blk = self.blk_combo.get_selected()

    def _on_closed(self, *_):
        c = self.cur()
        if c:
            c.blocks[self.blk].closed = self.closed_chk.get_active()

    def _on_led(self, btn, name):
        if not btn.get_active():
            return
        for b in self.led_btns:
            if b is not btn:
                b.set_active(False)
        self.led_hint.set_text(
            f"Color: {name}. El protocolo del LED todavía no está "
            f"descifrado, así que solo queda guardado en el perfil.")

    def _assign(self, hid, idx):
        if idx == 0:
            self.assigned.pop(hid, None)
        elif idx - 1 < len(self.macros):
            self.assigned[hid] = self.macros[idx - 1]
        if hasattr(self, "info"):
            self._render_info()

    def _refresh_buttons(self):
        names = ["(sin asignar)"] + [m.name for m in self.macros]
        for hid, d in self.btn_rows.items():
            d.set_model(Gtk.StringList.new(names))
            m = self.assigned.get(hid)
            if m and m in self.macros:
                d.set_selected(self.macros.index(m) + 1)

    # ------------------------------------------------------------ macros
    def cur(self):
        if 0 <= self.sel < len(self.macros):
            return self.macros[self.sel]
        return None

    def _new_macro(self):
        self.macros.append(Macro(f"Macro {len(self.macros) + 1}"))
        self.sel = len(self.macros) - 1
        self._render()

    def _rename(self):
        c = self.cur()
        if not c:
            return
        dlg = Adw.MessageDialog.new(self, heading="Renombrar macro")
        entry = Gtk.Entry(text=c.name)
        dlg.set_extra_child(entry)
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("ok", "Cambiar")
        dlg.set_default_response("ok")
        dlg.set_close_response("cancel")

        def done(r):
            if r == "ok" and entry.get_text().strip():
                c.name = entry.get_text().strip()
                self._render()
            dlg.close()

        dlg.connect("response", done)
        dlg.present()

    def _del_macro(self):
        if not self.cur():
            return
        self.macros.pop(self.sel)
        self.assigned = {h: m for h, m in self.assigned.items()
                         if m in self.macros}
        self.sel = max(0, min(self.sel, len(self.macros) - 1))
        self._render()

    def _on_row(self, *_):
        row = self.macro_list.get_selected_row()
        if row:
            self.sel = row.get_index()
            self._render_actions()

    def _add_action(self):
        c = self.cur()
        if not c:
            return
        k = self.kind.get_selected()
        usage = self._items[self.target.get_selected()][0]
        time = int(self.delay.get_value())
        val = 1 if self.state_sel.get_selected() == 0 else 0
        if k == 0:
            a = Action("keyboard", 0x7, usage, val, time)
        elif k == 1:
            a = Action("mouse", 0x9, usage, val, time)
        elif k == 2:
            a = Action("mouse", 0x1, 0x38, usage, time)
        else:
            a = Action("hotkey", 0xC, usage, 1, time)
        c.blocks[self.blk].actions.append(a)
        self._render_actions()
        self._render_list()

    # ------------------------------------------------------------ render
    def _render(self):
        self._render_list()
        self._render_actions()
        self._refresh_buttons()
        self._regenerate()
        self._render_info()

    def _render_list(self):
        self.macro_list.remove_all()
        if not self.macros:
            self.macro_list.append(
                empty_row("Sin macros todavía. Pulsa «+ Nueva» para empezar."))
            return
        for m in self.macros:
            row = Gtk.ListBoxRow()
            h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            h.set_margin_top(8); h.set_margin_bottom(8)
            h.set_margin_start(12); h.set_margin_end(12)
            h.append(Gtk.Label(label=m.name, xalign=0, hexpand=True))
            h.append(dim(str(m.count())))
            row.set_child(h)
            self.macro_list.append(row)
        row = self.macro_list.get_row_at_index(self.sel)
        if row:
            self.macro_list.select_row(row)

    def _render_actions(self):
        c = self.cur()
        self.cmd_title.set_label(c.name if c else "Sin macro seleccionada")
        self.act_list.remove_all()
        if not c:
            self.act_list.append(empty_row(
                "Una macro es una secuencia de pulsaciones. Créala con "
                "«+ Nueva», añade acciones y asígnala a un botón."))
            self.act_hint.set_text("")
            return
        blk = c.blocks[self.blk]
        names = list(BLOCK_LABELS.values())
        self.blk_combo.set_selected(names.index(BLOCK_LABELS[blk.btype]))
        self.closed_chk.set_active(blk.closed)
        if not blk.actions:
            tips = {
                BLOCK_PRESS: "Se dispara al pulsar el botón. Es lo normal.",
                BLOCK_REPEAT: "Se repite en bucle mientras mantienes pulsado.",
                BLOCK_RELEASE: "Se dispara al soltar el botón.",
            }
            self.act_list.append(
                empty_row(f"{BLOCK_LABELS[blk.btype]}: sin acciones"))
            self.act_hint.set_text(tips[blk.btype])
            return
        for i, a in enumerate(blk.actions):
            row = Gtk.ListBoxRow()
            h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            h.set_margin_top(8); h.set_margin_bottom(8)
            h.set_margin_start(12); h.set_margin_end(8)
            h.append(dim(f"{i + 1}."))
            h.append(Gtk.Label(label=a.label(), xalign=0, hexpand=True))
            h.append(dim(a.state()))
            if a.time:
                h.append(dim(f"+{a.time} ms"))
            x = Gtk.Button(icon_name="user-trash-symbolic",
                           css_classes=["flat"])
            x.set_tooltip_text("Quitar")
            x.connect("clicked", lambda *_, n=i: self._del_action(n))
            h.append(x)
            row.set_child(h)
            self.act_list.append(row)
        self.act_hint.set_text(
            f"Bloque «{BLOCK_LABELS[blk.btype]}» · "
            f"{len(blk.actions)} acción(es).")

    def _del_action(self, idx):
        c = self.cur()
        if c and idx < len(c.blocks[self.blk].actions):
            c.blocks[self.blk].actions.pop(idx)
            self._render_actions()
            self._render_list()

    def _regenerate(self):
        xml = self._generated()
        self.preview.set_text(xml if xml else "(sin macros)")
        if xml:
            payload = 10 + len(xml) * 2
            self.blocks_lbl.set_text(
                f"{len(xml)} caracteres · {payload} bytes · "
                f"{-(-payload // 16)} bloques de 16 B")
        else:
            self.blocks_lbl.set_text("")

    def _generated(self):
        if not self.macros:
            return ""
        return pr0.build_profile([m.to_node(i + 1)
                                  for i, m in enumerate(self.macros)])

    # --------------------------------------------------------- hardware
    def _poll(self):
        try:
            if self.dev is None:
                self.dev = Rat9(claim=False)
            s = self.dev.status()
            self.state.update(mode=s.mode, battery=s.battery,
                              dpi=self.dev.all_dpi())
            pct = f"{s.battery}%" if s.battery is not None else "—"
            self.status.set_label(f"Perfil {s.mode or '—'}   ·   Batería {pct}")
        except Rat9Error as e:
            self.status.set_label("Sin acceso al ratón — ejecuta con sudo")
            self.status.set_tooltip_text(str(e))
        if hasattr(self, "batt_lbl"):
            self._render_battery()
        if hasattr(self, "dpi_box"):
            self._render_dpi()
        if hasattr(self, "info"):
            self._render_info()

    def _tick(self):
        self._poll()
        return True

    def _render_battery(self):
        pct = self.state.get("battery")
        self.batt_lbl.set_label(f"{pct}%" if pct is not None else "—")
        self.batt_bar.set_value(pct if pct is not None else 0)
        if pct is None:
            self.batt_hint.set_text("Sin lectura de batería.")
        elif pct <= 15:
            self.batt_hint.set_text("Batería baja: conéctalo al cargador.")
        elif pct <= 30:
            self.batt_hint.set_text("Batería limitada.")
        else:
            self.batt_hint.set_text("Batería correcta.")

    def _render_dpi(self):
        clear_box(self.dpi_box)
        data = self.state.get("dpi") or []
        if not data:
            self.dpi_box.append(empty_row("Sin acceso al ratón."))
            return
        by = {}
        for d in data:
            by.setdefault(d.mode, {})[d.axis] = d
        for mode in sorted(by):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
            row.set_margin_top(9); row.set_margin_bottom(9)
            act = self.state.get("mode") == mode
            lbl = Gtk.Label(
                label=f"Perfil {mode}" + ("   ● activo" if act else ""),
                xalign=0)
            lbl.set_size_request(200, -1)
            if act:
                lbl.add_css_class("accent")
            row.append(lbl)
            x = by[mode].get("X")
            y = by[mode].get("Y")
            row.append(dim(f"X: {x.dpi if x else '—'} dpi"))
            row.append(dim(f"Y: {y.dpi if y else '—'} dpi"))
            fab = FACTORY_DPI.get(mode)
            cur = x.dpi if x else None
            if cur is not None and fab is not None:
                t = Gtk.Label(label="fábrica" if cur == fab else "modificado")
                t.add_css_class("success" if cur == fab else "warning")
                t.set_xalign(0)
                row.append(t)
            self.dpi_box.append(row)

    def _render_info(self):
        lines = ["Mad Catz R.A.T.9 Wireless  ·  USB 0738:1709",
                 f"Perfil activo: {self.state.get('mode') or '—'}",
                 f"Macros creadas: {len(self.macros)}"]
        if self.assigned:
            lines.append("")
            lines.append("Asignaciones:")
            for hid, name in RAT9_BUTTONS.items():
                m = self.assigned.get(hid)
                lines.append(f"   {name:<22} → {m.name if m else '—'}")
        self.info.set_text("\n".join(lines))

    # --------------------------------------------------------- perfiles
    def _save(self):
        xml = self._generated()
        if not xml:
            return
        dlg = Gtk.FileDialog.new()
        dlg.set_initial_name("perfil.pr0")
        dlg.save(self, None, self._on_saved, xml)

    def _on_saved(self, dlg, result, xml):
        try:
            f = dlg.save_finish(result)
            f.write_bytes(xml.encode("utf-16-le"))
            self.raw_stats.set_text("✓ Guardado.")
        except Exception as e:
            self.raw_stats.set_text(f"✗ {e}")

    def _copy(self):
        xml = self._generated()
        if xml:
            self.get_clipboard().set(xml)
            self.blocks_lbl.set_text("Copiado al portapapeles.")

    def _txt(self):
        buf = self.raw_view.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def _show_generated(self):
        self.raw_view.set_text(self._generated())
        self._stats()

    def _show_schema(self):
        self.raw_view.set_text(SCHEMA_PR0)
        self._stats()

    def _analyze(self):
        txt = self._txt()
        if not txt.strip():
            return self.raw_stats.set_text("El texto está vacío.")
        try:
            root = pr0.parse(txt)
        except pr0.Pr0SyntaxError as e:
            return self.raw_stats.set_text(f"✗ {e}")
        cmds = root.first("commands")
        found = cmds.children if cmds else []
        self.macros = []
        for c in found:
            m = Macro(c.attrs.get("name", "Macro"))
            for i, bt in enumerate((BLOCK_PRESS, BLOCK_REPEAT,
                                    BLOCK_RELEASE)):
                blk = next((b for b in c.children
                            if b.attrs.get("type", BLOCK_PRESS) == bt), None)
                if not blk:
                    continue
                for a in blk.children:
                    if a.tag == "action":
                        m.blocks[i].actions.append(Action(
                            a.attrs.get("device", "keyboard"),
                            a.int_attr("page", 0), a.int_attr("usage", 0),
                            a.int_attr("value", 1), a.int_attr("time", 0)))
                m.blocks[i].closed = (blk.name == "macro")
            self.macros.append(m)
        self.assigned.clear()
        self.sel = 0
        self._render()
        self.raw_stats.set_text(
            f"✓ {len(found)} macro(s): "
            + ", ".join(c.attrs.get("name", "?") for c in found))

    def _validate(self):
        try:
            pr0.parse(self._txt())
            self.raw_stats.set_text("✓ Sintaxis válida.")
        except pr0.Pr0SyntaxError as e:
            self.raw_stats.set_text(f"✗ {e}")

    def _stats(self):
        t = self._txt()
        payload = 10 + len(t) * 2
        self.raw_stats.set_text(
            f"{len(t)} caracteres · {payload} bytes UTF-16 · "
            f"{-(-payload // 16)} bloques de 16 B")


class Rat9App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="dev.rat9.config",
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.win = None

    def do_activate(self):
        if self.win is None:
            self.win = Rat9Window(self)
        self.win.present()


def main():
    Adw.init()
    Rat9App().run(sys.argv)


if __name__ == "__main__":
    main()
