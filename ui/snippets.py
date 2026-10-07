import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QVBoxLayout, QWidget)

from core import snippets as snip_mod
from .styles import ACCENT
from .widgets import (Card, Segmented, ToggleSwitch, button, confirm, flow_row,
                      hint, page_header, rich_list, set_item, small_label)

TOKENS = ["{date}", "{time}", "{datetime}", "{day}", "{clipboard}", "{cursor}"]


class SnippetsPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.cfg = controller.config["snippets"]
        self.on_change = on_change
        self.current_id = None

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(14)

        head, right = page_header(
            "Snippets", "Type a trigger anywhere - a browser, a chat, an editor "
                        "- and Volt replaces it with the full text.")
        right.addWidget(small_label("Expansion"))
        self.master_sw = ToggleSwitch(self.cfg.get("enabled", True))
        self.master_sw.toggled.connect(self._master_toggle)
        right.addWidget(self.master_sw)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._list_pane(), 0)
        body.addWidget(self._editor_pane(), 1)
        root.addLayout(body, 1)

        self._reload_list()
        self._set_editor_enabled(False)
        if self.snips():
            self.snip_list.setCurrentRow(0)

    def snips(self) -> list[dict]:
        return self.cfg.setdefault("items", [])

    def _snip(self) -> dict | None:
        return next((s for s in self.snips() if s["id"] == self.current_id), None)

    def _apply(self):
        self.on_change()
        self.ctrl.refresh_snippets()

    def _list_pane(self):
        c = Card("Your snippets")
        c.setFixedWidth(260)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self._reload_list())
        c.add(self.search)
        self.snip_list = rich_list(QListWidget())
        self.snip_list.setMinimumHeight(220)
        self.snip_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.snip_list.currentItemChanged.connect(self._on_select)
        c.add(self.snip_list)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button("New snippet", "Primary", self._add))
        row.addWidget(button("Delete", "Ghost", self._delete))
        c.body().addLayout(row)
        return c

    def _reload_list(self):
        q = self.search.text().strip().lower()
        self.snip_list.blockSignals(True)
        self.snip_list.clear()
        for s in self.snips():
            text = s.get("text", "")
            if q and q not in s.get("trigger", "").lower() and q not in text.lower():
                continue
            preview = " ".join(text.split()) or "(empty)"
            it = QListWidgetItem()
            on = s.get("enabled", True)
            set_item(it, s.get("trigger") or "(no trigger)", preview,
                     glyph="snippets", color=ACCENT if on else None, dim=not on)
            it.setData(Qt.UserRole, s["id"])
            self.snip_list.addItem(it)
            if s["id"] == self.current_id:
                self.snip_list.setCurrentItem(it)
        self.snip_list.blockSignals(False)

    def _add(self):
        n = len(self.snips()) + 1
        s = {"id": uuid.uuid4().hex[:8], "trigger": f";new{n}",
             "text": "", "enabled": True}
        self.snips().append(s)
        self._apply()
        self.search.clear()
        self.current_id = s["id"]
        self._reload_list()
        self._load()
        self.trigger_edit.setFocus()
        self.trigger_edit.selectAll()

    def _delete(self):
        s = self._snip()
        if not s:
            return
        if not confirm(self, "Delete snippet", f"Delete '{s['trigger']}'?"):
            return
        self.snips().remove(s)
        self.current_id = None
        self._apply()
        self._reload_list()
        if self.snip_list.count():
            self.snip_list.setCurrentRow(0)
        else:
            self._set_editor_enabled(False)

    def _on_select(self, item, _prev=None):
        if not item:
            return
        self.current_id = item.data(Qt.UserRole)
        self._load()

    def _editor_pane(self):
        self.editor = Card("Editor")
        b = self.editor.body()

        self.trigger_edit = QLineEdit()
        self.trigger_edit.setPlaceholderText(";addr")
        self.trigger_edit.setMaxLength(32)
        self.trigger_edit.textEdited.connect(self._trigger_changed)
        self.enabled_sw = ToggleSwitch(True)
        self.enabled_sw.toggled.connect(self._enabled_changed)
        r = self.editor.add_row(small_label("Trigger"), self.trigger_edit)
        r.addWidget(small_label("Enabled"))
        r.addWidget(self.enabled_sw)

        self.warn = QLabel("", objectName="Warn")
        self.warn.setWordWrap(True)
        self.warn.setVisible(False)
        b.addWidget(self.warn)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "Full text to insert. Multi-line is fine.\n"
            "Use the token buttons below for dates, the clipboard, or where "
            "the caret should land.")
        self.text_edit.setMinimumHeight(150)
        self.text_edit.textChanged.connect(self._text_changed)
        b.addWidget(self.text_edit, 1)

        b.addWidget(flow_row("Insert", *[
            button(tok, "GhostSmall", lambda _=False, t=tok: self._insert_token(t))
            for tok in TOKENS]))

        self.preview = QLabel("", objectName="Hint")
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        b.addWidget(self.preview)

        mode_row = QHBoxLayout()
        mode_row.addWidget(small_label("Insert method (all snippets)"))
        mode_row.addStretch()
        self.mode = Segmented([("auto", "Auto"), ("type", "Type"), ("paste", "Paste")],
                              self.cfg.get("insert_mode", "auto"))
        self.mode.setToolTip(
            "Type: sends keystrokes. Paste: goes through the clipboard (instant, "
            "and newlines don't press Enter in chat apps; your clipboard is "
            "restored afterwards). Auto: paste multi-line or long text, type "
            "the rest.")
        self.mode.changed.connect(self._mode_changed)
        mode_row.addWidget(self.mode)
        b.addLayout(mode_row)
        b.addWidget(hint("Tip: start triggers with a prefix you'd never type by "
                         "accident (';' or '//'). Longest matching trigger wins."))
        return self.editor

    def _set_editor_enabled(self, on):
        self.editor.setEnabled(on)
        if not on:
            self.preview.setText("")
            self.warn.setVisible(False)

    def _load(self):
        s = self._snip()
        if not s:
            return
        self._set_editor_enabled(True)
        for w in (self.trigger_edit, self.enabled_sw, self.text_edit):
            w.blockSignals(True)
        self.trigger_edit.setText(s.get("trigger", ""))
        self.enabled_sw.setChecked(s.get("enabled", True))
        self.text_edit.setPlainText(s.get("text", ""))
        for w in (self.trigger_edit, self.enabled_sw, self.text_edit):
            w.blockSignals(False)
        self._update_preview()
        self._check_conflicts()

    def _trigger_changed(self, text):
        s = self._snip()
        if s:
            s["trigger"] = text.strip()
            self._apply()
            self._reload_list()
            self._check_conflicts()

    def _enabled_changed(self, v):
        s = self._snip()
        if s:
            s["enabled"] = v
            self._apply()
            self._reload_list()

    def _text_changed(self):
        s = self._snip()
        if s:
            s["text"] = self.text_edit.toPlainText()
            self._apply()
            self._reload_list()
            self._update_preview()

    def _insert_token(self, tok):
        self.text_edit.insertPlainText(tok)
        self.text_edit.setFocus()

    def _mode_changed(self, mode):
        self.cfg["insert_mode"] = mode
        self._apply()

    def _check_conflicts(self):
        s = self._snip()
        msg = ""
        if s and not s.get("trigger"):
            msg = "Add a trigger - this snippet can't fire without one."
        elif s:
            trig = s["trigger"]
            others = [o for o in self.snips()
                      if o is not s and o.get("enabled", True) and o.get("trigger")]
            if any(o["trigger"] == trig for o in others):
                msg = (f"Duplicate trigger - '{trig}' is already used by another "
                       "snippet; only one of them will fire.")
            else:
                overlap = [o["trigger"] for o in others
                           if o["trigger"].endswith(trig) or trig.endswith(o["trigger"])]
                if overlap:
                    msg = (f"Overlaps with {', '.join(overlap[:3])} - when both "
                           "match, the longest trigger wins.")
        self.warn.setText(msg)
        self.warn.setVisible(bool(msg))

    def _update_preview(self):
        s = self._snip()
        if not s or not s.get("text"):
            self.preview.setText("")
            return
        provider = (self.ctrl.clipboard.latest_text
                    if self.ctrl.clipboard else None)
        text, back = snip_mod.split_cursor(snip_mod.render(s["text"], provider))
        if back:
            text = text[:len(text) - back] + "|" + text[len(text) - back:]
        rendered = text.replace("\n", " ⏎ ")
        if len(rendered) > 160:
            rendered = rendered[:160] + "…"
        self.preview.setText(f"Preview: {rendered}")

    def sync(self):
        self.master_sw.setChecked(self.cfg.get("enabled", True))
        self._update_preview()

    def _master_toggle(self, v):
        self.cfg["enabled"] = v
        self._apply()
