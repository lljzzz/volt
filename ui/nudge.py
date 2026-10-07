import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QGridLayout,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from core import winman
from core.hotkeys import combo_to_text
from .hotkey_button import HotkeyButton
from .widgets import (Card, ToggleSwitch, button, hint, page_header, small_label)

GRID = [
    ("◤", "Top-left"),   ("↑", "Top"),    ("◥", "Top-right"),
    ("←", "Left"),       ("●", "Center"), ("→", "Right"),
    ("◣", "Bottom-left"), ("↓", "Bottom"), ("◢", "Bottom-right"),
]


def builtin_points() -> dict[str, tuple[int, int]]:
    pts = winman.screen_points()
    if pts:
        return pts
    screen = (QGuiApplication.screenAt(QCursor.pos())
              or QGuiApplication.primaryScreen())
    g = screen.geometry()
    dpr = screen.devicePixelRatio()
    left, right = g.left() + 1, g.right() - 1
    top, bottom = g.top() + 1, g.bottom() - 1
    cx, cy = g.center().x(), g.center().y()
    pts = {
        "Top-left": (left, top), "Top": (cx, top), "Top-right": (right, top),
        "Left": (left, cy), "Center": (cx, cy), "Right": (right, cy),
        "Bottom-left": (left, bottom), "Bottom": (cx, bottom),
        "Bottom-right": (right, bottom),
    }
    return {k: (int(x * dpr), int(y * dpr)) for k, (x, y) in pts.items()}


