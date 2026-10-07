import os
import time

from PySide6.QtCore import QObject, QPoint, QRect, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QWidget

from .styles import ACCENT


def default_folder() -> str:
    pics = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
    return os.path.normpath(os.path.join(pics or os.path.expanduser("~"), "Volt"))


class _Overlay(QWidget):
    def __init__(self, tool, screen, pixmap):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.tool = tool
        self.pm = pixmap
        self.setGeometry(screen.geometry())
        self._origin = None
        self._sel = QRect()
        self._mouse = QPoint(-1, -1)

    def showEvent(self, e):
        super().showEvent(e)
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def _phys(self, r: QRect) -> QRect:
        dpr = self.pm.devicePixelRatio()
        return QRect(round(r.x() * dpr), round(r.y() * dpr),
                     round(r.width() * dpr), round(r.height() * dpr))

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.pm)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))
        f = QFont(self.font())
        f.setPixelSize(12)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        if not self._sel.isNull():
            sel = self._sel.normalized()
            p.drawPixmap(sel, self.pm, self._phys(sel))
            p.setPen(QPen(QColor(ACCENT), 1))
            p.drawRect(sel.adjusted(0, 0, -1, -1))
            phys = self._phys(sel)
            label = f"{phys.width()} × {phys.height()}"
            tw = p.fontMetrics().horizontalAdvance(label) + 14
            box = QRect(sel.x(), sel.y() - 24 if sel.y() > 28 else sel.bottom() + 4, tw, 20)
            p.fillRect(box, QColor(20, 21, 24, 225))
            p.setPen(QColor("#ffffff"))
            p.drawText(box, Qt.AlignCenter, label)
        elif self.rect().contains(self._mouse):
            p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DashLine))
            p.drawLine(0, self._mouse.y(), self.width(), self._mouse.y())
            p.drawLine(self._mouse.x(), 0, self._mouse.x(), self.height())
            tip = "Drag to capture  ·  Enter = whole screen  ·  Esc = cancel"
            tw = p.fontMetrics().horizontalAdvance(tip) + 24
            box = QRect((self.width() - tw) // 2, 28, tw, 30)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(20, 21, 24, 230))
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor("#e6e6e6"))
            p.drawText(box, Qt.AlignCenter, tip)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.tool.cancel()
            return
        if e.button() == Qt.LeftButton:
            self._origin = e.position().toPoint()
            self._sel = QRect(self._origin, self._origin)
            self.update()

    def mouseMoveEvent(self, e):
        self._mouse = e.position().toPoint()
        if self._origin is not None:
            self._sel = QRect(self._origin, self._mouse).normalized()
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._origin is None:
            return
        sel = self._sel.normalized()
        self._origin = None
        if sel.width() < 4 or sel.height() < 4:
            self._sel = QRect()
            self.update()
            return
        crop = self.pm.copy(self._phys(sel))
        crop.setDevicePixelRatio(1.0)
        self.tool.finish(crop)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.tool.cancel()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            full = self.pm.copy()
            full.setDevicePixelRatio(1.0)
            self.tool.finish(full)


