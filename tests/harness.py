import json
import os
import sys
import tempfile
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = tempfile.mkdtemp(prefix="volt-tests-")
DATA = os.path.join(OUT, "data")
SHOTS = os.path.join(OUT, "shots")
os.makedirs(DATA, exist_ok=True)
os.makedirs(SHOTS, exist_ok=True)
os.environ["VOLT_DATA_DIR"] = DATA
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
sys.path.insert(0, PROJECT)

FAILS = []
CHECKS = 0


def check(name, cond, detail=""):
    global CHECKS
    CHECKS += 1
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


class FakeMouse:
    def __init__(self, *a, **k):
        self.position = (100, 100)
        self.log = []

    def press(self, b):
        self.log.append(("press", b))

    def release(self, b):
        self.log.append(("release", b))

    def move(self, dx, dy):
        x, y = self.position
        self.position = (x + dx, y + dy)


class FakeKeys:
    def __init__(self, *a, **k):
        self.log = []

    def press(self, k):
        self.log.append(("press", k))

    def release(self, k):
        self.log.append(("release", k))

    def type(self, t):
        self.log.append(("type", t))


import core.clicker
import core.hotkeys
import core.macro
import core.nudge
import core.snippets
import core.winput
import core.winman
import core.instance

core.clicker.Controller = FakeMouse
core.nudge.Controller = FakeMouse
core.macro.MouseController = FakeMouse
core.macro.KeyController = FakeKeys
core.snippets.KeyController = FakeKeys
SENT = []
core.winput.key_down = lambda tok: SENT.append(("down", tok)) or True
core.winput.key_up = lambda tok: SENT.append(("up", tok)) or True
core.winput.send_paste = lambda: SENT.append(("paste",))
core.winput.wait_modifiers_released = lambda timeout=1.0: None
core.hotkeys.HotkeyManager.start = lambda self: None
core.hotkeys.HotkeyManager.stop = lambda self: None
core.snippets.SnippetEngine.start = lambda self: None
core.winman.force_foreground = lambda hwnd: False
core.winman.snap = lambda *a, **k: None
core.instance.mark_window = lambda hwnd: None

from core import snippets as sn
from core import timers as tm
from core import config as cfg_store
from core import picker as pk

text, back = sn.expand("Hi {cursor}there", None)
check("expand cursor", (text, back) == ("Hi there", 5), (text, back))
text, back = sn.expand("A{clipboard}B", lambda: "x{cursor}y")
check("clipboard {cursor} kept literal", (text, back) == ("Ax{cursor}yB", 0), (text, back))
text, back = sn.expand("<{cursor}>{clipboard}", lambda: "zz")
check("cursor before clipboard", (text, back) == ("<>zz", 3), (text, back))
check("blockers prefix", sn.blockers(";date", [";d", ";dt", "x"]) == [";d"])
check("blockers suffix ok", sn.blockers(";xdate", ["date"]) == [])
check("blockers self", sn.blockers(";d", [";d"]) == [])

cases = {"25": 1500, "1h30": 5400, "90s": 90, "1:30": 90, "1:00:00": 3600,
         "1.5h": 5400, "2,5m": 150, "2.5": 150, "45min": 2700, "10sec": 10,
         "0": None, "abc": None, "home": None, "1h": 3600, "1h15m": 4500}
for k, v in cases.items():
    got = tm.parse_duration(k)
    check(f"parse_duration {k!r}", got == v, f"got {got}")
labels = {5400: "1 h 30 min timer", 3600: "1 h timer", 90: "1 min 30 s timer",
          45: "45 s timer", 600: "10 min timer", 3661: "1 h 1 min 1 s timer"}
for k, v in labels.items():
    got = tm.TimerManager._auto_label(k)
    check(f"auto label {k}", got == v, got)

check("calc", pk.calc("2+3*4") == "14" and pk.calc("hello") is None)

old = {"config_version": 2,
       "settings": {"dark_mode": True, "palette_hotkey": ["ctrl", "shift", "p"]},
       "macros": [{"id": "a", "name": "ok", "hotkey": [], "actions": []},
                  {"name": 5, "actions": [{"type": "delay", "ms": 5}, "junk", {}]},
                  "notadict", {"id": "a", "name": "dup"}],
       "snippets": {"items": [{"trigger": ";x"}, 7]},
       "nudge": {"anchors": [{"name": "", "x": "12", "y": None}]},
       "picker": {"history": ["#aabbcc", "#zzzzzz", 5, "#ABCDEF"]},
       "autoclicker": {"sequence_points": [{"x": "3", "y": 4.0}, None]}}
