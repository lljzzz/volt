import os

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QLineEdit, QMenu,
                               QPushButton, QVBoxLayout, QWidget)

from core.hotkeys import combo_to_text
from .hotkey_button import HotkeyButton
from .widgets import (Card, ToggleSwitch, button, flow_row, hint, page_header,
                      small_label)

RECENT = 12
THUMB = QSize(132, 84)


class CapturePage(QWidget):
    def __init__(self, controller, on_change, tool):
        super().__init__()
        self.ctrl = controller
        self.on_change = on_change
        self.tool = tool
        self.cfg = controller.config.setdefault("capture", {})

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)
        head, _right = page_header(
            "Screen capture", "Freeze the screen, drag a region, done. The shot "
                              "lands on your clipboard and in your capture folder.")
        root.addLayout(head)

        go = Card("Capture")
        self.hk_hint = hint("")
        go.add(flow_row(
            button("Capture region", "Primary",
                   lambda: tool.start("region", hide_window=True), icon_name="capture"),
            button("Full screen", "Ghost", lambda: tool.start("full", hide_window=True)),
            button("Region in 3 s", "Ghost",
                   lambda: tool.start("region", delay=3, hide_window=True),
                   tip="Time to open a menu or hover something first"),
            button("Region + pin", "Ghost",
                   lambda: tool.start("region", pin=True, hide_window=True),
                   tip="Keep the capture floating on top of everything"),
            spacing=8))
        go.add(self.hk_hint)
        root.addWidget(go)

        st = Card("Settings")
        self.hk = HotkeyButton(controller.hotkeys, self.cfg.get("hotkey", []), hid="capture")
        self.hk.captured.connect(self._set_hotkey)
        st.setting("Capture hotkey (region)", self.hk)
        for key, label, default in (("copy", "Copy to clipboard", True),
                                    ("save", "Save as PNG", True),
                                    ("notify", "Show a notice after capturing", True)):
            sw = ToggleSwitch(self.cfg.get(key, default))
            sw.toggled.connect(lambda v, k=key: self._set(k, v))
            st.setting(label, sw)
        self.folder_edit = QLineEdit(tool.folder())
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setMinimumWidth(260)
        st.setting("Folder", self.folder_edit,
                   button("Change…", "GhostSmall", self._pick_folder),
                   button("Open", "GhostSmall", self._open_folder))
        root.addWidget(st)

        self.recent_card = Card("Recent captures")
        self.recent_card.header_row.addWidget(
            button("Refresh", "GhostSmall", self.refresh_recent))
        self.recent_box = QVBoxLayout()
        self.recent_card.body().addLayout(self.recent_box)
        root.addWidget(self.recent_card)
        root.addStretch()

        tool.captured.connect(lambda _p: self.refresh_recent())
        self._update_hint()

    def _set(self, key, value):
        self.cfg[key] = value
        self.on_change()

    def _set_hotkey(self, combo):
        self.cfg["hotkey"] = combo
        self.on_change()
        self.ctrl.refresh_hotkeys()
        self._update_hint()

    def _update_hint(self):
        hk = self.cfg.get("hotkey")
        on = self.cfg.get("enabled", True)
        if hk and on:
            self.hk_hint.setText(f"Or press {combo_to_text(hk)} anywhere. "
                                 "Enter grabs the whole screen, Esc cancels.")
        else:
            self.hk_hint.setText("No global hotkey set - add one below, or use "
                                 "the palette / tray menu.")

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Capture folder", self.tool.folder())
        if d:
            self.cfg["folder"] = d
            self.on_change()
            self.folder_edit.setText(d)
            self.refresh_recent()

    def _open_folder(self):
        folder = self.tool.folder()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh_recent()
        self._update_hint()

    def _recent_files(self) -> list[str]:
        folder = self.tool.folder()
        try:
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if f.lower().endswith(".png")]
        except OSError:
            return []
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return files[:RECENT]

    def refresh_recent(self):
        if not self.isVisible():
            return
        while self.recent_box.count():
            w = self.recent_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        files = self._recent_files()
        if not files:
            self.recent_box.addWidget(small_label("No captures yet."))
            return
        thumbs = []
        for path in files:
            reader = QImageReader(path)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(THUMB, Qt.KeepAspectRatio))
            img = reader.read()
            b = QPushButton(objectName="GhostSmall")
            b.setFixedSize(THUMB + QSize(10, 10))
            b.setIcon(QPixmap.fromImage(img))
            b.setIconSize(THUMB)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(f"{os.path.basename(path)} - click to open, right-click for more")
            b.clicked.connect(lambda _=False, p=path: QDesktopServices.openUrl(
                QUrl.fromLocalFile(p)))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, p=path, btn=b: self._thumb_menu(btn, pos, p))
            thumbs.append(b)
        self.recent_box.addWidget(flow_row(*thumbs, spacing=8))

    def _thumb_menu(self, btn, pos, path):
        m = QMenu(self)
        m.addAction("Open", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
        m.addAction("Copy image", lambda: self._copy_file(path))
        m.addAction("Pin on screen", lambda: self.tool.pin(QPixmap(path)))
        m.addAction("Show folder", self._open_folder)
        m.exec(btn.mapToGlobal(pos))

    def _copy_file(self, path):
        QApplication.clipboard().setPixmap(QPixmap(path))
        self.ctrl.toast.emit("Image copied")
