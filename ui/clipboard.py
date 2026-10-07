import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPlainTextEdit, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

from core import transforms
from .hotkey_button import HotkeyButton
from .styles import ACCENT
from .widgets import (Card, ToggleSwitch, button, confirm, flow_row,
                      page_header, rich_list, set_item, small_label)


def _age(ts: float) -> str:
    if not ts:
        return ""
    d = max(0, time.time() - ts)
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)} min ago"
    if d < 86400:
        return f"{int(d // 3600)} h ago"
    return f"{int(d // 86400)} d ago"


class ClipboardPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.watch = controller.clipboard
        self.on_change = on_change
        self._shown: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(14)

        head, right = page_header(
            "Clipboard", "Everything you copy, searchable. Enter or double-click "
                         "copies an entry back; pins survive restarts.")
        right.addWidget(small_label("Capture"))
        self.master_sw = ToggleSwitch(self.watch.enabled)
        self.master_sw.toggled.connect(self.watch.set_enabled)
        right.addWidget(self.master_sw)
        root.addLayout(head)

        card = Card("History")
        b = card.body()
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search history…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh)
        top.addWidget(self.search, 1)
        self.count_lbl = small_label("")
        top.addWidget(self.count_lbl)
        top.addWidget(button("Clear unpinned", "Ghost", self._clear))
        b.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        self.list = rich_list(QListWidget())
        self.list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list.itemDoubleClicked.connect(self._copy_item)
        self.list.currentItemChanged.connect(self._selection_changed)
        self.list.setMinimumWidth(280)
        self.list.setMinimumHeight(240)
        split.addWidget(self.list)
        self.preview = QPlainTextEdit(objectName="Mono")
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select an entry to see all of it.")
        self.preview.setMinimumWidth(220)
        split.addWidget(self.preview)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        b.addWidget(split, 1)

        actions = QHBoxLayout()
        self.copy_btn = button("Copy", "Primary", lambda: self._copy_item(self.list.currentItem()),
                               icon_name="copy")
        self.pin_btn = button("Pin", "Ghost", self._toggle_pin)
        self.del_btn = button("Delete", "Ghost", self._delete)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.pin_btn)
        actions.addWidget(self.del_btn)
        actions.addStretch()
        b.addLayout(actions)
        self.transform_btns = [
            button(label, "GhostSmall", lambda _=False, fn=fn: self._transform(fn))
            for _key, label, fn, _group in transforms.QUICK]
        more = button("More", "GhostSmall")
        more.setMenu(self._transform_menu())
        more.setProperty("hasMenu", True)
        self.transform_btns.append(more)
        b.addWidget(flow_row("Copy as", *self.transform_btns))
        root.addWidget(card, 1)

        root.addWidget(self._settings_card())

        find = QShortcut(QKeySequence(QKeySequence.Find), self)
        find.activated.connect(lambda: (self.search.setFocus(), self.search.selectAll()))
        for key, fn in ((Qt.Key_Return, lambda: self._copy_item(self.list.currentItem())),
                        (Qt.Key_Enter, lambda: self._copy_item(self.list.currentItem())),
                        (Qt.Key_Delete, self._delete)):
            sc = QShortcut(QKeySequence(key), self.list)
            sc.setContext(Qt.WidgetShortcut)
            sc.activated.connect(fn)
        down = QShortcut(QKeySequence(Qt.Key_Down), self.search)
        down.setContext(Qt.WidgetShortcut)
        down.activated.connect(lambda: (self.list.setFocus(),
                                        self.list.setCurrentRow(0)))

        self.watch.changed.connect(self._refresh)
        self._refresh()
        self._selection_changed(None)

    def _settings_card(self):
        c = Card("Capture settings")
        cfg = self.watch.cfg
        remember = ToggleSwitch(cfg.get("remember_history", False))
        remember.toggled.connect(self.watch.set_remember)
        c.setting("Remember history across restarts", remember,
                  tip="Unpinned entries are kept in clipboard_history.json "
                      "next to the config. Off = only pins survive.")
        private = ToggleSwitch(cfg.get("ignore_sensitive", True))
        private.toggled.connect(lambda v: (cfg.__setitem__("ignore_sensitive", v),
                                           self.on_change()))
        c.setting("Skip password-manager copies", private,
                  tip="Ignores copies flagged as private (KeePassXC, 1Password, "
                      "Bitwarden and others mark passwords this way).")
        cap = QSpinBox()
        cap.setRange(10, 2000)
        cap.setValue(int(cfg.get("max_items", 100)))
        cap.setSuffix(" entries")
        cap.setFixedWidth(130)
        cap.valueChanged.connect(self.watch.set_max_items)
        c.setting("History size", cap)
        self.pp_btn = HotkeyButton(self.ctrl.hotkeys, cfg.get("paste_plain_hotkey", []),
                                   hid="paste_plain")
        self.pp_btn.captured.connect(self._set_pp_hotkey)
        c.setting("Paste as plain text (strips formatting)", self.pp_btn)
        return c

    def _transform_menu(self):
        m = QMenu(self)
        for group in transforms.GROUPS:
            sub = m.addMenu(group)
            for _key, label, fn, g in transforms.TRANSFORMS:
                if g == group:
                    sub.addAction(label, lambda fn=fn: self._transform(fn))
        return m

    def sync(self):
        self.master_sw.setChecked(self.watch.enabled)
        self._refresh()

    def _entry(self, item) -> dict | None:
        if item is None:
            return None
        idx = item.data(Qt.UserRole)
        if idx is None or not (0 <= idx < len(self._shown)):
            return None
        return self._shown[idx]

    def _refresh(self, *_):
        query = self.search.text().lower().strip()
        selected = self._entry(self.list.currentItem())
        self.list.blockSignals(True)
        self.list.clear()
        self._shown = []
        for e in self.watch.entries:
            if query and query not in e["text"].lower():
                continue
            preview = " ".join(e["text"].split())[:300]
            lines = e["text"].count("\n") + 1
            meta = f"{len(e['text']):,} chars" + (f" · {lines} lines" if lines > 1 else "")
            age = "pinned" if e["pinned"] else _age(e["ts"])
            it = QListWidgetItem()
            set_item(it, preview or "(whitespace)", meta,
                     glyph="pinned" if e["pinned"] else "clipboard",
                     color=ACCENT if e["pinned"] else None, right=age)
            it.setData(Qt.UserRole, len(self._shown))
            self._shown.append(e)
            self.list.addItem(it)
            if e is selected:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        total = len(self.watch.entries)
        self.count_lbl.setText(f"{len(self._shown)} of {total}" if query else
                               f"{total} entries")
        if not self._shown:
            it = QListWidgetItem()
            set_item(it, "Nothing here yet" if not total else "No matches",
                     "Copy something and it shows up here." if not total else "",
                     dim=True)
            it.setFlags(Qt.NoItemFlags)
            self.list.addItem(it)
        self._selection_changed(self.list.currentItem())

    def _selection_changed(self, item, _prev=None):
        e = self._entry(item)
        has = e is not None
        for btn in (self.copy_btn, self.pin_btn, self.del_btn, *self.transform_btns):
            btn.setEnabled(has)
        self.pin_btn.setText("Unpin" if (has and e["pinned"]) else "Pin")
        self.preview.setPlainText(e["text"] if has else "")

    def _copy_item(self, item):
        e = self._entry(item)
        if e:
            self.watch.copy(e["text"])
            self.ctrl.toast.emit("Copied to clipboard")

    def _toggle_pin(self):
        e = self._entry(self.list.currentItem())
        if e:
            self.watch.set_pinned(e, not e["pinned"])

    def _delete(self):
        e = self._entry(self.list.currentItem())
        if e:
            row = self.list.currentRow()
            self.watch.delete(e)
            self.list.setCurrentRow(min(row, self.list.count() - 1))

    def _transform(self, fn):
        e = self._entry(self.list.currentItem())
        if not e:
            return
        out, err = transforms.apply(fn, e["text"])
        if err:
            self.ctrl.toast.emit(f"Can't transform: {err}")
            return
        self.watch.copy(out)
        self.ctrl.toast.emit("Copied transformed text")

    def _set_pp_hotkey(self, combo):
        self.watch.cfg["paste_plain_hotkey"] = combo
        self.on_change()
        self.ctrl.refresh_hotkeys()

    def _clear(self):
        n = sum(1 for e in self.watch.entries if not e["pinned"])
        if n and confirm(self, "Clear history",
                         f"Delete {n} unpinned entr{'y' if n == 1 else 'ies'}?",
                         yes="Clear"):
            self.watch.clear_unpinned()
