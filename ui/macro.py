import json
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                               QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from core import macro as macro_mod
from core.hotkeys import combo_to_text
from .hotkey_button import HotkeyButton
from .styles import ACCENT, GREEN
from .widgets import (Card, Segmented, ToggleSwitch, button, confirm, flow_row,
                      page_header, pair, repolish, rich_list, set_item,
                      small_label)

STOP_KEY = "f8"


class ActionDialog(QDialog):
    def __init__(self, parent, action: dict):
        super().__init__(parent)
        self.setWindowTitle("Edit action")
        self.setMinimumWidth(340)
        self.a = dict(action)
        form = QFormLayout(self)
        form.setSpacing(10)
        t = self.a.get("type")
        self.fields = {}
        if t == "delay":
            ms = QSpinBox()
            ms.setRange(0, 3_600_000)
            ms.setSuffix(" ms")
            ms.setValue(int(self.a.get("ms", 0)))
            form.addRow("Wait", ms)
            self.fields["ms"] = ms
        elif t == "key":
            key = QLineEdit(str(self.a.get("key", "")))
            key.setPlaceholderText("a, enter, space, ctrl, f5, num5…")
            act = QComboBox()
            act.addItems(["press", "down", "up"])
            act.setCurrentText(self.a.get("action", "press"))
            form.addRow("Key", key)
            form.addRow("Action", act)
            self.fields.update(key=key, action=act)
        elif t in ("mouse", "move"):
            if t == "mouse":
                btn = QComboBox()
                btn.addItems(["left", "right", "middle"])
                btn.setCurrentText(self.a.get("button", "left"))
                act = QComboBox()
                act.addItems(["click", "down", "up"])
                act.setCurrentText(self.a.get("action", "click"))
                form.addRow("Button", btn)
                form.addRow("Action", act)
                self.fields.update(button=btn, action=act)
            here = QCheckBox("At a fixed position")
            here.setChecked(self.a.get("x") is not None or t == "move")
            here.setEnabled(t == "mouse")
            xs, ys = QSpinBox(), QSpinBox()
            for s, k in ((xs, "x"), (ys, "y")):
                s.setRange(-32000, 32000)
                s.setValue(int(self.a.get(k) or 0))
            form.addRow(here)
            form.addRow("X", xs)
            form.addRow("Y", ys)
            here.toggled.connect(lambda v: (xs.setEnabled(v), ys.setEnabled(v)))
            xs.setEnabled(here.isChecked())
            ys.setEnabled(here.isChecked())
            self.fields.update(here=here, x=xs, y=ys)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def result_action(self) -> dict:
        a, f = self.a, self.fields
        t = a.get("type")
        if t == "delay":
            a["ms"] = f["ms"].value()
        elif t == "key":
            a["key"] = f["key"].text().strip().lower() or a.get("key", "")
            a["action"] = f["action"].currentText()
        elif t in ("mouse", "move"):
            if t == "mouse":
                a["button"] = f["button"].currentText()
                a["action"] = f["action"].currentText()
            if f["here"].isChecked():
                a["x"], a["y"] = f["x"].value(), f["y"].value()
            else:
                a.pop("x", None)
                a.pop("y", None)
        return a


class MacroPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.on_change = on_change
        self.current_id = None
        self._recording = False

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(14)
        head, _right = page_header(
            "Macros", "Record keyboard + mouse input and replay it with a "
                      "hotkey. Keys are sent as hardware scan codes, so they "
                      "work in games too.")
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._list_pane(), 0)
        body.addWidget(self._editor_pane(), 1)
        root.addLayout(body, 1)

        controller.recording_done.connect(self._on_recorded)
        controller.macro_state.connect(self._on_macro_state)

        del_sc = QShortcut(QKeySequence(QKeySequence.Delete), self.table)
        del_sc.setContext(Qt.WidgetShortcut)
        del_sc.activated.connect(self._del_row)

        self._reload_list()
        self._set_editor_enabled(False)
        if self.ctrl.config["macros"]:
            self.macro_list.setCurrentRow(0)

    def _list_pane(self):
        c = Card("Your macros")
        c.setFixedWidth(250)
        self.macro_list = rich_list(QListWidget())
        self.macro_list.setMinimumHeight(220)
        self.macro_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.macro_list.currentItemChanged.connect(self._on_select)
        c.add(self.macro_list)
        c.add(button("New macro", "Primary", self._add_macro))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button("Duplicate", "Ghost", self._duplicate_macro))
        row.addWidget(button("Delete", "Ghost", self._delete_macro))
        c.body().addLayout(row)
        io_row = QHBoxLayout()
        io_row.setSpacing(8)
        io_row.addWidget(button("Import…", "Ghost", self._import))
        io_row.addWidget(button("Export…", "Ghost", self._export))
        c.body().addLayout(io_row)
        return c

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import macros", "", "Volt macros (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Import failed", f"Couldn't read file:\n{e}")
            return
        items = data if isinstance(data, list) else [data]
        added = 0
        for it in items:
            if (not isinstance(it, dict) or not isinstance(it.get("actions"), list)):
                continue
            it = dict(it)
            it["actions"] = [a for a in it["actions"]
                             if isinstance(a, dict) and a.get("type")]
            it["id"] = uuid.uuid4().hex[:8]
            it.setdefault("name", "Imported macro")
            it["hotkey"] = it.get("hotkey") if isinstance(it.get("hotkey"), list) else []
            it.setdefault("hotkey_mode", "toggle")
            it.setdefault("enabled", True)
            it.setdefault("repeat", 1)
            it.setdefault("loop", False)
            it.setdefault("speed", 1.0)
            it.setdefault("key_hold_ms", 25)
            self.ctrl.config["macros"].append(it)
            added += 1
        self.on_change()
        self.ctrl.refresh_hotkeys()
        self._reload_list()
        self.ctrl.toast.emit(f"Imported {added} macro{'s' if added != 1 else ''}")

    def _export(self):
        m = self._macro()
        if not m:
            self.ctrl.toast.emit("Select a macro to export first")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export macro", f"{m['name']}.json", "Volt macros (*.json)")
        if not path:
            return
        data = {k: v for k, v in m.items() if k != "id"}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.ctrl.toast.emit("Macro exported")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _select_id(self, mid):
        for i in range(self.macro_list.count()):
            if self.macro_list.item(i).data(Qt.UserRole) == mid:
                self.macro_list.setCurrentRow(i)
                return

    def _duplicate_macro(self):
        m = self._macro()
        if not m:
            return
        new = self.ctrl.duplicate_macro(m["id"])
        if new:
            self.on_change()
            self._reload_list()
            self._select_id(new["id"])

    def _delete_macro(self):
        m = self._macro()
        if not m:
            return
        if not confirm(self, "Delete macro", f"Delete '{m['name']}' and its "
                       f"{len(m['actions'])} actions?"):
            return
        self.ctrl.delete_macro(self.current_id)
        self.current_id = None
        self.on_change()
        self._reload_list()
        if self.macro_list.count() and self.ctrl.config["macros"]:
            self.macro_list.setCurrentRow(0)
        else:
            self._set_editor_enabled(False)

    def _reload_list(self):
        self.macro_list.blockSignals(True)
        self.macro_list.clear()
        for m in self.ctrl.config["macros"]:
            hk = combo_to_text(m["hotkey"]) if m["hotkey"] else "no hotkey"
            running = self.ctrl.is_macro_running(m["id"])
            it = QListWidgetItem()
            set_item(it, m["name"] or "Untitled",
                     f"{hk} · {len(m.get('actions', []))} actions",
                     glyph="play" if running else "macros",
                     color=GREEN if running else (ACCENT if m.get("enabled", True)
                                                  else None),
                     dim=not m.get("enabled", True))
            it.setData(Qt.UserRole, m["id"])
            self.macro_list.addItem(it)
            if m["id"] == self.current_id:
                self.macro_list.setCurrentItem(it)
        if not self.ctrl.config["macros"]:
            it = QListWidgetItem()
            set_item(it, "No macros yet", "Click New macro, then Record", dim=True)
            it.setFlags(Qt.NoItemFlags)
            self.macro_list.addItem(it)
        self.macro_list.blockSignals(False)

    def _add_macro(self):
        m = self.ctrl.new_macro()
        self.on_change()
        self.ctrl.refresh_hotkeys()
        self._reload_list()
        self._select_id(m["id"])
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _on_select(self, item, _prev=None):
        if not item or item.data(Qt.UserRole) is None:
            self._set_editor_enabled(False)
            return
        self.current_id = item.data(Qt.UserRole)
        self._load_macro()

    def _editor_pane(self):
        self.editor = Card("Editor")
        b = self.editor.body()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Macro name")
        self.name_edit.textEdited.connect(self._name_changed)
        self.enabled_sw = ToggleSwitch(True)
        self.enabled_sw.setToolTip("Hotkey enabled")
        self.enabled_sw.toggled.connect(self._enabled_changed)
        rn = self.editor.add_row(self.name_edit)
        rn.addWidget(small_label("Enabled"))
        rn.addWidget(self.enabled_sw)

        self.trigger_btn = HotkeyButton(self.ctrl.hotkeys, [])
        self.trigger_btn.captured.connect(self._hotkey_changed)
        self.trigger_mode = Segmented([("toggle", "Toggle"), ("hold", "Hold")])
        self.trigger_mode.changed.connect(self._mode_changed)
        rt = self.editor.add_row(small_label("Trigger"))
        rt.addWidget(self.trigger_btn)
        rt.addWidget(self.trigger_mode)
        rt.addStretch()

        self.repeat = QSpinBox()
        self.repeat.setRange(1, 1000000)
        self.repeat.setPrefix("× ")
        self.repeat.valueChanged.connect(lambda v: self._field("repeat", v))
        self.loop_sw = ToggleSwitch(False)
        self.loop_sw.toggled.connect(self._loop_changed)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.1, 10.0)
        self.speed.setSingleStep(0.1)
        self.speed.setSuffix("×")
        self.speed.setValue(1.0)
        self.speed.valueChanged.connect(lambda v: self._field("speed", v))
        self.key_hold = QSpinBox()
        self.key_hold.setRange(1, 1000)
        self.key_hold.setSuffix(" ms")
        self.key_hold.setValue(25)
        self.key_hold.setToolTip(
            "How long each tapped key is held. Games need ~10-25ms to register a press.")
        self.key_hold.valueChanged.connect(lambda v: self._field("key_hold_ms", v))
        self.repeat.setFixedWidth(110)
        self.speed.setFixedWidth(92)
        self.key_hold.setFixedWidth(100)
        b.addWidget(flow_row(pair("Repeat", self.repeat), pair("Loop", self.loop_sw),
                             pair("Speed", self.speed), pair("Key hold", self.key_hold),
                             spacing=18))

        s = self.ctrl.config["settings"]
        self.rec_checks = {}
        for key, label in [("rec_keys", "Keyboard"), ("rec_buttons", "Mouse buttons"),
                           ("rec_moves", "Mouse moves"), ("rec_delays", "Delays")]:
            cb = QCheckBox(label)
            cb.setChecked(s.get(key, True))
            cb.toggled.connect(lambda v, k=key: self._rec_pref(k, v))
            self.rec_checks[key] = cb
        b.addWidget(flow_row("Record", *self.rec_checks.values(), spacing=12))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["#", "Action", "Value"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setMinimumHeight(220)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(self._edit_row)
        b.addWidget(self.table, 1)
        self.summary = small_label("")
        b.addWidget(self.summary)

        self.rec_btn = button("Record", "Ghost", self._toggle_record, icon_name="record",
                              tip=f"Records until you press {STOP_KEY.upper()} "
                                  "(or click Stop).")
        row1 = self.editor.add_row(self.rec_btn)
        for text, fn in [("+ Delay", self._add_delay), ("+ Key", self._add_key),
                         ("+ Click", self._add_click), ("+ Move", self._add_move)]:
            row1.addWidget(button(text, "Ghost", fn))
        row1.addStretch()

        row2 = self.editor.add_row()
        for text, fn, tip in [("Edit", self._edit_selected, "Double-click a row too"),
                              ("Delete", self._del_row, "Del key works too"),
                              ("↑", lambda: self._move(-1), "Move up"),
                              ("↓", lambda: self._move(1), "Move down"),
                              ("Clear", self._clear, "Remove all actions")]:
            row2.addWidget(button(text, "GhostSmall", fn, tip=tip))
        row2.addStretch()
        self.test_btn = button("Test", "Primary", self._test, icon_name="play")
        row2.addWidget(self.test_btn)

        self.rec_hint = QLabel(f"Recording… press {STOP_KEY.upper()} to stop. "
                               "Your hotkeys and snippets are paused meanwhile.",
                               objectName="Warn")
        self.rec_hint.setVisible(False)
        b.addWidget(self.rec_hint)
        return self.editor

    def _macro(self):
        return self.ctrl.get_macro(self.current_id) if self.current_id else None

    def _load_macro(self):
        m = self._macro()
        if not m:
            return
        self._set_editor_enabled(True)
        for w in (self.name_edit, self.enabled_sw, self.trigger_mode,
                  self.repeat, self.loop_sw, self.speed, self.key_hold):
            w.blockSignals(True)
        self.name_edit.setText(m["name"])
        self.enabled_sw.setChecked(m.get("enabled", True))
        self.trigger_btn.setCombo(m["hotkey"])
        self.trigger_btn.set_hid(f"macro_{m['id']}")
        self.trigger_mode.setValue(m.get("hotkey_mode", "toggle"))
        self.repeat.setValue(m.get("repeat", 1))
        self.loop_sw.setChecked(m.get("loop", False))
        self.repeat.setEnabled(not m.get("loop", False))
        self.speed.setValue(m.get("speed", 1.0))
        self.key_hold.setValue(m.get("key_hold_ms", 25))
        for w in (self.name_edit, self.enabled_sw, self.trigger_mode,
                  self.repeat, self.loop_sw, self.speed, self.key_hold):
            w.blockSignals(False)
        self._refresh_table()
        self._update_test_btn()

    def _set_editor_enabled(self, on):
        self.editor.setEnabled(on)
        if not on:
            self.table.setRowCount(0)
            self.summary.setText("")
            self.name_edit.clear()

    def _field(self, key, value):
        m = self._macro()
        if m:
            m[key] = value
            self.on_change()

    def _loop_changed(self, v):
        self._field("loop", v)
        self.repeat.setEnabled(not v)

    def _name_changed(self, text):
        self._field("name", text)
        self._reload_list()

    def _enabled_changed(self, v):
        self._field("enabled", v)
        self.ctrl.refresh_hotkeys()
        self._reload_list()

    def _hotkey_changed(self, combo):
        self._field("hotkey", combo)
        self.ctrl.refresh_hotkeys()
        self._reload_list()

    def _mode_changed(self, mode):
        self._field("hotkey_mode", mode)
        self.ctrl.refresh_hotkeys()

    def sync(self):
        self._reload_list()

    def _refresh_table(self, select=None):
        m = self._macro()
        acts = m["actions"] if m else []
        self.table.setRowCount(len(acts))
        for i, a in enumerate(acts):
            label, value = macro_mod.describe(a)
            for col, text in enumerate((str(i + 1), label, value)):
                it = QTableWidgetItem(text)
                if col == 0:
                    it.setForeground(Qt.gray)
                self.table.setItem(i, col, it)
        if select is not None and 0 <= select < len(acts):
            self.table.selectRow(select)
        total = macro_mod.duration_ms(acts)
        self.summary.setText(
            f"{len(acts)} actions · ~{total / 1000:.1f} s per run" if acts else
            "Empty - press Record, or add actions by hand.")

    def _insert_at(self) -> int:
        rows = self._selected_rows()
        m = self._macro()
        return (rows[-1] + 1) if rows else (len(m["actions"]) if m else 0)

    def _selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def _insert(self, action):
        m = self._macro()
        if not m:
            return
        pos = self._insert_at()
        m["actions"].insert(pos, action)
        self.on_change()
        self._refresh_table(select=pos)

    def _add_delay(self):
        ms, ok = QInputDialog.getInt(self, "Add delay", "Milliseconds:", 100, 0, 3_600_000)
        if ok:
            self._insert({"type": "delay", "ms": ms})

    def _add_key(self):
        key, ok = QInputDialog.getText(
            self, "Add key", "Key (e.g. a, enter, space, ctrl, f5, num5):")
        if ok and key.strip():
            self._insert({"type": "key", "action": "press", "key": key.strip().lower()})

    def _add_click(self):
        btn, ok = QInputDialog.getItem(
            self, "Add click", "Button:", ["left", "right", "middle"], 0, False)
        if ok:
            self._insert({"type": "mouse", "action": "click", "button": btn})

    def _add_move(self):
        x, y = self.ctrl.nudge.position()
        dlg = ActionDialog(self, {"type": "move", "x": x, "y": y})
        if dlg.exec():
            self._insert(dlg.result_action())

    def _edit_selected(self):
        rows = self._selected_rows()
        if rows:
            self._edit_row(rows[0], 0)

    def _edit_row(self, row, _col=0):
        m = self._macro()
        if not m or row >= len(m["actions"]):
            return
        dlg = ActionDialog(self, m["actions"][row])
        if dlg.exec():
            m["actions"][row] = dlg.result_action()
            self.on_change()
            self._refresh_table(select=row)

    def _del_row(self):
        m = self._macro()
        rows = self._selected_rows()
        if not m or not rows:
            return
        for r in reversed(rows):
            if 0 <= r < len(m["actions"]):
                m["actions"].pop(r)
        self.on_change()
        self._refresh_table(select=min(rows[0], len(m["actions"]) - 1))

    def _move(self, delta):
        m = self._macro()
        rows = self._selected_rows()
        if not m or len(rows) != 1:
            return
        row, new = rows[0], rows[0] + delta
        if 0 <= new < len(m["actions"]):
            acts = m["actions"]
            acts[row], acts[new] = acts[new], acts[row]
            self.on_change()
            self._refresh_table(select=new)

    def _clear(self):
        m = self._macro()
        if not m or not m["actions"]:
            return
        if confirm(self, "Clear actions",
                   f"Delete all {len(m['actions'])} actions in '{m['name']}'?",
                   yes="Clear"):
            m["actions"] = []
            self.on_change()
            self._refresh_table()

    def _rec_pref(self, key, value):
        self.ctrl.config["settings"][key] = value
        self.on_change()

    def _toggle_record(self):
        if self._recording:
            self.ctrl.stop_recording(trim_click=True)
            return
        self._recording = True
        self.rec_btn.setText(f"Stop ({STOP_KEY.upper()})")
        repolish(self.rec_btn, "Danger")
        self.rec_hint.setVisible(True)
        s = self.ctrl.config["settings"]
        self.ctrl.start_recording(
            record_moves=s.get("rec_moves", False),
            record_buttons=s.get("rec_buttons", True),
            record_keys=s.get("rec_keys", True),
            record_delays=s.get("rec_delays", True),
            stop_token=STOP_KEY)

    def _on_recorded(self, actions):
        self._recording = False
        self.rec_btn.setText("Record")
        repolish(self.rec_btn, "Ghost")
        self.rec_hint.setVisible(False)
        m = self._macro()
        if m and actions:
            m["actions"].extend(actions)
            self.on_change()
            self._refresh_table()
            self.ctrl.toast.emit(f"Recorded {len(actions)} actions")
        self._reload_list()

    def _test(self):
        if self.ctrl.is_macro_running(self.current_id):
            self.ctrl.stop_macro(self.current_id)
        else:
            self.ctrl.play_macro(self.current_id)

    def _update_test_btn(self):
        running = bool(self.current_id) and self.ctrl.is_macro_running(self.current_id)
        self.test_btn.setText("Stop" if running else "Test")
        repolish(self.test_btn, "Running" if running else "Primary")

    def _on_macro_state(self, mid, running):
        if mid == self.current_id:
            self._update_test_btn()
        self._reload_list()
