import json

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHeaderView,
                               QLabel, QMessageBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from core import config as cfg_store
from core.hotkeys import MODIFIERS, combo_to_text, normalize
from .hotkey_button import HotkeyButton
from .styles import AMBER, RED, TEXT_MUTED
from .widgets import Card, ToggleSwitch, button, flow_row, page_header


class SettingsPage(QWidget):
    def __init__(self, controller, on_change, window):
        super().__init__()
        self.ctrl = controller
        self.cfg = controller.config["settings"]
        self.on_change = on_change
        self.win = window

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)
        head, _right = page_header("Settings")
        root.addLayout(head)

        gen = Card("General")
        self._toggle_row(gen, "Launch on startup (opens quietly in the tray)",
                         "launch_on_startup", cb=window.apply_startup)
        self._toggle_row(gen, "Start minimized to the tray", "start_minimized")
        self._toggle_row(gen, "Closing the window keeps Volt in the tray",
                         "minimize_to_tray_on_close", default=True)
        self.ontop_sw = self._toggle_row(gen, "Keep Volt on top of other windows",
                                         "always_on_top", cb=window.set_always_on_top)
        self.awake_sw = self._toggle_row(gen, "Keep the PC awake while Volt runs",
                                         "keep_awake", cb=window.toggle_keep_awake)
        self._toggle_row(
            gen, "Hotkeys don't reach other apps", "suppress_hotkeys", default=True,
            cb=lambda v: self.ctrl.refresh_hotkeys(),
            tip="When on, the key that completes a Volt hotkey is swallowed - "
                "e.g. Ctrl+Y starts the clicker without also doing 'redo' in "
                "the app you're in. Windows only.")
        root.addWidget(gen)

        keys = Card("Global hotkeys")
        self.palette_btn = HotkeyButton(self.ctrl.hotkeys,
                                        self.cfg.get("palette_hotkey", []), hid="palette")
        self.palette_btn.captured.connect(lambda c: self._set_hotkey("palette_hotkey", c))
        keys.setting("Quick palette - search & run anything", self.palette_btn)
        self.panic_btn = HotkeyButton(self.ctrl.hotkeys, self.cfg.get("panic_hotkey", []),
                                      hid="panic")
        self.panic_btn.captured.connect(lambda c: self._set_hotkey("panic_hotkey", c))
        keys.setting("Panic - stop every clicker and macro", self.panic_btn)
        self._toggle_row(keys, "Palette: Enter pastes clipboard items / snippets "
                               "into the app you were in", "palette_paste", default=True,
                         tip="Off = Enter only copies. Shift+Enter always just copies.")
        root.addWidget(keys)
        root.addWidget(self._hotkeys_card())

        bk = Card("Backup", subtitle=(
            "Export everything - settings, macros, snippets, anchors, colors - "
            "to one JSON file, or restore from one."))
        bk.add(flow_row(button("Export settings…", "Ghost", self._export),
                        button("Import settings…", "Ghost", self._import),
                        button("Open data folder", "Ghost", self._open_data),
                        spacing=8))
        root.addWidget(bk)

        about = Card("About")
        self.about_lbl = QLabel("", objectName="Muted")
        self.about_lbl.setWordWrap(True)
        about.add(self.about_lbl)
        root.addWidget(about)
        root.addStretch()

        self._refresh_hotkey_table()
        self._refresh_about()

    def _hotkeys_card(self):
        c = Card("All hotkeys", subtitle=(
            "Every global hotkey with conflicts flagged. Double-click a row to "
            "jump to the tool that owns it."))
        self.hk_table = QTableWidget(0, 4)
        self.hk_table.setHorizontalHeaderLabels(["Tool", "Action", "Hotkey", "Status"])
        self.hk_table.verticalHeader().setVisible(False)
        self.hk_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.hk_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        h = self.hk_table.horizontalHeader()
        for i in (0, 1, 2):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        self.hk_table.setFixedHeight(250)
        self.hk_table.cellDoubleClicked.connect(self._jump_from_table)
        c.add(self.hk_table)
        return c

    def _collect_hotkeys(self):
        cfg = self.ctrl.config
        rows = []

        def add(tool, action, combo, active=True, page="Settings", loose=False):
            if combo:
                rows.append((tool, action, combo_to_text(combo),
                             [normalize(combo)], active, loose, page))

        ac = cfg["autoclicker"]
        add("Autoclicker", f"{ac.get('hotkey_mode', 'toggle').title()} clicker",
            ac.get("hotkey", []), ac.get("armed", True), "Autoclicker")
        add("Failsafe", "Panic (stop all)", cfg["settings"].get("panic_hotkey", []),
            loose=True)
        add("Palette", "Open palette", cfg["settings"].get("palette_hotkey", []))
        add("Clipboard", "Paste as plain text",
            cfg["clipboard"].get("paste_plain_hotkey", []), page="Clipboard")
        pk = cfg.get("picker", {})
        add("Picker", "Pick color", pk.get("hotkey", []), pk.get("enabled", True), "Picker")
        cap = cfg.get("capture", {})
        add("Capture", "Capture region", cap.get("hotkey", []),
            cap.get("enabled", True), "Capture")

        arrows = ["up", "down", "left", "right"]
        n = cfg.get("nudge", {})
        if n.get("modifiers"):
            rows.append(("Nudge", "Move cursor",
                         combo_to_text(n["modifiers"]) + " + Arrows",
                         [normalize(n["modifiers"] + [a]) for a in arrows],
                         n.get("enabled", True), True, "Nudge"))
        wn = n.get("window", {})
        if wn.get("modifiers"):
            rows.append(("Nudge", "Move/resize window",
                         combo_to_text(wn["modifiers"]) + " + Arrows",
                         [normalize(wn["modifiers"] + [a]) for a in arrows],
                         wn.get("enabled", True), True, "Nudge"))

        macros_armed = cfg["settings"].get("macros_armed", True)
        for m in cfg.get("macros", []):
            add("Macro", m.get("name", "?"), m.get("hotkey", []),
                macros_armed and m.get("enabled", True), "Macros")
        for a in n.get("anchors", []):
            add("Anchor", f"Jump to {a.get('name', '?')}", a.get("hotkey", []),
                page="Nudge")
        return rows

    @staticmethod
    def _fires_together(x, x_loose, y, y_loose) -> bool:
        if x == y:
            return False
        if x < y:
            extra = y - x
            return x_loose or not (extra & MODIFIERS)
        if y < x:
            extra = x - y
            return y_loose or not (extra & MODIFIERS)
        return False

    def _refresh_hotkey_table(self):
        rows = self._collect_hotkeys()
        self._table_pages = [r[6] for r in rows]
        self.hk_table.setRowCount(len(rows))
        for i, (tool, action, display, combos, active, loose, _page) in enumerate(rows):
            status, level = ("ok", 0) if active else ("inactive (disarmed/disabled)", 0)
            for j, (t2, a2, _d2, c2, act2, loose2, _p2) in enumerate(rows):
                if j == i or not (active and act2):
                    continue
                if any(x == y for x in combos for y in c2):
                    status, level = f"Conflict with {t2}: {a2}", 2
                    break
                if level < 1 and any(self._fires_together(x, loose, y, loose2)
                                     for x in combos for y in c2):
                    status, level = f"Overlaps {t2}: {a2} (both can fire)", 1
            for col, text in enumerate((tool, action, display, status)):
                it = QTableWidgetItem(text)
                if col == 3:
                    it.setForeground(QColor(RED if level == 2 else
                                            AMBER if level == 1 else TEXT_MUTED))
                self.hk_table.setItem(i, col, it)

    def _jump_from_table(self, row, _col):
        if 0 <= row < len(getattr(self, "_table_pages", [])):
            page = self._table_pages[row]
            if page != "Settings":
                self.win.navigate(page)

    def sync(self):
        self._refresh_hotkey_table()
        self.ontop_sw.setChecked(self.cfg.get("always_on_top", False))
        self.awake_sw.setChecked(self.cfg.get("keep_awake", False))
        self.palette_btn.setCombo(self.cfg.get("palette_hotkey", []))
        self.panic_btn.setCombo(self.cfg.get("panic_hotkey", []))
        self._refresh_about()

    def _refresh_about(self):
        self.about_lbl.setText(
            f"Volt {self.win.VERSION} - lightweight desktop multitool.\n"
            f"Data folder: {cfg_store.data_dir()}")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Volt settings", "volt_backup.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.ctrl.config, f, indent=2, ensure_ascii=False)
            self.ctrl.toast.emit("Settings exported")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Volt settings", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("that file isn't a Volt settings backup")
        except Exception as e:
            QMessageBox.warning(self, "Import failed", str(e))
            return
        resp = QMessageBox.question(
            self, "Import settings",
            "This replaces all current settings, macros and snippets with the "
            "backup, then restarts Volt. Continue?")
        if resp != QMessageBox.Yes:
            return
        merged = cfg_store._merge(cfg_store.DEFAULTS, data)
        self.ctrl.config.clear()
        self.ctrl.config.update(cfg_store._migrate(merged))
        self.win.restart()

    def _open_data(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(cfg_store.data_dir()))

    def _toggle_row(self, card, label, key, cb=None, default=False, tip=None):
        sw = ToggleSwitch(self.cfg.get(key, default))

        def handler(v):
            self.cfg[key] = v
            self.on_change()
            if cb:
                cb(v)
        sw.toggled.connect(handler)
        card.setting(label, sw, tip=tip)
        return sw

    def _set_hotkey(self, key, combo):
        self.cfg[key] = combo
        self.on_change()
        self.ctrl.refresh_hotkeys()
        self._refresh_hotkey_table()

    def set_keep_awake_state(self, v: bool):
        self.awake_sw.setChecked(bool(v))

    def set_on_top_state(self, v: bool):
        self.ontop_sw.setChecked(bool(v))
