import re

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (QFrame, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QVBoxLayout, QWidget)

from core import snippets as snip_mod
from core import transforms, winman
from core.picker import calc
from core.timers import fmt_remaining, parse_duration
from ui.nudge import builtin_points
from .styles import ACCENT, GREEN
from .widgets import rich_list, set_item

MAX_CLIP_ITEMS = 15
MAX_SHOWN = 60
RECENT_MAX = 8


def _score(query: str, label: str) -> int:
    q, s = query.lower().strip(), label.lower()
    if not q:
        return 0
    if q in s:
        i = s.index(q)
        bonus = 60 if i == 0 or s[i - 1] in " :·-(" else 0
        return 300 - i + bonus
    words = q.split()
    if len(words) > 1 and all(w in s for w in words):
        return 200
    pos, score = 0, 100
    for ch in q:
        found = s.find(ch, pos)
        if found < 0:
            return -1
        score -= (found - pos)
        pos = found + 1
    return score


def _preview(text: str, n: int = 70) -> str:
    t = " ".join(text.split())
    return t[:n] + "…" if len(t) > n else t


class _Item:
    __slots__ = ("label", "hint", "fn", "kind", "glyph", "color", "text")

    def __init__(self, label, hint, fn, kind, glyph, color=None, text=None):
        self.label, self.hint, self.fn = label, hint, fn
        self.kind, self.glyph, self.color = kind, glyph, color
        self.text = text