class PinWindow(QWidget):
    def __init__(self, pixmap, on_copy=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.pm = pixmap
        self._on_copy = on_copy
        self._scale = 1.0
        self._drag = None
        dpr = self.devicePixelRatioF() or 1.0
        self._base = (pixmap.width() / dpr, pixmap.height() / dpr)
        self._apply_scale()
        self.move(QCursor.pos() - QPoint(int(self.width() / 2), int(self.height() / 2)))
        self.setToolTip("Drag to move · wheel to zoom · double-click or Esc to close")

    def _apply_scale(self):
        self.resize(max(24, int(self._base[0] * self._scale)),
                    max(24, int(self._base[1] * self._scale)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(self.rect(), self.pm)
        p.setPen(QPen(QColor(ACCENT), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def wheelEvent(self, e):
        step = 1.1 if e.angleDelta().y() > 0 else 1 / 1.1
        self._scale = min(4.0, max(0.2, self._scale * step))
        center = self.geometry().center()
        self._apply_scale()
        self.move(center - QPoint(self.width() // 2, self.height() // 2))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.addAction("Copy image", self._copy)
        m.addAction("Save as…", self._save_as)
        m.addAction("Reset zoom", self._reset)
        m.addSeparator()
        m.addAction("Close", self.close)
        m.exec(e.globalPos())

    def _copy(self):
        QApplication.clipboard().setPixmap(self.pm)
        if self._on_copy:
            self._on_copy()

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save image", os.path.join(default_folder(), "pinned.png"),
            "PNG image (*.png)")
        if path:
            self.pm.save(path, "PNG")

    def _reset(self):
        self._scale = 1.0
        self._apply_scale()


class CaptureTool(QObject):
    captured = Signal(str)

    def __init__(self, controller, window=None):
        super().__init__()
        self.ctrl = controller
        self.win = window
        self._overlays: list[_Overlay] = []
        self._pins: list[PinWindow] = []
        self._pin_next = False
        self._restore_window = False

    @property
    def cfg(self) -> dict:
        return self.ctrl.config.setdefault("capture", {})

    def folder(self) -> str:
        return self.cfg.get("folder") or default_folder()

    def active(self) -> bool:
        return bool(self._overlays)

    def start(self, mode="region", delay=0, pin=False, hide_window=False):
        if self._overlays:
            return
        if hide_window and self.win is not None and self.win.isVisible():
            self._restore_window = True
            self.win.hide()
            delay = max(delay, 0.25)
        if delay:
            QTimer.singleShot(int(delay * 1000), lambda: self.start(mode, 0, pin))
            return
        self._pin_next = pin
        if mode == "full":
            screen = (QGuiApplication.screenAt(QCursor.pos())
                      or QGuiApplication.primaryScreen())
            pm = screen.grabWindow(0)
            pm.setDevicePixelRatio(1.0)
            self.finish(pm)
            return
        shots = [(s, s.grabWindow(0)) for s in QGuiApplication.screens()]
        for screen, pm in shots:
            ov = _Overlay(self, screen, pm)
            self._overlays.append(ov)
        for ov in self._overlays:
            ov.show()
        under = QGuiApplication.screenAt(QCursor.pos())
        for ov in self._overlays:
            if under is not None and ov.geometry().contains(QCursor.pos()):
                ov.activateWindow()

    def _close_overlays(self):
        for ov in self._overlays:
            ov.close()
        self._overlays = []
        if self._restore_window and self.win is not None:
            self._restore_window = False
            self.win.showNormal() if not self.win.isMaximized() else self.win.show()

    def cancel(self):
        self._close_overlays()

    def finish(self, pixmap):
        self._close_overlays()
        cfg = self.cfg
        path, bits = "", []
        if cfg.get("copy", True):
            QApplication.clipboard().setPixmap(pixmap)
            bits.append("copied")
        if cfg.get("save", True):
            folder = self.folder()
            try:
                os.makedirs(folder, exist_ok=True)
                name = time.strftime("Volt_%Y-%m-%d_%H-%M-%S")
                path = os.path.join(folder, f"{name}.png")
                n = 2
                while os.path.exists(path):
                    path = os.path.join(folder, f"{name}_{n}.png")
                    n += 1
                if pixmap.save(path, "PNG"):
                    bits.append("saved")
                else:
                    path = ""
            except OSError as e:
                path = ""
                self.ctrl.toast.emit(f"Couldn't save capture: {e}")
        if self._pin_next:
            self.pin(pixmap)
            bits.append("pinned")
        if cfg.get("notify", True):
            msg = f"Captured {pixmap.width()} × {pixmap.height()}"
            self.ctrl.toast.emit(f"{msg} - {', '.join(bits)}" if bits else msg)
        self.captured.emit(path)

    def pin(self, pixmap):
        w = PinWindow(pixmap, on_copy=lambda: self.ctrl.toast.emit("Image copied"))
        w.destroyed.connect(lambda *_: self._pins.remove(w) if w in self._pins else None)
        self._pins.append(w)
        w.show()
        w.activateWindow()
