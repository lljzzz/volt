from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QSpinBox,
                               QStackedWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from core import platform
from core.hotkeys import combo_to_text
from .hotkey_button import HotkeyButton
from .widgets import (Card, RefreshingCombo, Segmented, ToggleSwitch, button,
                      hint, page_header, repolish, small_label)


class AutoclickerPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.cfg = controller.config["autoclicker"]
        self.on_change = on_change

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)

        head, right = page_header(
            "Autoclicker", "Changes apply instantly, even while it's clicking.")
        self.status = QLabel("Idle", objectName="StatIdle")
        right.addWidget(self.status)
        self.start_btn = button("Start", "Primary", self._toggle)
        self.start_btn.setMinimumWidth(150)
        right.addWidget(self.start_btn)
        root.addLayout(head)

        root.addWidget(self._cadence_card())
        root.addWidget(self._behaviour_card())
        root.addWidget(self._sequence_card())
        root.addWidget(self._failsafe_card())
        root.addStretch()

        controller.clicker_state.connect(self._reflect_state)
        controller.clicker_count.connect(self._count)
        self._reflect_state(controller.clicker.running)

    def _cadence_card(self):
        c = Card("Cadence")

        self.mode = Segmented([("rate", "Rate"), ("delay", "Delay")], self.cfg["mode"])
        self.mode.changed.connect(self._on_mode_change)
        c.setting("Mode", self.mode)

        rate_page = QWidget()
        rl = QHBoxLayout(rate_page)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        self.cps = QSpinBox()
        self.cps.setRange(1, 100000)
        self.cps.setValue(self.cfg["cps"])
        self.cps.setFixedWidth(112)
        self.cps.valueChanged.connect(self._on_cps_change)
        self.unit = Segmented([("second", "Second"), ("minute", "Minute"),
                               ("hour", "Hour")], self.cfg["unit"])
        self.unit.changed.connect(self._on_unit_change)
        rl.addStretch()
        rl.addWidget(self.cps)
        rl.addWidget(small_label("clicks per"))
        rl.addWidget(self.unit)

        delay_page = QWidget()
        dl = QHBoxLayout(delay_page)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)
        dl.addStretch()
        dl.addWidget(small_label("one click every"))
        self.d_h = self._delay_box(99, " h")
        self.d_m = self._delay_box(59, " m")
        self.d_s = self._delay_box(59, " s")
        self.d_ms = self._delay_box(999, " ms")
        for box in (self.d_h, self.d_m, self.d_s, self.d_ms):
            dl.addWidget(box)
        self._set_delay_boxes(self.cfg.get("delay_ms", 40))

        self.cad_stack = QStackedWidget()
        self.cad_stack.addWidget(rate_page)
        self.cad_stack.addWidget(delay_page)
        self.cad_stack.setCurrentIndex(1 if self.cfg["mode"] == "delay" else 0)
        c.setting("Speed", self.cad_stack)

        self.hk = HotkeyButton(self.ctrl.hotkeys, self.cfg["hotkey"], hid="clicker")
        self.hk.captured.connect(self._set_hotkey)
        self.hk_mode = Segmented([("toggle", "Toggle"), ("hold", "Hold")],
                                 self.cfg["hotkey_mode"])
        self.hk_mode.changed.connect(self._set_hotkey_mode)
        c.setting("Hotkey", self.hk, self.hk_mode,
                  tip="Toggle: press to start, press again to stop. "
                      "Hold: clicks only while the combo is held.")

        self.button = Segmented([("left", "Left"), ("middle", "Middle"),
                                 ("right", "Right")], self.cfg["mouse_button"])
        self.button.changed.connect(lambda v: self._set("mouse_button", v))
        c.setting("Mouse button", self.button)
        return c

    def _delay_box(self, maximum, suffix):
        b = QSpinBox()
        b.setRange(0, maximum)
        b.setSuffix(suffix)
        b.setFixedWidth(96)
        b.valueChanged.connect(self._on_delay_change)
        return b

    def _read_delay_ms(self) -> int:
        return (self.d_h.value() * 3_600_000 + self.d_m.value() * 60_000 +
                self.d_s.value() * 1_000 + self.d_ms.value())

    def _set_delay_boxes(self, total_ms: int):
        total_ms = max(0, int(total_ms))
        h, rem = divmod(total_ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1_000)
        for box, val in ((self.d_h, h), (self.d_m, m),
                         (self.d_s, s), (self.d_ms, ms)):
            box.blockSignals(True)
            box.setValue(min(val, box.maximum()))
            box.blockSignals(False)

    def _rate_to_ms(self) -> int:
        factor = {"second": 1.0, "minute": 60.0, "hour": 3600.0}[self.cfg["unit"]]
        cps = max(self.cfg["cps"], 1)
        return max(1, round(factor / cps * 1000))

    @staticmethod
    def _ms_to_rate(total_ms: int):
        total_ms = max(1, total_ms)
        cps = 1000.0 / total_ms
        if cps >= 1:
            return max(1, round(cps)), "second"
        if cps * 60 >= 1:
            return max(1, round(cps * 60)), "minute"
        return max(1, round(cps * 3600)), "hour"

    def _on_cps_change(self, v):
        self.cfg["cps"] = v
        self.on_change()

    def _on_unit_change(self, v):
        self.cfg["unit"] = v
        self.on_change()

    def _on_delay_change(self, _=None):
        self.cfg["delay_ms"] = max(1, self._read_delay_ms())
        self.on_change()

    def _on_mode_change(self, mode):
        if mode == self.cfg["mode"]:
            return
        if mode == "delay":
            self._set_delay_boxes(self._rate_to_ms())
            self.cfg["delay_ms"] = max(1, self._read_delay_ms())
            self.cad_stack.setCurrentIndex(1)
        else:
            cps, unit = self._ms_to_rate(self._read_delay_ms())
            self.cps.blockSignals(True)
            self.cps.setValue(min(cps, self.cps.maximum()))
            self.cps.blockSignals(False)
            self.unit.setValue(unit)
            self.cfg["cps"], self.cfg["unit"] = cps, unit
            self.cad_stack.setCurrentIndex(0)
        self.cfg["mode"] = mode
        self.on_change()

    @staticmethod
    def _spin(lo, hi, value, suffix="", width=None):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setSuffix(suffix)
        s.setValue(value)
        if width:
            s.setFixedWidth(width)
        return s

    def _behaviour_card(self):
        c = Card("Click behaviour")

        self.duration = self._spin(0, 100, self.cfg["click_duration"], " %", 96)
        self.duration.valueChanged.connect(lambda v: self._set("click_duration", v))
        c.setting("Click duration (hold per click)", self.duration,
                  tip="How long each click is held down. 100% = 50 ms, "
                      "capped so it never eats the interval.")

        self.var_pct = self._spin(0, 90, self.cfg["speed_variation_pct"], " %", 96)
        self.var_pct.valueChanged.connect(lambda v: self._set("speed_variation_pct", v))
        self.var_sw = ToggleSwitch(self.cfg["speed_variation"])
        self.var_sw.toggled.connect(lambda v: self._set("speed_variation", v))
        c.setting("Speed variation (humanize)", self.var_pct, self.var_sw,
                  tip="Randomises each interval by up to this much; the "
                      "average stays on target.")

        self.shake_px = self._spin(1, 50, self.cfg["mouse_shake_px"], " px", 96)
        self.shake_px.valueChanged.connect(lambda v: self._set("mouse_shake_px", v))
        self.shake_sw = ToggleSwitch(self.cfg["mouse_shake"])
        self.shake_sw.toggled.connect(lambda v: self._set("mouse_shake", v))
        c.setting("Mouse shake", self.shake_px, self.shake_sw,
                  tip="Jitters the cursor around its spot each click (it "
                      "never drifts away).")

        self.dc_ms = self._spin(1, 1000, self.cfg["double_click_ms"], " ms", 96)
        self.dc_ms.valueChanged.connect(lambda v: self._set("double_click_ms", v))
        self.dc_sw = ToggleSwitch(self.cfg["double_click"])
        self.dc_sw.toggled.connect(lambda v: self._set("double_click", v))
        c.setting("Double click", self.dc_ms, self.dc_sw)

        self.limit_val = self._spin(1, 10000000, self.cfg["limit_value"], "", 120)
        self.limit_val.valueChanged.connect(lambda v: self._set("limit_value", v))
        self.limit_type = Segmented([("click", "Clicks"), ("time", "Seconds")],
                                    self.cfg["limit_type"])
        self.limit_type.changed.connect(lambda v: self._set("limit_type", v))
        self.limit_sw = ToggleSwitch(self.cfg["limit_enabled"])
        self.limit_sw.toggled.connect(lambda v: self._set("limit_enabled", v))
        c.setting("Stop after", self.limit_val, self.limit_type, self.limit_sw)
        return c

    def _failsafe_card(self):
        c = Card("Failsafes", subtitle=(
            "The panic hotkey (Settings) always stops everything. These add "
            "guard rails on top."))

        self.armed_sw = ToggleSwitch(self.cfg.get("armed", True))
        self.armed_sw.toggled.connect(self._set_armed)
        c.setting("Hotkey armed (off = the global hotkey does nothing)", self.armed_sw)

        self.focus_sw = ToggleSwitch(self.cfg.get("stop_on_focus_change", False))
        self.focus_sw.toggled.connect(lambda v: self._set("stop_on_focus_change", v))
        c.setting("Stop when focus changes (alt-tab kills it)", self.focus_sw)

        self.block_edit = QLineEdit(self.cfg.get("window_blocklist", ""))
        self.block_edit.setPlaceholderText("e.g. discord, chrome.exe, explorer")
        self.block_edit.setClearButtonEnabled(True)
        self.block_edit.setMinimumWidth(280)
        self.block_edit.textEdited.connect(lambda t: self._set("window_blocklist", t))
        c.setting("Never click on (title or app, comma-separated)", self.block_edit)

        self.win_combo = RefreshingCombo(platform.list_windows)
        if self.cfg.get("window_lock_title"):
            self.win_combo.addItem(self.cfg["window_lock_title"])
            self.win_combo.setCurrentText(self.cfg["window_lock_title"])
        self.win_combo.currentTextChanged.connect(
            lambda t: self._set("window_lock_title", t))
        self.win_sw = ToggleSwitch(self.cfg["window_lock_enabled"])
        self.win_sw.toggled.connect(lambda v: self._set("window_lock_enabled", v))
        c.setting("Only click in this window", self.win_combo, self.win_sw,
                  tip="Clicking pauses whenever the chosen window isn't focused.")

        if not platform.available():
            c.add(hint("Window failsafes are Windows-only."))
        return c

    def _sequence_card(self):
        c = Card("Sequence + drag clicking", subtitle=(
            "Clicks run through these points in order instead of clicking in "
            "place. Tick 'Drag' to hold the button on the way to a point "
            "(drag stroke). Double-click X or Y to edit."))

        self.seq_sw = ToggleSwitch(self.cfg.get("sequence_enabled", False))
        self.seq_sw.toggled.connect(lambda v: self._set("sequence_enabled", v))
        c.setting("Enable sequence mode", self.seq_sw)

        self.seq_table = QTableWidget(0, 3)
        self.seq_table.setHorizontalHeaderLabels(["X", "Y", "Drag here"])
        self.seq_table.verticalHeader().setVisible(False)
        self.seq_table.setEditTriggers(QAbstractItemView.DoubleClicked
                                       | QAbstractItemView.EditKeyPressed)
        self.seq_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.seq_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.seq_table.setFixedHeight(160)
        self.seq_table.itemChanged.connect(self._seq_cell_edited)
        c.add(self.seq_table)
        self._refresh_seq_table()

        self.rec_pts_btn = button("Record points", "Ghost", self._toggle_seq_record,
                                  tip="Press F7 anywhere to save the cursor "
                                      "position as a point, F8 (or this "
                                      "button) to finish.",
                                  icon_name="record")
        self._seq_recording = False
        self.ctrl.seq_point.connect(self._seq_point_recorded)
        self.ctrl.seq_record_state.connect(self._seq_rec_state)

        add_btn = button("Add cursor position", "Ghost", self._seq_add_cursor)
        self.pick_btn = button("Pick in 3s", "Ghost", self._seq_pick_delayed,
                               tip="Click, then move your mouse to the spot - "
                                   "the point is grabbed 3 seconds later.")
        rb = c.add_row(self.rec_pts_btn, add_btn, self.pick_btn)
        rb.addStretch()
        rb.addWidget(button("↑", "GhostSmall", lambda: self._seq_move(-1)))
        rb.addWidget(button("↓", "GhostSmall", lambda: self._seq_move(1)))
        rb.addWidget(button("Delete", "GhostSmall", self._seq_delete))
        rb.addWidget(button("Clear", "GhostSmall", self._seq_clear))

        self.seq_delay = self._spin(0, 60000, self.cfg.get("sequence_point_delay_ms", 50),
                                    " ms", 110)
        self.seq_delay.valueChanged.connect(
            lambda v: self._set("sequence_point_delay_ms", v))
        c.setting("Delay between points", self.seq_delay)
        return c

    def _toggle_seq_record(self):
        if self._seq_recording:
            self.ctrl.stop_seq_record()
        else:
            self.ctrl.start_seq_record()

    def _seq_rec_state(self, on: bool):
        self._seq_recording = on
        self.rec_pts_btn.setText("Finish (F8)" if on else "Record points")
        repolish(self.rec_pts_btn, "Primary" if on else "Ghost")
        if on:
            self.ctrl.toast.emit("Recording points: F7 adds, F8 finishes")

    def _seq_point_recorded(self, x: int, y: int):
        self.cfg.setdefault("sequence_points", []).append(
            {"x": x, "y": y, "drag": False})
        self.on_change()
        self._refresh_seq_table()
        self.ctrl.toast.emit(f"Point {len(self.cfg['sequence_points'])}: ({x}, {y})")

    def _set_armed(self, v: bool):
        self.cfg["armed"] = v
        self.on_change()
        self.ctrl.refresh_hotkeys()
        self._reflect_state(self.ctrl.clicker.running)

    def sync(self):
        self.armed_sw.setChecked(self.cfg.get("armed", True))
        self.focus_sw.setChecked(self.cfg.get("stop_on_focus_change", False))
        self._reflect_state(self.ctrl.clicker.running)

    def _refresh_seq_table(self):
        pts = self.cfg.get("sequence_points", [])
        self.seq_table.blockSignals(True)
        self.seq_table.setRowCount(len(pts))
        for i, pt in enumerate(pts):
            for col, key in ((0, "x"), (1, "y")):
                it = QTableWidgetItem(str(pt[key]))
                it.setTextAlignment(Qt.AlignCenter)
                self.seq_table.setItem(i, col, it)
            cell = QWidget()
            lay = QHBoxLayout(cell)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setAlignment(Qt.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(bool(pt.get("drag", False)))
            cb.setEnabled(i > 0)
            cb.toggled.connect(lambda v, idx=i: self._seq_set_drag(idx, v))
            lay.addWidget(cb)
            self.seq_table.setCellWidget(i, 2, cell)
        self.seq_table.blockSignals(False)

    def _seq_cell_edited(self, item):
        pts = self.cfg.get("sequence_points", [])
        row, col = item.row(), item.column()
        if not (0 <= row < len(pts)) or col > 1:
            return
        key = "x" if col == 0 else "y"
        try:
            pts[row][key] = int(float(item.text().strip()))
            self.on_change()
        except ValueError:
            self.ctrl.toast.emit("Coordinates must be whole numbers")
        self.seq_table.blockSignals(True)
        item.setText(str(pts[row][key]))
        self.seq_table.blockSignals(False)

    def _seq_pick_delayed(self):
        if not self.pick_btn.isEnabled():
            return
        self.pick_btn.setEnabled(False)

        def tick(n):
            if n == 0:
                self._seq_add_cursor()
                self.pick_btn.setText("Pick in 3s")
                self.pick_btn.setEnabled(True)
                return
            self.pick_btn.setText(f"Picking in {n}…")
            QTimer.singleShot(1000, lambda: tick(n - 1))

        tick(3)

    def _seq_add_cursor(self):
        x, y = self.ctrl.nudge.position()
        self._seq_point_recorded(x, y)

    def _seq_delete(self):
        rows = sorted({i.row() for i in self.seq_table.selectedIndexes()}, reverse=True)
        pts = self.cfg.get("sequence_points", [])
        for row in rows:
            if 0 <= row < len(pts):
                pts.pop(row)
        if rows:
            self.on_change()
            self._refresh_seq_table()

    def _seq_clear(self):
        if self.cfg.get("sequence_points"):
            self.cfg["sequence_points"] = []
            self.on_change()
            self._refresh_seq_table()

    def _seq_move(self, delta):
        row = self.seq_table.currentRow()
        pts = self.cfg.get("sequence_points", [])
        new = row + delta
        if 0 <= row < len(pts) and 0 <= new < len(pts):
            pts[row], pts[new] = pts[new], pts[row]
            self.on_change()
            self._refresh_seq_table()
            self.seq_table.selectRow(new)

    def _seq_set_drag(self, idx, value):
        pts = self.cfg.get("sequence_points", [])
        if 0 <= idx < len(pts):
            pts[idx]["drag"] = value
            self.on_change()

    def _set(self, key, value):
        self.cfg[key] = value
        self.on_change()

    def _set_hotkey(self, combo):
        self.cfg["hotkey"] = combo
        self.on_change()
        self.ctrl.refresh_hotkeys()
        self._reflect_state(self.ctrl.clicker.running)

    def _set_hotkey_mode(self, mode):
        self.cfg["hotkey_mode"] = mode
        self.on_change()
        self.ctrl.refresh_hotkeys()

    def _toggle(self):
        self.ctrl.toggle_clicker()

    def _reflect_state(self, running):
        hk = self.cfg.get("hotkey") if self.cfg.get("armed", True) else None
        suffix = f"  ({combo_to_text(hk)})" if hk else ""
        self.start_btn.setText(("Stop" if running else "Start") + suffix)
        repolish(self.start_btn, "Running" if running else "Primary")
        self.status.setText("Running" if running else "Idle")
        repolish(self.status, "StatRunning" if running else "StatIdle")

    def _count(self, n):
        if self.ctrl.clicker.running:
            self.status.setText(f"Running · {n:,} clicks")
        elif n:
            self.status.setText(f"Idle · last run {n:,} clicks")