class Palette(QWidget):
    def __init__(self, window):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.win = window
        self._items: list[_Item] = []
        self._display: list[_Item] = []
        self._target_hwnd = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame(objectName="Palette")
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(6)

        self.input = QLineEdit(objectName="PaletteInput")
        self.input.setPlaceholderText("Search commands, macros, snippets, clipboard… "
                                      "or type math")
        self.input.textChanged.connect(self._refilter)
        self.input.installEventFilter(self)
        lay.addWidget(self.input)

        self.list = rich_list(QListWidget(objectName="PaletteList"), compact=True)
        self.list.itemClicked.connect(lambda _: self._execute())
        self.list.setFocusPolicy(Qt.NoFocus)
        lay.addWidget(self.list, 1)

        self.hint = QLabel("", objectName="Hint")
        self.hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.hint)

        self.setFixedWidth(620)
        self.setFixedHeight(470)

    def open(self, prefill: str = ""):
        hwnd = winman.active_handle()
        if hwnd and int(hwnd) not in (int(self.winId()), int(self.win.winId())):
            self._target_hwnd = hwnd
        elif not self.isVisible():
            self._target_hwnd = 0
        self._build()
        self.input.blockSignals(True)
        self.input.setText(prefill)
        self.input.blockSignals(False)
        self._refilter(prefill)
        screen = (QGuiApplication.screenAt(QCursor.pos())
                  or QGuiApplication.primaryScreen())
        g = screen.availableGeometry()
        self.move(g.x() + (g.width() - self.width()) // 2,
                  g.y() + int(g.height() * 0.18))
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def event(self, e):
        if e.type() == QEvent.WindowDeactivate:
            self.hide()
        return super().event(e)

    def eventFilter(self, obj, e):
        if obj is self.input and e.type() == QEvent.KeyPress:
            k = e.key()
            n = self.list.count()
            if k == Qt.Key_Escape:
                if self.input.text():
                    self.input.clear()
                else:
                    self.hide()
                return True
            if k in (Qt.Key_Down, Qt.Key_Up, Qt.Key_Tab, Qt.Key_Backtab) and n:
                step = -1 if k in (Qt.Key_Up, Qt.Key_Backtab) else 1
                self.list.setCurrentRow((self.list.currentRow() + step) % n)
                return True
            if k in (Qt.Key_PageDown, Qt.Key_PageUp) and n:
                step = 8 if k == Qt.Key_PageDown else -8
                self.list.setCurrentRow(max(0, min(n - 1, self.list.currentRow() + step)))
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                self._execute(copy_only=bool(e.modifiers() & Qt.ShiftModifier))
                return True
        return super().eventFilter(obj, e)

    def _build(self):
        w, ctrl = self.win, self.win.controller
        cfg = w.config
        items: list[_Item] = []
        add = items.append
        clip = ctrl.clipboard

        def copy_fn(text):
            return lambda: clip.copy(text) if clip else None

        ac_on = ctrl.clicker.running
        add(_Item(f"{'Stop' if ac_on else 'Start'} autoclicker", "toggle the clicker",
                  ctrl.toggle_clicker, "Action", "autoclicker", GREEN if ac_on else None))
        add(_Item("Stop everything", "clicker + all macros", ctrl.stop_everything,
                  "Action", "stop"))
        add(_Item("Capture screen region", "drag to select · copies + saves",
                  lambda: w.capture_tool.start("region"), "Capture", "capture"))
        add(_Item("Capture full screen", "the screen under the cursor",
                  lambda: w.capture_tool.start("full"), "Capture", "capture"))
        add(_Item("Capture region and pin", "keep it floating on top",
                  lambda: w.capture_tool.start("region", pin=True), "Capture", "capture"))
        pinned = cfg["settings"].get("always_on_top", False)
        add(_Item(f"Pin Volt on top: turn {'off' if pinned else 'on'}",
                  "keep Volt above other windows",
                  lambda: w.set_always_on_top(not pinned), "Setting", "pin"))
        awake_on = cfg["settings"].get("keep_awake", False)
        add(_Item(f"Keep awake: turn {'off' if awake_on else 'on'}",
                  "stop the PC from sleeping",
                  lambda: w.toggle_keep_awake(not awake_on), "Setting", "coffee"))
        add(_Item("Paste as plain text", "strip formatting and paste",
                  ctrl.paste_plain, "Clipboard", "paste"))
        add(_Item("New note", "opens Volt on a fresh note",
                  lambda: (w.restore(), w.navigate("Notes"), w.pages["Notes"].new_note()),
                  "Notes", "add"))
        add(_Item("Show Volt", "restore the window", w.restore, "Volt", "bolt"))
        add(_Item("Quit Volt", "", w.quit, "Volt", "power"))
        for page, icon_name in w.NAV:
            add(_Item(f"Open {page}", "go to page",
                      lambda p=page: (w.restore(), w.navigate(p)), "Page", icon_name))

        for m in cfg["macros"]:
            mid = m["id"]
            running = ctrl.is_macro_running(mid)
            add(_Item(f"{'Stop' if running else 'Run'} macro: {m['name']}",
                      f"{len(m.get('actions', []))} actions",
                      lambda mid=mid: ctrl.toggle_macro(mid), "Macro",
                      "stop" if running else "macros", GREEN if running else ACCENT))

        provider = clip.latest_text if clip else None
        for s in cfg["snippets"].get("items", []):
            if not s.get("text"):
                continue
            text, _back = snip_mod.split_cursor(snip_mod.render(s["text"], provider))
            add(_Item(f"Snippet: {s.get('trigger', '?')}", _preview(s["text"]),
                      copy_fn(text), "Snippet", "snippets", text=text))

        if clip:
            for e in clip.entries[:MAX_CLIP_ITEMS]:
                add(_Item(f"Clipboard: {_preview(e['text'], 60)}",
                          "pinned" if e.get("pinned") else "",
                          copy_fn(e["text"]), "Clipboard",
                          "pinned" if e.get("pinned") else "clipboard",
                          ACCENT if e.get("pinned") else None, text=e["text"]))
            latest = clip.latest_text()
            if latest and len(latest) <= 200_000:
                for _key, label, fn, _group in transforms.TRANSFORMS:
                    out, err = transforms.apply(fn, latest)
                    if err is None:
                        add(_Item(f"Clipboard as {label}", _preview(out, 50),
                                  copy_fn(out), "Transform", "text", text=out))

        if ctrl.notes:
            for n in ctrl.notes.sorted():
                title = ctrl.notes.title_of(n)
                add(_Item(f"Note: {title}", "open in Volt",
                          lambda nid=n["id"]: (w.restore(), w.navigate("Notes"),
                                               w.pages["Notes"].open_note(nid)),
                          "Note", "notes", ACCENT if n["pinned"] else None))
                add(_Item(f"Copy note: {title}", _preview(n["text"], 50),
                          copy_fn(n["text"]), "Note", "copy", text=n["text"]))

        hwnd = self._target_hwnd
        if winman.available() and hwnd:
            for key, label in winman.SNAPS:
                add(_Item(f"Snap window: {label}", "the window you were in",
                          lambda k=key, h=hwnd: winman.snap(k, h), "Window", "window"))

        tm = getattr(w, "timers", None)
        if tm:
            for mins in (5, 10, 15, 25, 45, 60):
                add(_Item(f"Start {mins} min timer", "notification when done",
                          lambda s=mins * 60: tm.start(s), "Timer", "timers"))
            for t in list(tm.items):
                add(_Item(f"Cancel timer: {t['label']}",
                          f"{fmt_remaining(tm.remaining(t))} left",
                          lambda tid=t["id"]: tm.cancel(tid), "Timer", "timers", ACCENT))

        for hx in cfg.get("picker", {}).get("history", [])[:8]:
            add(_Item(f"Color {hx}", "recent pick", copy_fn(hx), "Color",
                      "color", hx, text=hx))

        for a in cfg.get("nudge", {}).get("anchors", []):
            add(_Item(f"Mouse to: {a['name']}", f"({a['x']}, {a['y']})",
                      lambda a=a: ctrl.nudge.jump(a["x"], a["y"]), "Anchor", "target"))
        for name, (x, y) in builtin_points().items():
            add(_Item(f"Mouse to: {name}", "current screen",
                      lambda x=x, y=y: ctrl.nudge.jump(x, y), "Anchor", "target"))

        self._items = items

    def _dynamic(self, text: str) -> list[_Item]:
        out = []
        t = text.strip()
        result = calc(t)
        if result is not None:
            out.append(_Item(f"=  {result}", "Enter pastes · Shift+Enter copies",
                             lambda r=result: self._copy(r), "Calculator", "calc",
                             ACCENT, text=result))
        m = re.match(r"^(?:note|n)\s*:\s*(.+)$", t, re.I)
        if m:
            body = m.group(1).strip()
            out.append(_Item(f"Add note: {_preview(body, 60)}", "saved to Notes",
                             lambda b=body: self._add_note(b), "Notes", "add", ACCENT))
        m = re.match(r"^(?:timer|t)\s+(.+)$", t, re.I)
        dur_text = m.group(1) if m else t
        secs = parse_duration(dur_text) if (m or re.search(r"[hms:]", t)) else None
        if secs and len(t) <= 20:
            out.append(_Item(f"Start timer: {fmt_remaining(secs)}", "notification when done",
                             lambda s=secs: self.win.timers.start(s), "Timer",
                             "timers", ACCENT))
        return out

    def _recent_rank(self) -> dict[str, int]:
        recent = self.win.config["settings"].get("palette_recent", [])
        return {label: i for i, label in enumerate(recent)}

    def _refilter(self, text):
        self.list.clear()
        self._display = self._dynamic(text)
        q = text.strip()
        if q:
            scored = []
            for i, it in enumerate(self._items):
                sc = _score(q, f"{it.label} {it.hint} {it.kind}")
                if sc >= 0:
                    scored.append((sc, i))
            scored.sort(key=lambda t: (-t[0], t[1]))
            self._display += [self._items[i] for _sc, i in scored[:MAX_SHOWN]]
        else:
            rank = self._recent_rank()
            recent = sorted((it for it in self._items if it.label in rank),
                            key=lambda it: rank[it.label])
            rest = [it for it in self._items if it.label not in rank]
            self._display += (recent + rest)[:MAX_SHOWN]
        paste_on = self.win.config["settings"].get("palette_paste", True)
        for it in self._display:
            li = QListWidgetItem()
            set_item(li, it.label, it.hint, glyph=it.glyph, color=it.color,
                     right=it.kind)
            self.list.addItem(li)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.hint.setText(
            ("↑↓ navigate · Enter run / paste · Shift+Enter copy · Esc close"
             if paste_on and self._target_hwnd else
             "↑↓ navigate · Enter run · Esc close")
            if self._display else "No matches")

    def _copy(self, text: str):
        if self.win.controller.clipboard:
            self.win.controller.clipboard.copy(text)
            self.win.controller.toast.emit("Copied")

    def _add_note(self, body: str):
        notes = self.win.controller.notes
        if notes:
            notes.add(body)
            self.win.controller.toast.emit("Note saved")

    def _remember(self, item: _Item):
        if item.kind in ("Calculator",) or item.label.startswith(("Add note:", "Start timer:")):
            return
        s = self.win.config["settings"]
        recent = [r for r in s.get("palette_recent", []) if r != item.label]
        s["palette_recent"] = ([item.label] + recent)[:RECENT_MAX]
        self.win.save()

    def _execute(self, copy_only=False):
        row = self.list.currentRow()
        if not (0 <= row < len(self._display)):
            return
        item = self._display[row]
        self.hide()
        self._remember(item)
        ctrl = self.win.controller
        paste_on = self.win.config["settings"].get("palette_paste", True)
        try:
            if item.text is not None and not copy_only and paste_on and self._target_hwnd:
                ctrl.paste_into(self._target_hwnd, item.text)
            elif item.text is not None:
                if ctrl.clipboard:
                    ctrl.clipboard.copy(item.text)
                ctrl.toast.emit("Copied")
            else:
                item.fn()
        except Exception as e:
            print(f"[palette] action failed: {e}")
