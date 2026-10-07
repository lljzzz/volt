import os
import sys
import time

from PySide6.QtCore import QProcess, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout,
                               QLabel, QMenu, QPushButton, QScrollArea,
                               QStackedWidget, QSystemTrayIcon, QVBoxLayout,
                               QWidget)

from core import config as cfg_store
from core import instance
from core.clipboard import ClipboardWatcher
from core.controller import Controller
from core.notes import NotesStore
from core.timers import TimerManager
from ui import icons
from ui.autoclicker import AutoclickerPage
from ui.capture import CaptureTool
from ui.capturepage import CapturePage
from ui.clipboard import ClipboardPage
from ui.dashboard import DashboardPage
from ui.hotkey_button import HotkeyButton
from ui.macro import MacroPage
from ui.notes import NotesPage
from ui.nudge import NudgePage
from ui.palette import Palette
from ui.picker import PickerPage
from ui.settings import SettingsPage
from ui.snippets import SnippetsPage
from ui.styles import ACCENT, ACCENT_INK, GREEN, QSS
from ui.textpage import TextPage
from ui.timers import TimersPage
from ui.widgets import NavButton, Toast

VERSION = "0.7"
APP_TITLE = "Volt"

SECTIONS = [
    (None, [("Dashboard", "dashboard")]),
    ("AUTOMATE", [("Autoclicker", "autoclicker"), ("Macros", "macros"),
                  ("Snippets", "snippets")]),
    ("PRODUCTIVITY", [("Clipboard", "clipboard"), ("Notes", "notes"),
                      ("Text", "text"), ("Timers", "timers")]),
    ("SCREEN", [("Capture", "capture"), ("Picker", "picker"), ("Nudge", "nudge")]),
]
NAV = [e for _s, entries in SECTIONS for e in entries] + [("Settings", "settings")]


def make_icon(bg: str = ACCENT) -> QIcon:
    ic = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(bg))
        p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), size * 0.26, size * 0.26)
        p.setPen(QColor(ACCENT_INK))
        if icons.family():
            p.setFont(icons.font(int(size * 0.62)))
            p.drawText(pm.rect(), Qt.AlignCenter, icons.glyph("bolt"))
        else:
            f = p.font()
            f.setBold(True)
            f.setPixelSize(int(size * 0.6))
            p.setFont(f)
            p.drawText(pm.rect(), Qt.AlignCenter, "V")
        p.end()
        ic.addPixmap(pm)
    return ic


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__(objectName="TitleBar")
        self.win = window
        self.setFixedHeight(38)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 6, 0)
        lay.setSpacing(6)
        logo = QLabel(icons.glyph("bolt"), objectName="TitleLogo")
        logo.setStyleSheet(icons.css(14))
        lay.addWidget(logo)
        lay.addWidget(QLabel("VOLT", objectName="TitleText"))
        lay.addStretch()
        self.pin_btn = self._btn("pin", "Keep Volt on top of other windows", checkable=True)
        self.pin_btn.toggled.connect(window.set_always_on_top)
        self.min_btn = self._btn("min", "Minimize", window.showMinimized)
        self.max_btn = self._btn("max", "Maximize", window.toggle_maximized)
        self.close_btn = self._btn("close", "Close (Volt keeps running in the tray)",
                                   window.close, name="WinBtnClose")
        for b in (self.pin_btn, self.min_btn, self.max_btn, self.close_btn):
            lay.addWidget(b)
        self._drag = None

    def _btn(self, glyph, tip, slot=None, checkable=False, name="WinBtn"):
        b = QPushButton(icons.glyph(glyph), objectName=name, checkable=checkable)
        b.setStyleSheet(icons.css(10))
        b.setFixedSize(42, 30)
        b.setToolTip(tip)
        b.setFocusPolicy(Qt.NoFocus)
        if slot:
            b.clicked.connect(slot)
        return b

    def set_maximized(self, on: bool):
        self.max_btn.setText(icons.glyph("restore" if on else "max"))
        self.max_btn.setToolTip("Restore" if on else "Maximize")

    def set_pinned(self, on: bool):
        self.pin_btn.setText(icons.glyph("pinned" if on else "pin"))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.win.is_max():
                gp = e.globalPosition().toPoint()
                frac = e.position().x() / max(1, self.width())
                self.win.set_max(False)
                g = self.win.geometry()
                self.win.move(int(gp.x() - g.width() * frac), gp.y() - int(e.position().y()))
            h = self.win.windowHandle()
            if not (h and h.startSystemMove()):
                self._drag = e.globalPosition().toPoint() - self.win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.win.toggle_maximized()


