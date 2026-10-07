import threading
import time
import uuid

from PySide6.QtCore import QObject, Signal

from . import winman, winput
from .clicker import ClickerEngine
from .hotkeys import HotkeyManager, combo_to_text
from .macro import MacroPlayer, MacroRecorder
from .nudge import NudgeEngine
from .snippets import SnippetEngine


class Controller(QObject):
    clicker_state = Signal(bool)
    clicker_count = Signal(int)
    limit_reached = Signal()
    failsafe = Signal(str)
    panic = Signal()
    macro_state = Signal(str, bool)
    recording_done = Signal(list)
    snippet_fired = Signal(str)
    palette_requested = Signal()
    pick_requested = Signal()
    capture_requested = Signal()
    seq_point = Signal(int, int)
    seq_record_state = Signal(bool)
    paste_plain_requested = Signal()
    toast = Signal(str)
    navigate = Signal(str)

    _swap_request = Signal(str, object)
    _restore_request = Signal()

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        config.setdefault("macros", [])
        config.setdefault("snippets", {"enabled": True, "items": []})
        self.clicker = ClickerEngine()
        self.hotkeys = HotkeyManager()
        self.recorder = MacroRecorder()
        self.snippets = SnippetEngine()
        self.nudge = NudgeEngine()
        self.winnudge = winman.WindowNudger(self._window_step,
                                            self._window_mode)
        self.timers = None
        self.clipboard = None
        self.notes = None
        self._players: dict[str, MacroPlayer] = {}
        self._saved_clip = None

        self.clicker.on_state_change = lambda r: self.clicker_state.emit(r)
        self.clicker.on_tick = lambda c: self.clicker_count.emit(c)
        self.clicker.on_limit_reached = lambda: self.limit_reached.emit()
        self.clicker.on_failsafe = lambda why: self.failsafe.emit(why)
        self.recorder.on_complete = self._on_recording_complete
        self.snippets.on_expand = lambda t: self.snippet_fired.emit(t)
        self.snippets.paster = self.paste_text
        self._swap_request.connect(self._do_swap)
        self._restore_request.connect(self._do_restore)

        self.hotkeys.start()
        self.refresh_hotkeys()
        self.refresh_snippets()
        self.snippets.start()

    def attach_clipboard(self, watcher):
        self.clipboard = watcher
        self.snippets.clipboard_provider = watcher.latest_text

    def refresh_hotkeys(self):
        s = self.config["settings"]
        self.hotkeys.suppress = bool(s.get("suppress_hotkeys", True))
        ac = self.config["autoclicker"]
        mode = ac.get("hotkey_mode", "toggle")
        combo = ac.get("hotkey", []) if ac.get("armed", True) else []
        if mode == "toggle":
            self.hotkeys.register(
                "clicker", combo, "toggle",
                on_activate=self._toggle_clicker)
        else:
            self.hotkeys.register(
                "clicker", combo, "hold",
                on_activate=self._start_clicker,
                on_deactivate=self.clicker.stop)

        self.hotkeys.register(
            "panic", s.get("panic_hotkey", []), "toggle",
            on_activate=self._panic, loose=True)

        self.hotkeys.register(
            "palette", s.get("palette_hotkey", []),
            "toggle", on_activate=lambda: self.palette_requested.emit())
        n = self.config.get("nudge", {})
        mods = [m for m in n.get("modifiers", []) if m]
        dirs = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
        for name, (dx, dy) in dirs.items():
            combo = (mods + [name]) if (n.get("enabled") and mods) else []
            self.hotkeys.register(
                f"nudge_{name}", combo, "hold",
                on_activate=lambda dx=dx, dy=dy:
                    self.nudge.start_hold(dx, dy, self._nudge_step),
                on_deactivate=lambda dx=dx, dy=dy:
                    self.nudge.stop_hold(dx, dy),
                loose=True)

        wn = n.get("window", {})
        wmods = [m for m in wn.get("modifiers", []) if m]
        w_on = winman.available() and wn.get("enabled") and wmods
        for name, (dx, dy) in dirs.items():
            combo = (wmods + [name]) if w_on else []
            self.hotkeys.register(
                f"window_{name}", combo, "hold",
                on_activate=lambda dx=dx, dy=dy:
                    self.winnudge.start_hold(dx, dy),
                on_deactivate=lambda dx=dx, dy=dy:
                    self.winnudge.stop_hold(dx, dy),
                loose=True)

        pk = self.config.get("picker", {})
        self.hotkeys.register(
            "picker",
            pk.get("hotkey", []) if pk.get("enabled", True) else [],
            "toggle", on_activate=lambda: self.pick_requested.emit())

        cap = self.config.get("capture", {})
        self.hotkeys.register(
            "capture",
            cap.get("hotkey", []) if cap.get("enabled", True) else [],
            "toggle", on_activate=lambda: self.capture_requested.emit())

        current = {f"anchor_{a['id']}" for a in n.get("anchors", [])}
        for hid in [h for h in self.hotkeys.ids()
                    if h.startswith("anchor_") and h not in current]:
            self.hotkeys.unregister(hid)
        for a in n.get("anchors", []):
            self.hotkeys.register(
                f"anchor_{a['id']}", a.get("hotkey", []), "toggle",
                on_activate=lambda a=a: self.nudge.jump(a["x"], a["y"]))

        self.hotkeys.register(
            "paste_plain",
            self.config.get("clipboard", {}).get("paste_plain_hotkey", []),
            "toggle", on_activate=lambda: self.paste_plain_requested.emit())

        macros_armed = s.get("macros_armed", True)
        live = {f"macro_{m['id']}" for m in self.config["macros"]}
        for hid in [h for h in self.hotkeys.ids()
                    if h.startswith("macro_") and h not in live]:
            self.hotkeys.unregister(hid)
        for m in self.config["macros"]:
            mid = m["id"]
            if not macros_armed or not m.get("enabled", True) or not m.get("hotkey"):
                self.hotkeys.unregister(f"macro_{mid}")
                continue
            if m.get("hotkey_mode", "toggle") == "hold":
                self.hotkeys.register(
                    f"macro_{mid}", m["hotkey"], "hold",
                    on_activate=lambda mid=mid: self.play_macro(mid, force_loop=True),
                    on_deactivate=lambda mid=mid: self.stop_macro(mid))
            else:
                self.hotkeys.register(
                    f"macro_{mid}", m["hotkey"], "toggle",
                    on_activate=lambda mid=mid: self.toggle_macro(mid))

    def hotkey_label(self, hid: str) -> str:
        fixed = {"clicker": "Autoclicker", "panic": "Panic stop",
                 "palette": "Quick palette", "paste_plain": "Paste as plain text",
                 "picker": "Color picker", "capture": "Screen capture",
                 "seqrec_add": "Sequence recorder", "seqrec_done": "Sequence recorder"}
        if hid in fixed:
            return fixed[hid]
        if hid.startswith("nudge_"):
            return "Mouse nudge"
        if hid.startswith("window_"):
            return "Window nudge"
        if hid.startswith("macro_"):
            m = self.get_macro(hid[6:])
            return f"Macro '{m['name']}'" if m else "a macro"
        if hid.startswith("anchor_"):
            a = next((a for a in self.config["nudge"].get("anchors", [])
                      if a["id"] == hid[7:]), None)
            return f"Anchor '{a['name']}'" if a else "an anchor"
        return hid

    def conflict_message(self, combo, own_hid=None) -> str:
        if not combo:
            return ""
        others = self.hotkeys.find_conflicts(combo, exclude=own_hid)
        if not others:
            return ""
        names = sorted({self.hotkey_label(h) for h in others})
        return f"{combo_to_text(combo)} is also used by {', '.join(names)}"

    def refresh_snippets(self):
        self.snippets.configure(self.config["snippets"])

    def _toggle_clicker(self):
        self.clicker.toggle(self.config["autoclicker"])

    def _start_clicker(self):
        self.clicker.start(self.config["autoclicker"])

    def _nudge_step(self) -> int:
        n = self.config.get("nudge", {})
        if n.get("fast_enabled", True) and self.hotkeys.is_pressed("shift"):
            return int(n.get("fast_step_px", 10))
        return int(n.get("step_px", 1))

    def _window_step(self) -> int:
        wn = self.config.get("nudge", {}).get("window", {})
        return int(wn.get("step_px", 20))

    def _window_mode(self) -> str:
        wn = self.config.get("nudge", {}).get("window", {})
        if wn.get("resize_with_shift", True) and self.hotkeys.is_pressed("shift"):
            return "resize"
        return "move"

    def _panic(self):
        self.stop_everything()
        self.panic.emit()

    def stop_everything(self):
        self.clicker.stop()
        self.stop_all_macros()
        self.nudge.stop_all()
        self.winnudge.stop_all()

    def start_clicker(self):
        self.clicker.start(self.config["autoclicker"])

    def stop_clicker(self):
        self.clicker.stop()

    def toggle_clicker(self):
        self.clicker.toggle(self.config["autoclicker"])

    def paste_text(self, text: str) -> bool:
        if self.clipboard is None:
            return False
        ready = threading.Event()
        self._swap_request.emit(text, ready)
        if not ready.wait(1.0):
            return False
        winput.send_paste()
        time.sleep(0.4)
        self._restore_request.emit()
        return True

    def _do_swap(self, text, ready):
        self._saved_clip = self.clipboard.snapshot()
        self.clipboard.set_text_silent(text)
        ready.set()

    def _do_restore(self):
        self.clipboard.restore(self._saved_clip)
        self._saved_clip = None

    def paste_into(self, hwnd: int, text: str):
        if self.clipboard is None:
            return
        self.clipboard.copy(text)

        def send():
            time.sleep(0.05)
            winman.activate(hwnd)
            time.sleep(0.12)
            winput.wait_modifiers_released(1.0)
            winput.send_paste()

        threading.Thread(target=send, daemon=True).start()

    def paste_plain(self):
        if self.clipboard is None:
            return
        text = self.clipboard.latest_text()
        if not text:
            return
        self.clipboard.copy(text)

        def send():
            time.sleep(0.05)
            winput.wait_modifiers_released(1.5)
            winput.send_paste()

        threading.Thread(target=send, daemon=True).start()

    def new_macro(self) -> dict:
        m = {
            "id": uuid.uuid4().hex[:8],
            "name": f"Macro {len(self.config['macros']) + 1}",
            "hotkey": [], "hotkey_mode": "toggle",
            "enabled": True, "repeat": 1, "loop": False, "speed": 1.0,
            "key_hold_ms": 25,
            "actions": [],
        }
        self.config["macros"].append(m)
        return m

    def get_macro(self, mid: str) -> dict | None:
        return next((m for m in self.config["macros"] if m["id"] == mid), None)

    def delete_macro(self, mid: str):
        self.stop_macro(mid)
        self.hotkeys.unregister(f"macro_{mid}")
        self.config["macros"] = [m for m in self.config["macros"] if m["id"] != mid]
        self._players.pop(mid, None)

    def play_macro(self, mid: str, force_loop=False):
        m = self.get_macro(mid)
        if not m or not m.get("actions"):
            return
        player = self._players.get(mid)
        if player and player.running:
            return
        player = MacroPlayer()
        player.on_state = lambda r, mid=mid: self.macro_state.emit(mid, r)
        self._players[mid] = player
        player.play(m["actions"], repeat=m.get("repeat", 1),
                    loop=force_loop or m.get("loop", False),
                    speed=m.get("speed", 1.0),
                    key_hold=m.get("key_hold_ms", 25))

    def stop_macro(self, mid: str):
        p = self._players.get(mid)
        if p:
            p.stop()

    def toggle_macro(self, mid: str):
        p = self._players.get(mid)
        if p and p.running:
            p.stop()
        else:
            self.play_macro(mid)

    def stop_all_macros(self):
        for p in self._players.values():
            p.stop()

    def is_macro_running(self, mid: str) -> bool:
        p = self._players.get(mid)
        return bool(p and p.running)

    def running_macros(self) -> int:
        return sum(1 for p in self._players.values() if p.running)

    def duplicate_macro(self, mid: str) -> dict | None:
        import json
        src = self.get_macro(mid)
        if not src:
            return None
        m = json.loads(json.dumps(src))
        m["id"] = uuid.uuid4().hex[:8]
        m["name"] = f"{src['name']} copy"
        m["hotkey"] = []
        self.config["macros"].append(m)
        return m

    def start_seq_record(self):
        self.hotkeys.register("seqrec_add", ["f7"], "toggle",
                              on_activate=self._seq_add_point)
        self.hotkeys.register("seqrec_done", ["f8"], "toggle",
                              on_activate=self.stop_seq_record)
        self.seq_record_state.emit(True)

    def _seq_add_point(self):
        x, y = self.nudge.position()
        self.seq_point.emit(int(x), int(y))

    def stop_seq_record(self):
        self.hotkeys.unregister("seqrec_add")
        self.hotkeys.unregister("seqrec_done")
        self.seq_record_state.emit(False)

    def start_recording(self, record_moves=True, record_buttons=True,
                        record_keys=True, record_delays=True, stop_token="f8"):
        self.hotkeys.pause()
        self.snippets.pause()
        self.recorder.start(record_moves=record_moves,
                            record_buttons=record_buttons,
                            record_keys=record_keys,
                            record_delays=record_delays,
                            stop_token=stop_token)

    def stop_recording(self, trim_click=False):
        self.recorder.stop(trim_click=trim_click)

    def _on_recording_complete(self, actions):
        self.hotkeys.resume()
        self.snippets.resume()
        self.recording_done.emit(actions)

    def shutdown(self):
        self.clicker.stop()
        self.stop_all_macros()
        try:
            self.recorder.stop()
        except Exception:
            pass
        self.nudge.stop_all()
        self.winnudge.stop_all()
        self.snippets.stop()
        self.hotkeys.stop()