class NudgePage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.cfg = controller.config["nudge"]
        self.on_change = on_change

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)
        head, right = page_header(
            "Nudge", "Pixel-exact control of the cursor and windows from the "
                     "keyboard, plus anchors you can teleport the cursor to.")
        self.pos_lbl = QLabel("", objectName="Kbd")
        self.pos_lbl.setToolTip("Live cursor position (physical pixels)")
        right.addWidget(self.pos_lbl)
        root.addLayout(head)

        root.addWidget(self._keys_card())
        root.addWidget(self._window_card())
        root.addWidget(self._anchors_card())
        root.addStretch()

        self._pos_timer = QTimer(self)
        self._pos_timer.setInterval(100)
        self._pos_timer.timeout.connect(self._tick_pos)

    def showEvent(self, e):
        super().showEvent(e)
        self._pos_timer.start()
        self._tick_pos()

    def hideEvent(self, e):
        self._pos_timer.stop()
        super().hideEvent(e)

    def _tick_pos(self):
        x, y = self.ctrl.nudge.position()
        self.pos_lbl.setText(f"x {x}   y {y}")

    def _mod_row(self, current, on_toggle):
        row = QHBoxLayout()
        row.setSpacing(12)
        checks = {}
        for key, label in [("ctrl", "Ctrl"), ("alt", "Alt"), ("cmd", "Win")]:
            cb = QCheckBox(label)
            cb.setChecked(key in current)
            cb.toggled.connect(lambda v, k=key: on_toggle(k, v))
            checks[key] = cb
            row.addWidget(cb)
        lbl = QLabel("", objectName="Accent")
        row.addWidget(lbl)
        return row, checks, lbl

    def _keys_card(self):
        c = Card("Mouse nudge", subtitle=(
            "Hold the modifiers + an arrow key to move the cursor by an exact "
            "step. Tap = one step, keep holding = glide, two arrows = "
            "diagonal. Add Shift for the fast step - even mid-glide."))

        self.enable_sw = ToggleSwitch(self.cfg.get("enabled", True))
        self.enable_sw.toggled.connect(lambda v: self._set("enabled", v))
        c.setting("Enabled", self.enable_sw)

        row, self.mod_checks, self.combo_lbl = self._mod_row(
            self.cfg.get("modifiers", []), self._mod_toggle)
        r = c.add_row(small_label("Modifiers"), stretch_last=True)
        r.addLayout(row)

        self.step = QSpinBox()
        self.step.setRange(1, 500)
        self.step.setSuffix(" px")
        self.step.setFixedWidth(100)
        self.step.setValue(self.cfg.get("step_px", 1))
        self.step.valueChanged.connect(lambda v: self._set("step_px", v))
        c.setting("Step", self.step)

        self.fast_step = QSpinBox()
        self.fast_step.setRange(1, 2000)
        self.fast_step.setSuffix(" px")
        self.fast_step.setFixedWidth(100)
        self.fast_step.setValue(self.cfg.get("fast_step_px", 10))
        self.fast_step.valueChanged.connect(lambda v: self._set("fast_step_px", v))
        self.fast_sw = ToggleSwitch(self.cfg.get("fast_enabled", True))
        self.fast_sw.toggled.connect(lambda v: self._set("fast_enabled", v))
        c.setting("Fast step (+ Shift)", self.fast_step, self.fast_sw)

        c.add(hint("If Ctrl+Alt+Arrow rotates your screen, that's the Intel "
                   "graphics driver hotkey - turn it off there or pick other "
                   "modifiers here."))
        self._update_combo_label()
        return c

    def _mod_toggle(self, key, value):
        self.cfg["modifiers"] = [k for k, cb in self.mod_checks.items() if cb.isChecked()]
        self._apply()
        self._update_combo_label()

    def _update_combo_label(self):
        mods = self.cfg.get("modifiers", [])
        self.combo_lbl.setText(f"{combo_to_text(mods)} + Arrows" if mods
                               else "pick at least one")

    def _set(self, key, value):
        self.cfg[key] = value
        self._apply()

    def _apply(self):
        self.on_change()
        self.ctrl.refresh_hotkeys()

    def _window_card(self):
        c = Card("Window nudge", subtitle=(
            "Same idea for the focused window: modifiers + arrows move it by "
            "an exact step. Hold Shift too and the arrows resize instead. "
            "Snap presets (halves, quarters, center) live in the palette."))
        wcfg = self.cfg.setdefault("window", {})
        if not winman.available():
            c.add(hint("Windows only - inactive on this platform."))
            return c

        self.wenable_sw = ToggleSwitch(wcfg.get("enabled", True))
        self.wenable_sw.toggled.connect(lambda v: self._wset("enabled", v))
        c.setting("Enabled", self.wenable_sw)

        row, self.wmod_checks, self.wcombo_lbl = self._mod_row(
            wcfg.get("modifiers", []), self._wmod_toggle)
        r = c.add_row(small_label("Modifiers"), stretch_last=True)
        r.addLayout(row)

        self.wstep = QSpinBox()
        self.wstep.setRange(1, 300)
        self.wstep.setSuffix(" px")
        self.wstep.setFixedWidth(100)
        self.wstep.setValue(wcfg.get("step_px", 20))
        self.wstep.valueChanged.connect(lambda v: self._wset("step_px", v))
        c.setting("Step", self.wstep)

        rs = ToggleSwitch(wcfg.get("resize_with_shift", True))
        rs.toggled.connect(lambda v: self._wset("resize_with_shift", v))
        c.setting("Shift + arrows resizes", rs)
        self._update_wcombo_label()
        return c

    def _wset(self, key, value):
        self.cfg.setdefault("window", {})[key] = value
        self._apply()

    def _wmod_toggle(self, key, value):
        mods = [k for k, cb in self.wmod_checks.items() if cb.isChecked()]
        self.cfg.setdefault("window", {})["modifiers"] = mods
        self._apply()
        self._update_wcombo_label()

    def _update_wcombo_label(self):
        mods = self.cfg.get("window", {}).get("modifiers", [])
        self.wcombo_lbl.setText(f"{combo_to_text(mods)} + Arrows" if mods
                                else "pick at least one")

    def sync(self):
        self.enable_sw.setChecked(self.cfg.get("enabled", True))
        if hasattr(self, "wenable_sw"):
            self.wenable_sw.setChecked(self.cfg.get("window", {}).get("enabled", True))

    def _anchors_card(self):
        c = Card("Anchors", subtitle=(
            "Teleport the cursor. The grid targets the screen the cursor is on. "
            "Custom anchors are saved spots with optional hotkeys - double-click "
            "a name or coordinate to edit it."))

        wrap = QHBoxLayout()
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, (glyph, name) in enumerate(GRID):
            b = QPushButton(glyph, objectName="GhostSmall")
            b.setFixedSize(42, 34)
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self._jump_builtin(n))
            grid.addWidget(b, i // 3, i % 3)
        wrap.addLayout(grid)
        wrap.addSpacing(18)

        col = QVBoxLayout()
        col.setSpacing(8)
        self.anchor_table = QTableWidget(0, 4)
        self.anchor_table.setHorizontalHeaderLabels(["Name", "X", "Y", "Hotkey"])
        self.anchor_table.verticalHeader().setVisible(False)
        self.anchor_table.setEditTriggers(QAbstractItemView.DoubleClicked
                                          | QAbstractItemView.EditKeyPressed)
        self.anchor_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        h = self.anchor_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2, 3):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.anchor_table.setFixedHeight(160)
        self.anchor_table.itemChanged.connect(self._anchor_edited)
        col.addWidget(self.anchor_table)

        btns = QHBoxLayout()
        self.save_btn = button("Save cursor in 3 s", "Ghost", self._save_delayed,
                               tip="Click, then move your mouse to the spot - "
                                   "the position is saved 3 seconds later.")
        btns.addWidget(self.save_btn)
        btns.addWidget(button("Jump", "Ghost", self._jump_selected))
        btns.addWidget(button("Delete", "Ghost", self._delete_selected))
        btns.addStretch()
        col.addLayout(btns)
        wrap.addLayout(col, 1)
        c.body().addLayout(wrap)

        self._refresh_anchors()
        return c

    def anchors(self) -> list[dict]:
        return self.cfg.setdefault("anchors", [])

    def _jump_builtin(self, name):
        x, y = builtin_points()[name]
        self.ctrl.nudge.jump(x, y)

    def _refresh_anchors(self):
        anchors = self.anchors()
        self.anchor_table.blockSignals(True)
        self.anchor_table.setRowCount(len(anchors))
        for i, a in enumerate(anchors):
            self.anchor_table.setItem(i, 0, QTableWidgetItem(a["name"]))
            for col, key in ((1, "x"), (2, "y")):
                it = QTableWidgetItem(str(a[key]))
                it.setTextAlignment(Qt.AlignCenter)
                self.anchor_table.setItem(i, col, it)
            hb = HotkeyButton(self.ctrl.hotkeys, a.get("hotkey", []),
                              hid=f"anchor_{a['id']}")
            hb.setObjectName("GhostSmall")
            hb.captured.connect(lambda combo, a=a: self._set_anchor_hotkey(a, combo))
            self.anchor_table.setCellWidget(i, 3, hb)
        self.anchor_table.blockSignals(False)

    def _anchor_edited(self, item):
        anchors = self.anchors()
        row, col = item.row(), item.column()
        if not 0 <= row < len(anchors):
            return
        a = anchors[row]
        if col == 0:
            if item.text().strip():
                a["name"] = item.text().strip()
        elif col in (1, 2):
            key = "x" if col == 1 else "y"
            try:
                a[key] = int(float(item.text().strip()))
            except ValueError:
                self.ctrl.toast.emit("Coordinates must be whole numbers")
        self._apply()
        self._refresh_anchors()

    def _save_delayed(self):
        if not self.save_btn.isEnabled():
            return
        self.save_btn.setEnabled(False)

        def tick(n):
            if n == 0:
                self.save_btn.setText("Save cursor in 3 s")
                self.save_btn.setEnabled(True)
                self._save_here()
                return
            self.save_btn.setText(f"Saving in {n}…")
            QTimer.singleShot(1000, lambda: tick(n - 1))

        tick(3)

    def _save_here(self):
        x, y = self.ctrl.nudge.position()
        name, ok = QInputDialog.getText(
            self, "New anchor", f"Name for ({x}, {y}):",
            text=f"Anchor {len(self.anchors()) + 1}")
        if not ok or not name.strip():
            return
        self.anchors().append({"id": uuid.uuid4().hex[:8], "name": name.strip(),
                               "x": x, "y": y, "hotkey": []})
        self._apply()
        self._refresh_anchors()

    def _selected_anchor(self) -> dict | None:
        row = self.anchor_table.currentRow()
        anchors = self.anchors()
        return anchors[row] if 0 <= row < len(anchors) else None

    def _jump_selected(self):
        a = self._selected_anchor()
        if a:
            self.ctrl.nudge.jump(a["x"], a["y"])

    def _delete_selected(self):
        a = self._selected_anchor()
        if a:
            self.anchors().remove(a)
            self._apply()
            self._refresh_anchors()

    def _set_anchor_hotkey(self, anchor, combo):
        anchor["hotkey"] = combo
        self._apply()
