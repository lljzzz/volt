from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QMenu,
                               QPushButton, QVBoxLayout, QWidget)

from core import picker as pk
from .hotkey_button import HotkeyButton
from .styles import BORDER_2
from .widgets import Card, Segmented, ToggleSwitch, button, page_header, small_label

HISTORY_MAX = 32
SWATCHES_PER_ROW = 16
LOUPE_RADIUS = 5


class Loupe(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(110, 110)
        self.pm = None

    def set_pixmap(self, pm):
        self.pm = pm
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.fillRect(r, QColor("#0f1012"))
        if self.pm is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            p.drawPixmap(r, self.pm)
            side = LOUPE_RADIUS * 2 + 1
            cell = r.width() / side
            c = QRect(int(LOUPE_RADIUS * cell), int(LOUPE_RADIUS * cell),
                      int(cell) + 1, int(cell) + 1)
            p.setPen(QPen(QColor("#000000"), 3))
            p.drawRect(c)
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.drawRect(c)
        p.setPen(QColor(BORDER_2))
        p.drawRect(r)


class PickerPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.cfg = controller.config["picker"]
        self.on_change = on_change
        self._rgb = (0, 0, 0)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)
        head, _right = page_header(
            "Color picker", "Grab any pixel on screen with a hotkey; it's copied "
                            "and saved to your swatches.")
        root.addLayout(head)

        root.addWidget(self._live_card())
        root.addWidget(self._capture_card())
        root.addWidget(self._history_card())
        root.addStretch()

        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._live_tick)

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _live_card(self):
        c = Card("Under the cursor", subtitle="Click a value to copy it.")
        row = QHBoxLayout()
        row.setSpacing(16)
        self.loupe = Loupe()
        row.addWidget(self.loupe)
        self.swatch = QFrame()
        self.swatch.setFixedSize(110, 110)
        row.addWidget(self.swatch)
        col = QVBoxLayout()
        col.setSpacing(6)
        self.values = {}
        for kind, _label in pk.FORMATS:
            b = QPushButton("", objectName="GhostSmall")
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("text-align:left; padding:6px 12px; font-size:13px;")
            b.setMinimumWidth(190)
            b.clicked.connect(lambda _=False, k=kind: self._copy_rgb(self._rgb, k))
            col.addWidget(b)
            self.values[kind] = b
        self.pos_lbl = small_label("(0, 0)")
        col.addWidget(self.pos_lbl)
        col.addStretch()
        row.addLayout(col)
        row.addStretch()
        c.body().addLayout(row)
        self._show_rgb((0, 0, 0))
        return c

    def _show_rgb(self, rgb):
        self._rgb = rgb
        hx = pk.to_hex(rgb)
        self.swatch.setStyleSheet(
            f"background:{hx}; border:1px solid {BORDER_2}; border-radius:10px;")
        for kind, b in self.values.items():
            b.setText(pk.fmt(rgb, kind))

    def _live_tick(self):
        pos = QCursor.pos()
        rgb = pk.pixel_at(pos.x(), pos.y())
        if rgb is None:
            return
        self._show_rgb(rgb)
        self.pos_lbl.setText(f"({pos.x()}, {pos.y()})")
        self.loupe.set_pixmap(pk.grab_around(pos.x(), pos.y(), LOUPE_RADIUS))

    def _capture_card(self):
        c = Card("Capture")
        self.hk_btn = HotkeyButton(self.ctrl.hotkeys, self.cfg.get("hotkey", []),
                                   hid="picker")
        self.hk_btn.captured.connect(self._set_hotkey)
        c.setting("Pick hotkey (works anywhere)", self.hk_btn)

        self.fmt_seg = Segmented(pk.FORMATS, self.cfg.get("format", "hex"))
        self.fmt_seg.changed.connect(self._set_format)
        c.setting("Copy format", self.fmt_seg)

        auto = ToggleSwitch(self.cfg.get("auto_copy", True))
        auto.toggled.connect(lambda v: self._set("auto_copy", v))
        c.setting("Copy to clipboard on pick", auto)

        notify = ToggleSwitch(self.cfg.get("notify", True))
        notify.toggled.connect(lambda v: self._set("notify", v))
        c.setting("Show a notice on pick", notify)
        return c

    def _set(self, key, value):
        self.cfg[key] = value
        self.on_change()

    def _set_format(self, v):
        self._set("format", v)
        self._refresh_history()

    def _set_hotkey(self, combo):
        self.cfg["hotkey"] = combo
        self.on_change()
        self.ctrl.refresh_hotkeys()

    def _history_card(self):
        c = Card("Swatches")
        c.header_row.addWidget(button("Clear", "GhostSmall", self._clear))
        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        self.grid.setAlignment(Qt.AlignLeft)
        c.body().addLayout(self.grid)
        self.hist_hint = small_label("")
        c.add(self.hist_hint)
        self._refresh_history()
        return c

    def history(self) -> list[str]:
        return self.cfg.setdefault("history", [])

    def _refresh_history(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        hist = self.history()
        for i, hx in enumerate(hist):
            b = QPushButton(objectName="Swatch")
            b.setFixedSize(30, 30)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(f"{hx} - click to copy, right-click to remove")
            b.setStyleSheet(f"background:{hx}; border:1px solid {BORDER_2};")
            b.clicked.connect(lambda _=False, h=hx: self._copy_rgb(pk.from_hex(h)))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, h=hx, btn=b: self._swatch_menu(btn, pos, h))
            self.grid.addWidget(b, i // SWATCHES_PER_ROW, i % SWATCHES_PER_ROW)
        self.hist_hint.setText(
            f"{len(hist)} colors - click to copy as "
            f"{self.cfg.get('format', 'hex').upper()}"
            if hist else "No colors yet - press the pick hotkey over anything.")

    def _swatch_menu(self, btn, pos, hx):
        m = QMenu(self)
        rgb = pk.from_hex(hx)
        for kind, label in pk.FORMATS:
            m.addAction(f"Copy {pk.fmt(rgb, kind)}",
                        lambda k=kind: self._copy_rgb(rgb, k))
        m.addSeparator()
        m.addAction("Remove", lambda: self._remove(hx))
        m.exec(btn.mapToGlobal(pos))

    def _remove(self, hx):
        if hx in self.history():
            self.history().remove(hx)
            self.on_change()
            self._refresh_history()

    def _copy_rgb(self, rgb, kind=None):
        text = pk.fmt(rgb, kind or self.cfg.get("format", "hex"))
        if self.ctrl.clipboard:
            self.ctrl.clipboard.copy(text)
            self.ctrl.toast.emit(f"Copied {text}")

    def _clear(self):
        self.history().clear()
        self.on_change()
        self._refresh_history()

    def add_capture(self, x: int, y: int, rgb) -> str:
        hx = pk.to_hex(rgb)
        hist = self.history()
        if hx in hist:
            hist.remove(hx)
        hist.insert(0, hx)
        del hist[HISTORY_MAX:]
        self.on_change()
        self._refresh_history()
        formatted = pk.fmt(rgb, self.cfg.get("format", "hex"))
        if self.cfg.get("auto_copy", True) and self.ctrl.clipboard:
            self.ctrl.clipboard.copy(formatted)
        return formatted
