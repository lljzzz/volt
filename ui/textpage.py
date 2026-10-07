import secrets
import string
import time
import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QLabel, QPlainTextEdit,
                               QSpinBox, QVBoxLayout, QWidget)

from core import transforms
from .widgets import Card, button, flow_row, page_header, small_label


class TextPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(14)
        head, right = page_header(
            "Text tools", "Paste text, transform it, copy it back. Transforms "
                          "work on the selection when there is one.")
        right.addWidget(button("Paste", "Ghost", self._paste, icon_name="paste"))
        right.addWidget(button("Copy", "Primary", self._copy, icon_name="copy"))
        root.addLayout(head)

        ed_card = Card("Text")
        ed_card.header_row.addWidget(button("Clear", "GhostSmall", self._clear))
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Paste or type text here…")
        self.edit.setMinimumHeight(200)
        self.edit.textChanged.connect(self._update_stats)
        self.edit.selectionChanged.connect(self._update_stats)
        ed_card.add(self.edit)
        ed_card.body().setStretchFactor(self.edit, 1)
        self.stats = small_label("")
        ed_card.add(self.stats)
        self.err = QLabel("", objectName="Error")
        self.err.setVisible(False)
        ed_card.add(self.err)
        root.addWidget(ed_card, 1)

        tr = Card("Transform")
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for r, group in enumerate(transforms.GROUPS):
            lbl = small_label(group)
            lbl.setFixedWidth(56)
            grid.addWidget(lbl, r, 0, Qt.AlignTop)
            btns = [button(label, "GhostSmall", lambda _=False, fn=fn: self._apply(fn))
                    for _key, label, fn, g in transforms.TRANSFORMS if g == group]
            grid.addWidget(flow_row(*btns), r, 1)
        grid.setColumnStretch(1, 1)
        tr.body().addLayout(grid)
        root.addWidget(tr)

        gen = Card("Generate", subtitle="Inserted at the cursor.")
        self.pw_len = QSpinBox()
        self.pw_len.setRange(6, 128)
        self.pw_len.setValue(20)
        self.pw_len.setSuffix(" chars")
        self.pw_len.setFixedWidth(110)
        self.pw_sym = QCheckBox("Symbols")
        self.pw_sym.setChecked(True)
        gen.add(flow_row(
            button("UUID", "GhostSmall", lambda: self._insert(str(uuid.uuid4()))),
            button("Unix time", "GhostSmall", lambda: self._insert(str(int(time.time())))),
            button("ISO date-time", "GhostSmall",
                   lambda: self._insert(time.strftime("%Y-%m-%dT%H:%M:%S"))),
            "    Password", self.pw_len, self.pw_sym,
            button("Generate", "GhostSmall", self._password)))
        root.addWidget(gen)
        self._update_stats()

    def _target(self):
        cur = self.edit.textCursor()
        if cur.hasSelection():
            return cur, cur.selectedText().replace("\u2029", "\n")
        return None, self.edit.toPlainText()

    def _apply(self, fn):
        cur, text = self._target()
        if not text:
            self.ctrl.toast.emit("Nothing to transform yet")
            return
        out, err = transforms.apply(fn, text)
        self.err.setVisible(bool(err))
        if err:
            self.err.setText(f"Can't transform: {err}")
            return
        if cur is not None:
            cur.insertText(out)
        else:
            c = self.edit.textCursor()
            c.select(c.SelectionType.Document)
            c.insertText(out)

    def _insert(self, text):
        self.edit.insertPlainText(text)
        self.edit.setFocus()

    def _password(self):
        alphabet = string.ascii_letters + string.digits
        if self.pw_sym.isChecked():
            alphabet += "!@#$%^&*-_=+?"
        n = self.pw_len.value()
        while True:
            pw = "".join(secrets.choice(alphabet) for _ in range(n))
            if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                    and any(c.isdigit() for c in pw)
                    and (not self.pw_sym.isChecked()
                         or any(not c.isalnum() for c in pw))):
                break
        self._insert(pw)

    def _update_stats(self):
        s = transforms.stats(self.edit.toPlainText())
        sel = self.edit.textCursor().selectedText()
        extra = f" · {len(sel):,} selected" if sel else ""
        self.stats.setText(f"{s['chars']:,} characters · {s['words']:,} words · "
                           f"{s['lines']:,} lines · {s['bytes']:,} bytes{extra}")
        self.err.setVisible(False)

    def _paste(self):
        if self.ctrl.clipboard:
            self.edit.setPlainText(self.ctrl.clipboard.latest_text())
            self.edit.setFocus()

    def _copy(self):
        cur, text = self._target()
        if text and self.ctrl.clipboard:
            self.ctrl.clipboard.copy(text)
            self.ctrl.toast.emit("Selection copied" if cur else "Text copied")

    def _clear(self):
        self.edit.clear()
        self.edit.setFocus()
