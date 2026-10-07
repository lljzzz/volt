from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QVBoxLayout, QWidget)

from core.hotkeys import combo_to_text
from core.timers import fmt_remaining
from . import icons
from .styles import ACCENT, GREEN
from .widgets import (Card, StatTile, ToggleSwitch, button, page_header,
                      repolish, small_label)


class DashboardPage(QWidget):
    def __init__(self, controller, on_change, navigate=None):
        super().__init__()
        self.ctrl = controller
        self.on_change = on_change
        self.navigate = navigate or (lambda name: None)
        self._rows = {}
        cfg = controller.config

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)

        head, right = page_header("Dashboard")
        self.subtitle = QLabel("", objectName="PageSubtitle")
        head.addWidget(self.subtitle)
        stop = button("Stop everything", "Danger", self._stop_all,
                      tip="Stops the clicker and every running macro")
        right.addWidget(stop)
        root.addLayout(head)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.t_click = StatTile("autoclicker", "Autoclicker")
        self.click_btn = button("Start", "Primary", self._toggle_clicker)
        self.click_btn.setFixedHeight(28)
        self.click_btn.setStyleSheet("padding: 3px 14px;")
        self.t_click.extra.addWidget(self.click_btn)
        self.t_macros = StatTile("macros", "Macros")
        self.t_snips = StatTile("snippets", "Snippets")
        self.t_clip = StatTile("clipboard", "Clipboard")
        self.t_timers = StatTile("timers", "Timers")
        self.t_notes = StatTile("notes", "Notes")
        tiles = [(self.t_click, "Autoclicker"), (self.t_macros, "Macros"),
                 (self.t_snips, "Snippets"), (self.t_clip, "Clipboard"),
                 (self.t_timers, "Timers"), (self.t_notes, "Notes")]
        for i, (tile, page) in enumerate(tiles):
            tile.clicked.connect(lambda p=page: self.navigate(p))
            grid.addWidget(tile, i // 3, i % 3)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        root.addLayout(grid)

        qc = Card("Quick controls", subtitle=(
            "Arm or disarm each tool's global hotkeys/capture without losing "
            "its settings - no more accidental clicker starts."))
        qgrid = QGridLayout()
        qgrid.setHorizontalSpacing(28)
        qgrid.setVerticalSpacing(10)
        self._qc_switches = []
        self._qc_defs = [
            ("Autoclicker hotkey",
             lambda: cfg["autoclicker"].get("armed", True),
             lambda v: cfg["autoclicker"].__setitem__("armed", v)),
            ("Macro hotkeys",
             lambda: cfg["settings"].get("macros_armed", True),
             lambda v: cfg["settings"].__setitem__("macros_armed", v)),
            ("Snippet expansion",
             lambda: cfg["snippets"].get("enabled", True),
             lambda v: cfg["snippets"].__setitem__("enabled", v)),
            ("Clipboard capture",
             lambda: cfg["clipboard"].get("enabled", True),
             lambda v: cfg["clipboard"].__setitem__("enabled", v)),
            ("Mouse nudge keys",
             lambda: cfg["nudge"].get("enabled", True),
             lambda v: cfg["nudge"].__setitem__("enabled", v)),
            ("Window nudge keys",
             lambda: cfg["nudge"].get("window", {}).get("enabled", True),
             lambda v: cfg["nudge"].setdefault("window", {}).__setitem__("enabled", v)),
            ("Color pick hotkey",
             lambda: cfg["picker"].get("enabled", True),
             lambda v: cfg["picker"].__setitem__("enabled", v)),
            ("Screen capture hotkey",
             lambda: cfg["capture"].get("enabled", True),
             lambda v: cfg["capture"].__setitem__("enabled", v)),
        ]
        for i, (label, get_fn, set_fn) in enumerate(self._qc_defs):
            row, col = i % 4, (i // 4) * 2
            qgrid.addWidget(small_label(label), row, col)
            sw = ToggleSwitch(get_fn())
            sw.toggled.connect(lambda v, sf=set_fn: self._qc_toggle(sf, v))
            qgrid.addWidget(sw, row, col + 1, alignment=Qt.AlignRight)
            self._qc_switches.append((sw, get_fn))
        qgrid.setColumnStretch(0, 1)
        qgrid.setColumnStretch(2, 1)
        qc.body().addLayout(qgrid)
        root.addWidget(qc)

        self.macros_card = Card("Macros")
        self.macros_card.header_row.addWidget(
            button("Manage", "GhostSmall", lambda: self.navigate("Macros")))
        self.macros_box = QVBoxLayout()
        self.macros_box.setSpacing(8)
        self.macros_card.body().addLayout(self.macros_box)
        root.addWidget(self.macros_card)
        root.addStretch()

        controller.clicker_state.connect(self._clicker_state)
        controller.clicker_count.connect(self._count)
        controller.macro_state.connect(self._macro_state)
        controller.snippet_fired.connect(lambda *_: self._refresh_tiles())
        if controller.clipboard:
            controller.clipboard.changed.connect(self._refresh_tiles)
        if controller.timers:
            controller.timers.updated.connect(self._refresh_timer_tile)
        if controller.notes:
            controller.notes.changed.connect(self._refresh_tiles)
        self._clicks = 0

    def refresh(self):
        panic = self.ctrl.config["settings"].get("panic_hotkey", [])
        pal = self.ctrl.config["settings"].get("palette_hotkey", [])
        bits = []
        if panic:
            bits.append(f"Panic stop: {combo_to_text(panic)}")
        if pal:
            bits.append(f"Palette: {combo_to_text(pal)}")
        self.subtitle.setText("   ·   ".join(bits))
        for sw, get_fn in self._qc_switches:
            sw.setChecked(get_fn())
        self._rebuild_macros()
        self._refresh_tiles()

    def sync(self):
        self.refresh()

    def _refresh_tiles(self):
        c = self.ctrl
        ac = c.config["autoclicker"]
        running = c.clicker.running
        rate = (f"{ac['delay_ms']} ms delay" if ac.get("mode") == "delay"
                else f"{ac['cps']}/{ac['unit']}")
        hk = combo_to_text(ac["hotkey"]) if ac.get("hotkey") else "no hotkey"
        if not ac.get("armed", True):
            hk += " (disarmed)"
        self.t_click.set("Running" if running else "Idle",
                         f"{rate} · {hk}", GREEN if running else None)
        self.t_click.value.setStyleSheet(f"color:{GREEN};" if running else "")
        self.click_btn.setText("Stop" if running else "Start")
        repolish(self.click_btn, "Running" if running else "Primary")

        macros = c.config["macros"]
        n_run = c.running_macros()
        self.t_macros.set(f"{n_run} running" if n_run else f"{len(macros)}",
                          "running now" if n_run else
                          ("macros saved" if len(macros) != 1 else "macro saved"),
                          GREEN if n_run else None)

        sn = c.config["snippets"]
        active = sum(1 for s in sn.get("items", []) if s.get("enabled", True))
        fired = c.snippets.expand_count
        state = "on" if sn.get("enabled", True) else "off"
        self.t_snips.set(f"{active}", f"active · engine {state}"
                         + (f" · {fired} expanded" if fired else ""),
                         ACCENT if sn.get("enabled", True) else None)

        cw = c.clipboard
        if cw:
            pins = sum(1 for e in cw.entries if e["pinned"])
            self.t_clip.set(f"{len(cw.entries)}",
                            f"entries · {pins} pinned · capture "
                            f"{'on' if cw.enabled else 'off'}")
        if c.notes:
            n = len(c.notes.items)
            self.t_notes.set(f"{n}", "note" if n == 1 else "notes")
        self._refresh_timer_tile()

    def _refresh_timer_tile(self):
        tm = self.ctrl.timers
        if not tm:
            return
        live = [t for t in tm.items if not t["paused"]]
        if live:
            nxt = min(live, key=tm.remaining)
            self.t_timers.set(fmt_remaining(tm.remaining(nxt)),
                              f"{nxt['label']} · {len(tm.items)} running", ACCENT)
        else:
            self.t_timers.set(f"{len(tm.items)}" if tm.items else "None",
                              "paused" if tm.items else "no timers running")

    def _rebuild_macros(self):
        while self.macros_box.count():
            item = self.macros_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rows.clear()
        macros = self.ctrl.config["macros"]
        if not macros:
            self.macros_box.addWidget(small_label(
                "No macros yet - record one in the Macros tab."))
            return
        for m in macros:
            self.macros_box.addWidget(self._macro_row(m))

    def _macro_row(self, m):
        mid = m["id"]
        row = QFrame(objectName="Row")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 8, 10, 8)
        lay.setSpacing(12)

        name = QLabel(m["name"])
        name.setStyleSheet("font-weight:700;")
        hk = combo_to_text(m["hotkey"]) if m["hotkey"] else "no hotkey"
        sub = QLabel(f"{hk} · {m.get('hotkey_mode', 'toggle')} · "
                     f"{len(m.get('actions', []))} actions", objectName="Muted")
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(name)
        col.addWidget(sub)
        lay.addLayout(col)
        lay.addStretch()

        en = ToggleSwitch(m.get("enabled", True))
        en.setToolTip("Hotkey enabled")
        en.toggled.connect(lambda v, mid=mid: self._toggle_enabled(mid, v))
        lay.addWidget(en)

        run = button("", "Primary", lambda _=False, mid=mid: self.ctrl.toggle_macro(mid))
        run.setFixedWidth(84)
        self._style_run(run, self.ctrl.is_macro_running(mid))
        run.setEnabled(bool(m.get("actions")))
        lay.addWidget(run)
        self._rows[mid] = run
        return row

    @staticmethod
    def _style_run(btn, running):
        btn.setText("Stop" if running else "Run")
        btn.setIcon(icons.icon("stop" if running else "play",
                               "#06140b" if running else "#1a0f08", 12))
        repolish(btn, "Running" if running else "Primary")

    def _qc_toggle(self, set_fn, value):
        set_fn(value)
        self.on_change()
        self.ctrl.refresh_hotkeys()
        self.ctrl.refresh_snippets()
        self._refresh_tiles()

    def _toggle_enabled(self, mid, value):
        m = self.ctrl.get_macro(mid)
        if m:
            m["enabled"] = value
            self.on_change()
            self.ctrl.refresh_hotkeys()

    def _toggle_clicker(self):
        self.ctrl.toggle_clicker()

    def _stop_all(self):
        self.ctrl.stop_clicker()
        self.ctrl.stop_all_macros()
        self.ctrl.toast.emit("Stopped everything")

    def _macro_state(self, mid, running):
        btn = self._rows.get(mid)
        if btn is not None:
            self._style_run(btn, running)
        self._refresh_tiles()

    def _clicker_state(self, running):
        self._refresh_tiles()

    def _count(self, n):
        if self.ctrl.clicker.running or n:
            self.t_click.sub.setText(f"{n:,} clicks this run")
