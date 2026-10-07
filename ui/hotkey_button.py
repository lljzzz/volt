from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QMenu, QPushButton

from core.hotkeys import combo_to_text


class HotkeyButton(QPushButton):
    captured = Signal(list)
    _got = Signal(list)
    _cancelled = Signal()

    conflict_fn = None
    notify = None

    def __init__(self, hotkey_manager, combo: list[str] = None, hid: str = None):
        super().__init__(objectName="Hotkey")
        self._mgr = hotkey_manager
        self._combo = list(combo or [])
        self._hid = hid
        self._capturing = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumWidth(110)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self._got.connect(self._on_got)
        self._cancelled.connect(self._on_cancelled)
        self._cb = lambda keys: self._got.emit(list(keys))
        self._cancel_cb = lambda: self._cancelled.emit()
        self.clicked.connect(self._begin)
        self._render()

    def combo(self):
        return self._combo

    def setCombo(self, combo):
        self._combo = list(combo or [])
        self._render()

    def set_hid(self, hid):
        self._hid = hid

    def _render(self):
        if self._capturing:
            self.setText("Press keys…  (Esc cancels)")
        else:
            self.setText(combo_to_text(self._combo) if self._combo else "Not set")
        self.setProperty("capturing", self._capturing)
        self.setProperty("empty", not self._combo and not self._capturing)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setToolTip("Click, then press the new combo. Esc cancels, "
                        "Backspace clears. Right-click for options.")

    def _begin(self):
        if self._capturing:
            self._mgr.cancel_capture(self._cb)
            return
        self._capturing = True
        self.setFocus(Qt.MouseFocusReason)
        self._render()
        self._mgr.begin_capture(self._cb, self._cancel_cb)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if self._capturing:
            self._mgr.cancel_capture(self._cb)

    def _on_cancelled(self):
        self._capturing = False
        self._render()

    def _on_got(self, keys):
        self._capturing = False
        self._combo = keys
        self._render()
        if keys and HotkeyButton.conflict_fn and HotkeyButton.notify:
            msg = HotkeyButton.conflict_fn(keys, self._hid)
            if msg:
                HotkeyButton.notify(f"Heads up: {msg}")
        self.captured.emit(keys)

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("Change…", self._begin)
        clear = m.addAction("Clear hotkey", self._clear)
        clear.setEnabled(bool(self._combo))
        m.exec(self.mapToGlobal(pos))

    def _clear(self):
        if self._capturing:
            self._mgr.cancel_capture(self._cb)
        self._combo = []
        self._render()
        self.captured.emit([])
