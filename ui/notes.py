import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit,
                               QVBoxLayout, QWidget)

from core import transforms
from .styles import ACCENT
from .widgets import (Card, button, confirm, page_header, rich_list, set_item,
                      small_label)


def _when(ts: float) -> str:
    if not ts:
        return ""
    d = time.time() - ts
    if d < 60:
        return "now"
    if d < 3600:
        return f"{int(d // 60)}m"
    if d < 86400:
        return f"{int(d // 3600)}h"
    return time.strftime("%d %b", time.localtime(ts))


class NotesPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.store = controller.notes
        self.current_id = None

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(14)
        head, right = page_header(
            "Notes", "Scratch notes that save themselves. The first line is "
                     "the title.")
        right.addWidget(button("New note", "Primary", self.new_note,
                               tip="Ctrl+N", icon_name="add"))
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)

        side = Card("All notes")
        side.setFixedWidth(270)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search notes…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self._reload())
        side.add(self.search)
        self.list = rich_list(QListWidget())
        self.list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list.setMinimumHeight(260)
        self.list.currentItemChanged.connect(self._on_select)
        side.add(self.list)
        body.addWidget(side)

        self.editor_card = Card("Note")
        self.pin_btn = button("Pin", "GhostSmall", self._toggle_pin)
        self._note_buttons = [self.pin_btn,
                              button("Copy", "GhostSmall", self._copy, icon_name="copy"),
                              button("Delete", "GhostSmall", self._delete)]
        for b in self._note_buttons:
            self.editor_card.header_row.addWidget(b)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Start typing…")
        self.editor.setMinimumHeight(260)
        self.editor.textChanged.connect(self._edited)
        self.editor_card.add(self.editor)
        self.editor_card.body().setStretchFactor(self.editor, 1)
        self.stats = small_label("")
        self.editor_card.add(self.stats)
        body.addWidget(self.editor_card, 1)
        root.addLayout(body, 1)

        sc = QShortcut(QKeySequence(QKeySequence.New), self)
        sc.activated.connect(self.new_note)
        find = QShortcut(QKeySequence(QKeySequence.Find), self)
        find.activated.connect(lambda: (self.search.setFocus(), self.search.selectAll()))

        self.store.changed.connect(self._store_changed)
        self._reload()
        if self.store.items:
            self.list.setCurrentRow(0)
        else:
            self._show(None)

    def _reload(self):
        q = self.search.text().strip().lower()
        self.list.blockSignals(True)
        self.list.clear()
        for n in self.store.sorted():
            if q and q not in n["text"].lower():
                continue
            body = n["text"].strip().split("\n", 1)
            sub = " ".join(body[1].split())[:120] if len(body) > 1 else ""
            it = QListWidgetItem()
            set_item(it, self.store.title_of(n), sub or "No additional text",
                     glyph="pinned" if n["pinned"] else "notes",
                     color=ACCENT if n["pinned"] else None,
                     right=_when(n["updated"]))
            it.setData(Qt.UserRole, n["id"])
            self.list.addItem(it)
            if n["id"] == self.current_id:
                self.list.setCurrentItem(it)
        if not self.list.count():
            it = QListWidgetItem()
            set_item(it, "No notes" if not q else "No matches",
                     "Ctrl+N creates one" if not q else "", dim=True)
            it.setFlags(Qt.NoItemFlags)
            self.list.addItem(it)
        self.list.blockSignals(False)

    def _store_changed(self):
        if not self.editor.hasFocus():
            self._reload()
            self._select_first_if_none()

    def _select_first_if_none(self):
        if self.current_id is None and self.store.items:
            self.list.setCurrentRow(0)

    def _on_select(self, item, _prev=None):
        if item is None or item.data(Qt.UserRole) is None:
            return
        self._show(item.data(Qt.UserRole))

    def _show(self, nid):
        self.current_id = nid
        n = self.store.get(nid) if nid else None
        self.editor.blockSignals(True)
        self.editor.setPlainText(n["text"] if n else "")
        self.editor.blockSignals(False)
        for b in self._note_buttons:
            b.setEnabled(n is not None)
        self.pin_btn.setText("Unpin" if n and n["pinned"] else "Pin")
        self._update_stats()

    def new_note(self, text: str = ""):
        n = self.store.add(text if isinstance(text, str) else "")
        self.search.clear()
        self.current_id = n["id"]
        self._reload()
        self._show(n["id"])
        self.editor.setFocus()
        cur = self.editor.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        self.editor.setTextCursor(cur)

    def open_note(self, nid: str):
        self.search.clear()
        self.current_id = nid
        self._reload()
        self._show(nid)
        self.editor.setFocus()

    def _edited(self):
        if not self.current_id:
            text = self.editor.toPlainText()
            if not text.strip():
                return
            n = self.store.add(text)
            self.current_id = n["id"]
            self._reload()
            for b in self._note_buttons:
                b.setEnabled(True)
            self._update_stats()
            return
        self.store.update(self.current_id, self.editor.toPlainText())
        self._update_stats()
        item = self.list.currentItem()
        n = self.store.get(self.current_id)
        if item and n:
            body = n["text"].strip().split("\n", 1)
            sub = " ".join(body[1].split())[:120] if len(body) > 1 else ""
            set_item(item, self.store.title_of(n), sub or "No additional text",
                     glyph="pinned" if n["pinned"] else "notes",
                     color=ACCENT if n["pinned"] else None, right="now")
            item.setData(Qt.UserRole, n["id"])

    def _update_stats(self):
        s = transforms.stats(self.editor.toPlainText())
        self.stats.setText(f"{s['words']:,} words · {s['chars']:,} characters · "
                           f"{s['lines']:,} lines · saved automatically"
                           if self.current_id else "")

    def _toggle_pin(self):
        n = self.store.get(self.current_id) if self.current_id else None
        if n:
            self.store.set_pinned(n["id"], not n["pinned"])
            self.pin_btn.setText("Unpin" if n["pinned"] else "Pin")
            self._reload()

    def _copy(self):
        if self.current_id and self.ctrl.clipboard:
            self.ctrl.clipboard.copy(self.editor.toPlainText())
            self.ctrl.toast.emit("Note copied")

    def _delete(self):
        n = self.store.get(self.current_id) if self.current_id else None
        if not n:
            return
        if n["text"].strip() and not confirm(
                self, "Delete note", f"Delete '{self.store.title_of(n)}'?"):
            return
        self.store.delete(n["id"])
        self.current_id = None
        self._reload()
        if self.list.count() and self.store.items:
            self.list.setCurrentRow(0)
        else:
            self._show(None)

    def sync(self):
        self._reload()
        self._select_first_if_none()