with open(cfg_store.CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(old, f)
c = cfg_store.load()
check("migrated version", c["config_version"] == 3)
check("dark_mode dropped", "dark_mode" not in c["settings"])
check("upgrader skips welcome", c["settings"]["welcome_done"] is True)
check("theme default", c["settings"]["theme"] == "dark" and c["settings"]["accent"] == "orange")
check("palette kept", c["settings"]["palette_hotkey"] == ["ctrl", "shift", "p"])
ids = [m["id"] for m in c["macros"]]
check("macros sanitized", len(c["macros"]) == 3 and len(set(ids)) == 3, ids)
check("macro fields", all(isinstance(m["name"], str) and isinstance(m["hotkey"], list)
                          and isinstance(m["actions"], list) for m in c["macros"]))
check("macro actions filtered", c["macros"][1]["actions"] == [{"type": "delay", "ms": 5}])
check("snippets sanitized", len(c["snippets"]["items"]) == 1
      and c["snippets"]["items"][0]["text"] == "" and "id" in c["snippets"]["items"][0])
a = c["nudge"]["anchors"][0]
check("anchor sanitized", a["x"] == 12 and a["y"] == 0 and a["name"] == "Anchor"
      and a["hotkey"] == [])
check("history filtered", c["picker"]["history"] == ["#aabbcc", "#ABCDEF"])
check("points sanitized", c["autoclicker"]["sequence_points"] == [{"x": 3, "y": 4}])
os.remove(cfg_store.CONFIG_PATH)
c = cfg_store.load()
check("new install shows welcome", c["settings"]["welcome_done"] is False)

from core.macro import MacroRecorder
from pynput.keyboard import Key, KeyCode
rec = MacroRecorder()
rec._recording, rec._record_keys, rec._record_delays = True, True, False
rec._stop_token = "f8"
rec._kr(Key.space)
rec._kp(KeyCode.from_vk(65))
rec._kr(KeyCode.from_vk(65))
check("stray key-up skipped", [e["action"] for e in rec._events] == ["down", "up"],
      rec._events)

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
fams = set(QFontDatabase.families())
print("icon font:", "Segoe Fluent Icons" in fams, "Segoe MDL2 Assets" in fams)

from ui import styles
for theme in ("dark", "light"):
    for acc in styles.ACCENTS:
        styles.set_theme(theme, acc)
        q = styles.qss()
        bad = [ln for ln in q.splitlines() if "{c." in ln or "None" in ln]
        check(f"qss {theme}/{acc}", not bad and "url(" in q, bad[:2])
for name in ("spin_light_up", "spin_light_down", "spin_light_up_h", "spin_light_down_h",
             "spin_up", "spin_down", "check"):
    check(f"asset {name}", os.path.exists(os.path.join(PROJECT, "assets", name + ".png")))
check("mix", styles.mix("#000000", "#ffffff", 0.5) == "#808080")

import main as volt_main
os.makedirs(os.path.join(OUT, "captures"), exist_ok=True)
_orig_load = cfg_store.load

def _load_scratch():
    c = _orig_load()
    c["capture"]["folder"] = os.path.join(OUT, "captures")
    return c

cfg_store.load = _load_scratch
volt_main.MainWindow._apply_native_styles = lambda self: None
win = volt_main.MainWindow()
win.resize(1180, 820)
win.show()
app.processEvents()


def shot(name, widget=None):
    w = widget or win
    app.processEvents()
    pm = w.grab()
    path = os.path.join(SHOTS, name + ".png")
    pm.save(path)
    return path


def scroll_top(name):
    sa = win._wrappers[name]
    sa.verticalScrollBar().setValue(0)


check("welcome visible on new install", win.pages["Dashboard"].welcome.isVisible())
shot("dark_dashboard")
for name in win.pages:
    win.navigate(name)
    scroll_top(name)
    shot(f"dark_{name.lower()}")

ctrl = win.controller
snips = win.pages["Snippets"]
for trig in (";zz", ";zzt"):
    snips._add()
    snips.trigger_edit.setText(trig)
    snips._trigger_changed(trig)
snips._check_conflicts()
check("prefix conflict warns", "can never fire" in snips.warn.text(), snips.warn.text())
first = next(s for s in snips.snips() if s["trigger"] == ";zz")
snips.current_id = first["id"]
snips._load()
check("blocking conflict warns", "fires partway through ';zzt'" in snips.warn.text(),
      snips.warn.text())

notes = win.pages["Notes"]
win.navigate("Notes")
before = len(ctrl.notes.items)
notes.new_note()
notes.new_note()
check("blank notes cleaned", len(ctrl.notes.items) == before + 1,
      f"{before} -> {len(ctrl.notes.items)}")
notes.editor.setPlainText("Groceries\nmilk")
win.navigate("Dashboard")
check("non-blank note kept", any(n["text"].startswith("Groceries") for n in ctrl.notes.items))
win.navigate("Notes")
notes.new_note()
win.navigate("Dashboard")
check("blank note dropped on leave",
      all(n["text"].strip() for n in ctrl.notes.items), [n["text"] for n in ctrl.notes.items])

cb = QApplication.clipboard()
cb.setText("hello plain")
app.processEvents()
SENT.clear()
ctrl.paste_plain()
time.sleep(0.3)
app.processEvents()
check("paste plain sends paste", ("paste",) in SENT, SENT)
check("paste plain uses live text", cb.text() == "hello plain")
cb.clear()
app.processEvents()
SENT.clear()
toasts = []
ctrl.toast.connect(toasts.append)
ctrl.paste_plain()
time.sleep(0.2)
app.processEvents()
check("paste plain with empty clipboard does nothing", not SENT and toasts, (SENT, toasts))

exec(open(os.path.join(os.path.dirname(__file__), "image_tests.py"), encoding="utf-8").read())
win._deactivated_at = time.monotonic()
win.toggle_visible()
check("tray click hides recently active window", not win.isVisible())
win._deactivated_at = 0.0
win.toggle_visible()
check("tray click restores hidden window", win.isVisible())

win.toaster.show_message("short")
w1 = win.toaster.width()
win.toaster.show_message("x" * 400)
w2 = win.toaster.width()
win.toaster.show_message("short again")
w3 = win.toaster.width()
check("toast wraps long text", w2 <= 560 and win.toaster.wordWrap() is False and w3 < 200,
      (w1, w2, w3))

tmr = ctrl.timers
tmr.start(5400)
check("timer label", tmr.items[-1]["label"] == "1 h 30 min timer", tmr.items[-1]["label"])
win.navigate("Timers")
shot("dark_timers_running")

ac = win.pages["Autoclicker"]
ac.win_combo.setEditText("Notepad")
check("window lock editable", ctrl.config["autoclicker"]["window_lock_title"] == "Notepad")
ac.win_combo._provider = lambda: ["Alpha", "Beta"]
ac.win_combo.showPopup()
check("window lock keeps saved title", ac.win_combo.currentText() == "Notepad")
ac.win_combo.hidePopup()

settings = win.pages["Settings"]
win.pages["Dashboard"]._dismiss_welcome()
check("welcome dismissed", ctrl.config["settings"]["welcome_done"] is True)

t0 = time.perf_counter()
settings._set_look("theme", "light")
dt = time.perf_counter() - t0
check("theme switch applied", styles.T.name == "light", styles.T.name)
print(f"theme switch took {dt * 1000:.0f} ms")
for name in win.pages:
    win.navigate(name)
    scroll_top(name)
    shot(f"light_{name.lower()}")
win.navigate("Settings")
settings._set_look("accent", "blue")
check("accent switch", styles.T.accent == styles.ACCENTS["blue"])
shot("light_settings_blue")
win.navigate("Dashboard")
shot("light_dashboard_blue")
settings._set_look("theme", "dark")
win.navigate("Macros")
shot("dark_macros_blue")
settings._set_look("accent", "orange")

win.palette.open("")
app.processEvents()
shot("dark_palette", win.palette)
win.palette.input.setText("1h")
app.processEvents()
labels = [it.label for it in win.palette._display[:3]]
check("palette timer suggestion", any(l.startswith("Start timer") for l in labels), labels)
win.palette.hide()
settings._set_look("theme", "light")
win.palette.open("")
shot("light_palette", win.palette)
win.palette.hide()

export_path = os.path.join(OUT, "backup.json")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (export_path, ""))
settings._export()
data = json.load(open(export_path, encoding="utf-8"))
check("backup has notes", isinstance(data.get("notes"), list) and data["notes"])
ctrl.notes.items.clear()
restarted = []
win.restart = lambda: restarted.append(True)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (export_path, ""))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
settings._import()
check("import restores notes", restarted and any(n["text"].startswith("Groceries")
                                                for n in ctrl.notes.items))

win.quit()
print("FAILS:", FAILS)
print(f"{CHECKS - len(FAILS)}/{CHECKS} checks passed. Artifacts: {OUT}")
sys.exit(1 if FAILS else 0)