class _Grip(QWidget):
    def __init__(self, win, edges, cursor):
        super().__init__(win)
        self._edges = edges
        self.setCursor(cursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            h = self.window().windowHandle()
            if h:
                h.startSystemResize(self._edges)


class MainWindow(QWidget):
    VERSION = VERSION
    NAV = NAV

    def __init__(self):
        super().__init__()
        self.config = cfg_store.load()
        self._quitting = False
        self._max = False
        self._normal_geo = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self.flush_save)

        self.controller = Controller(self.config)
        self.clipwatch = ClipboardWatcher(self.config, self.save)
        self.clipwatch.attach(QApplication.clipboard())
        self.controller.attach_clipboard(self.clipwatch)
        self.timers = TimerManager(self.config.setdefault("timers", {}), self.save)
        self.controller.timers = self.timers
        self.timers.finished.connect(self._on_timer_done)
        self.notes = NotesStore()
        self.controller.notes = self.notes

        self.toaster = Toast()
        self.controller.toast.connect(self.toast)
        self.controller.navigate.connect(self.navigate)
        HotkeyButton.conflict_fn = self.controller.conflict_message
        HotkeyButton.notify = self.toast

        self.setObjectName("Root")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(980, 600)
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(make_icon())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.titlebar = TitleBar(self)
        outer.addWidget(self.titlebar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._sidebar())
        self.stack = QStackedWidget()
        self.capture_tool = CaptureTool(self.controller, self)
        c, s = self.controller, self.save
        self.pages = {
            "Dashboard": DashboardPage(c, s, self.navigate),
            "Autoclicker": AutoclickerPage(c, s),
            "Macros": MacroPage(c, s),
            "Snippets": SnippetsPage(c, s),
            "Clipboard": ClipboardPage(c, s),
            "Notes": NotesPage(c, s),
            "Text": TextPage(c, s),
            "Timers": TimersPage(c, s),
            "Capture": CapturePage(c, s, self.capture_tool),
            "Picker": PickerPage(c, s),
            "Nudge": NudgePage(c, s),
            "Settings": SettingsPage(c, s, self),
        }
        self._wrappers = {}
        for name, page in self.pages.items():
            page.setObjectName("PageBody")
            sa = QScrollArea(objectName="PageScroll")
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sa.setWidget(page)
            self._wrappers[name] = sa
            self.stack.addWidget(sa)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        self.palette = Palette(self)
        E, C = Qt.Edge, Qt.CursorShape
        self._grips = {
            "l": _Grip(self, E.LeftEdge, C.SizeHorCursor),
            "r": _Grip(self, E.RightEdge, C.SizeHorCursor),
            "t": _Grip(self, E.TopEdge, C.SizeVerCursor),
            "b": _Grip(self, E.BottomEdge, C.SizeVerCursor),
            "tl": _Grip(self, E.LeftEdge | E.TopEdge, C.SizeFDiagCursor),
            "br": _Grip(self, E.RightEdge | E.BottomEdge, C.SizeFDiagCursor),
            "tr": _Grip(self, E.RightEdge | E.TopEdge, C.SizeBDiagCursor),
            "bl": _Grip(self, E.LeftEdge | E.BottomEdge, C.SizeBDiagCursor),
        }
        self._geo_timer = QTimer(self)
        self._geo_timer.setSingleShot(True)
        self._geo_timer.setInterval(600)
        self._geo_timer.timeout.connect(self._remember_geometry)

        self._build_tray()
        self._shortcuts()
        ctl = self.controller
        ctl.panic.connect(self._on_panic)
        ctl.failsafe.connect(lambda why: self.toast(f"Clicker stopped: {why}"))
        ctl.limit_reached.connect(lambda: self.toast("Clicker stopped: limit reached"))
        ctl.palette_requested.connect(lambda: self.palette.open())
        ctl.paste_plain_requested.connect(ctl.paste_plain)
        ctl.pick_requested.connect(self._on_pick)
        ctl.capture_requested.connect(lambda: self.capture_tool.start("region"))
        ctl.clicker_state.connect(lambda _r: self._status_changed())
        ctl.macro_state.connect(lambda *_: self._status_changed())
        self.timers.updated.connect(self._status_changed)

        self._restore_geometry()
        last = self.config["settings"].get("last_page", "Dashboard")
        self.navigate(last if last in self.pages else "Dashboard")

        s = self.config["settings"]
        if s.get("always_on_top"):
            self.set_always_on_top(True)
        if s.get("keep_awake"):
            from core import awake
            awake.set_keep_awake(True)
        if s.get("launch_on_startup"):
            self.apply_startup(True)
        self._activate_msg = instance.activate_message()
        instance.mark_window(int(self.winId()))
        self._apply_native_styles()
        self.timers.restore()
        self._status_changed()
        if cfg_store.LOAD_WARNING:
            QTimer.singleShot(1200, lambda: self.tray.showMessage(
                APP_TITLE, cfg_store.LOAD_WARNING, QSystemTrayIcon.Warning, 10000))

    def _sidebar(self):
        bar = QWidget(objectName="Sidebar")
        bar.setFixedWidth(178)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(2)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_btns = {}
        idx = 0

        def add(name, icon_name, shortcut):
            b = NavButton(icon_name, name, shortcut)
            b.clicked.connect(lambda _=False, n=name: self.navigate(n))
            self._nav_group.addButton(b)
            lay.addWidget(b)
            self._nav_btns[name] = b

        for section, entries in SECTIONS:
            if section:
                lay.addWidget(QLabel(section, objectName="SideSection"))
            for name, icon_name in entries:
                idx += 1
                add(name, icon_name, f"Ctrl+{idx}" if idx <= 9 else "")
        lay.addStretch()
        add("Settings", "settings", "Ctrl+0")
        ver = QLabel(f"v{VERSION}", objectName="Muted")
        ver.setStyleSheet("font-size:11px; padding: 6px 12px 0 12px;")
        lay.addWidget(ver)
        return bar

    def navigate(self, name):
        page = self.pages.get(name)
        if page is None:
            return
        if hasattr(page, "sync"):
            page.sync()
        self.stack.setCurrentWidget(self._wrappers[name])
        self._nav_btns[name].setChecked(True)
        if self.config["settings"].get("last_page") != name:
            self.config["settings"]["last_page"] = name
            self.save()

    def _shortcuts(self):
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(fn)

        for i, (name, _icon) in enumerate(NAV[:9]):
            sc(f"Ctrl+{i + 1}", lambda n=name: self.navigate(n))
        sc("Ctrl+0", lambda: self.navigate("Settings"))
        sc("Ctrl+,", lambda: self.navigate("Settings"))
        sc("Ctrl+K", lambda: self.palette.open())
        sc("Ctrl+W", self.close)
        sc("Ctrl+Q", self.quit)

    def _status_changed(self):
        c = self.controller
        running = c.clicker.running
        self._nav_btns["Autoclicker"].set_badge("" if running else None)
        n = c.running_macros()
        self._nav_btns["Macros"].set_badge(str(n) if n else None)
        t = len(self.timers.items)
        self._nav_btns["Timers"].set_badge(str(t) if t else None, ACCENT)
        busy = []
        if running:
            busy.append("clicker running")
        if n:
            busy.append(f"{n} macro{'s' if n > 1 else ''} running")
        tip = f"{APP_TITLE} - " + (", ".join(busy) if busy else "idle")
        if tip != getattr(self, "_tray_tip", None):
            self._tray_tip = tip
            self.tray.setIcon(self._icon_busy if busy else self._icon_idle)
            self.tray.setToolTip(tip)

    def toast(self, text: str):
        self.toaster.show_message(text, self)

    def _on_pick(self):
        from PySide6.QtGui import QCursor
        from core import picker as pk
        pos = QCursor.pos()
        rgb = pk.pixel_at(pos.x(), pos.y())
        if rgb is None:
            return
        formatted = self.pages["Picker"].add_capture(pos.x(), pos.y(), rgb)
        if self.config["picker"].get("notify", True):
            copied = " - copied" if self.config["picker"].get("auto_copy", True) else ""
            self.toast(f"Picked {formatted}{copied}")

    def _on_timer_done(self, label: str):
        QApplication.beep()
        self.tray.showMessage("Timer done", label or "Timer finished",
                              QSystemTrayIcon.Information, 8000)
        self.toast(f"Timer done: {label}")

    def _on_panic(self):
        self.tray.showMessage(APP_TITLE, "Failsafe triggered - everything stopped.",
                              QSystemTrayIcon.Warning, 2000)
        self.toast("Panic stop - everything stopped")

    def set_always_on_top(self, enabled: bool):
        enabled = bool(enabled)
        self.config["settings"]["always_on_top"] = enabled
        self.save()
        pin = self.titlebar.pin_btn
        if pin.isChecked() != enabled:
            pin.blockSignals(True)
            pin.setChecked(enabled)
            pin.blockSignals(False)
        self.titlebar.set_pinned(enabled)
        settings_page = self.pages.get("Settings")
        if settings_page:
            settings_page.set_on_top_state(enabled)
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
        if visible:
            self.show()
        instance.mark_window(int(self.winId()))
        self._apply_native_styles()

    def toggle_keep_awake(self, enabled: bool):
        from core import awake
        self.config["settings"]["keep_awake"] = bool(enabled)
        self.save()
        awake.set_keep_awake(enabled)
        self.pages["Settings"].set_keep_awake_state(enabled)
        self.toast("Keeping the PC awake" if enabled else "Sleep allowed again")

    def is_max(self) -> bool:
        return self._max

    def set_max(self, on: bool):
        on = bool(on)
        if on == self._max:
            return
        if on:
            self._normal_geo = self.geometry()
            self._max = True
            screen = self.screen() or QGuiApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
        else:
            self._max = False
            if self._normal_geo is not None and self._normal_geo.isValid():
                self.setGeometry(self._normal_geo)
        self.titlebar.set_maximized(on)
        self._place_grips()
        self._geo_timer.start()

    def toggle_maximized(self):
        self.set_max(not self._max)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_grips()
        self._geo_timer.start()

    def moveEvent(self, e):
        super().moveEvent(e)
        self._geo_timer.start()

    def _place_grips(self):
        w, h, t, c = self.width(), self.height(), 5, 10
        geo = {"l": QRect(0, c, t, h - 2 * c), "r": QRect(w - t, c, t, h - 2 * c),
               "t": QRect(c, 0, w - 2 * c, t), "b": QRect(c, h - t, w - 2 * c, t),
               "tl": QRect(0, 0, c, c), "tr": QRect(w - c, 0, c, c),
               "bl": QRect(0, h - c, c, c), "br": QRect(w - c, h - c, c, c)}
        maxed = self._max
        for key, grip in self._grips.items():
            grip.setGeometry(geo[key])
            grip.setVisible(not maxed)
            grip.raise_()

    def _restore_geometry(self):
        g = self.config["settings"].get("window_geometry") or []
        rect = QRect(*g) if len(g) == 4 else QRect()
        on_screen = rect.isValid() and any(
            s.availableGeometry().intersected(rect).width() >= 120 and
            s.availableGeometry().intersected(rect).height() >= 80
            for s in QGuiApplication.screens())
        if on_screen:
            self.setGeometry(rect)
        else:
            self.resize(1120, 780)
            scr = QGuiApplication.primaryScreen().availableGeometry()
            self.move(scr.center() - self.rect().center())

    def _remember_geometry(self):
        r = self._normal_geo if (self._max and self._normal_geo) else self.geometry()
        if not r.isValid() or self.isMinimized():
            return
        s = self.config["settings"]
        geo = [r.x(), r.y(), r.width(), r.height()]
        if s.get("window_geometry") != geo or s.get("window_maximized") != self._max:
            s["window_geometry"] = geo
            s["window_maximized"] = self._max
            self.save()

    def show_initial(self):
        self.show()
        if self.config["settings"].get("window_maximized"):
            self.set_max(True)

    def _apply_native_styles(self):
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_STYLE, WS_MINIMIZEBOX, WS_SYSMENU = -16, 0x00020000, 0x00080000
            u32 = ctypes.windll.user32
            get = u32.GetWindowLongPtrW
            put = u32.SetWindowLongPtrW
            get.restype = put.restype = ctypes.c_ssize_t
            get.argtypes = (ctypes.c_void_p, ctypes.c_int)
            put.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
            style = get(hwnd, GWL_STYLE)
            put(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX | WS_SYSMENU)
        except Exception as e:
            print(f"[window] {e}")

    def nativeEvent(self, event_type, message):
        if self._activate_msg:
            try:
                import ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == self._activate_msg:
                    QTimer.singleShot(0, self.restore)
                    return True, 0
            except Exception:
                pass
        return False, 0

    def restore(self):
        if self.isMinimized() or not self.isVisible():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def toggle_visible(self):
        if self.isVisible() and self.isActiveWindow() and not self.isMinimized():
            self._remember_geometry()
            self.hide()
        else:
            self.restore()

    def _build_tray(self):
        self._icon_idle = make_icon(ACCENT)
        self._icon_busy = make_icon(GREEN)
        self.tray = QSystemTrayIcon(self._icon_idle, self)
        self.tray.setToolTip(APP_TITLE)
        menu = QMenu()
        self._tray_menu = menu
        menu.addAction("Show Volt", self.restore)
        self.tray_palette = menu.addAction("Quick palette", lambda: self.palette.open())
        menu.addSeparator()
        self.tray_clicker = menu.addAction("Start autoclicker", self.controller.toggle_clicker)
        self.tray_armed = menu.addAction("Autoclicker hotkey armed")
        self.tray_armed.setCheckable(True)
        self.tray_armed.triggered.connect(self._tray_set_armed)
        menu.addAction("Stop everything", self._stop_everything)
        menu.addSeparator()
        menu.addAction("Capture screen region",
                       lambda: QTimer.singleShot(250, lambda: self.capture_tool.start("region")))
        self.tray_awake = menu.addAction("Keep PC awake")
        self.tray_awake.setCheckable(True)
        self.tray_awake.triggered.connect(self.toggle_keep_awake)
        menu.addSeparator()
        menu.addAction("Quit Volt", self.quit)
        menu.aboutToShow.connect(self._sync_tray_menu)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.toggle_visible() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def _sync_tray_menu(self):
        from core.hotkeys import combo_to_text
        s = self.config["settings"]
        pal = s.get("palette_hotkey")
        self.tray_palette.setText(f"Quick palette\t{combo_to_text(pal)}" if pal
                                  else "Quick palette")
        self.tray_clicker.setText("Stop autoclicker" if self.controller.clicker.running
                                  else "Start autoclicker")
        self.tray_armed.setChecked(self.config["autoclicker"].get("armed", True))
        self.tray_awake.setChecked(s.get("keep_awake", False))

    def _tray_set_armed(self, v: bool):
        self.config["autoclicker"]["armed"] = bool(v)
        self.save()
        self.controller.refresh_hotkeys()

    def _stop_everything(self):
        self.controller.stop_clicker()
        self.controller.stop_all_macros()

    def save(self):
        self._save_timer.start()

    def flush_save(self):
        self._save_timer.stop()
        cfg_store.save(self.config)

    def _launch_command(self, extra=()) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, *extra]
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            pyw = exe[:-10] + "pythonw.exe"
            exe = pyw if os.path.exists(pyw) else exe
        return [exe, script, *extra]

    def apply_startup(self, enabled: bool):
        if not sys.platform.startswith("win"):
            return
        try:
            import winreg
            cmd = " ".join(p if p.startswith("--") else f'"{p}"'
                           for p in self._launch_command(["--startup"]))
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            try:
                if enabled:
                    winreg.SetValueEx(key, "VOLT", 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, "VOLT")
                    except FileNotFoundError:
                        pass
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            print(f"[startup] {e}")
            self.toast(f"Couldn't update startup entry: {e}")

    def restart(self):
        self.flush_save()
        cmd = self._launch_command()
        instance.release()
        QProcess.startDetached(cmd[0], cmd[1:])
        self.quit(save=False)

    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        e.ignore()
        self._remember_geometry()
        s = self.config["settings"]
        if s.get("minimize_to_tray_on_close", True):
            self.hide()
            if not s.get("tray_hint_shown"):
                self.tray.showMessage(APP_TITLE, "Still running in the tray - "
                                      "your hotkeys keep working.",
                                      QSystemTrayIcon.Information, 2500)
                s["tray_hint_shown"] = True
                self.save()
        else:
            self.quit()

    def quit(self, save=True):
        self._quitting = True
        if save:
            self._remember_geometry()
        self.controller.shutdown()
        self.clipwatch.flush()
        self.notes.flush()
        if save:
            self.flush_save()
        if self.config["settings"].get("keep_awake"):
            from core import awake
            awake.set_keep_awake(False)
        self.tray.hide()
        self.toaster.hide()
        QApplication.quit()


def _setup_logging():
    if not getattr(sys, "frozen", False):
        return
    try:
        path = cfg_store.data_path("volt.log")
        if os.path.exists(path) and os.path.getsize(path) > 512_000:
            os.replace(path, path + ".old")
        f = open(path, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f
        print(f"--- Volt {VERSION} started {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        pass


def _set_app_id():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Volt.Multitool")
        except Exception:
            pass


def main():
    if not instance.acquire():
        instance.signal_existing()
        return
    _setup_logging()
    _set_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)
    win = MainWindow()
    hidden = ("--startup" in sys.argv or "--minimized" in sys.argv
              or win.config["settings"].get("start_minimized"))
    if not hidden:
        win.show_initial()
    code = app.exec()
    instance.release()
    sys.exit(code)


if __name__ == "__main__":
    main()
