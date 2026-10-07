import threading
import time

from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyController
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController

from . import hires, winput
from .hotkeys import _token, key_name

_BTN = {"left": Button.left, "right": Button.right, "middle": Button.middle}
_BTN_NAME = {Button.left: "left", Button.right: "right", Button.middle: "middle"}


def token_to_key(tok: str):
    if not tok:
        return None
    if hasattr(Key, tok):
        return getattr(Key, tok)
    if tok.startswith("vk") and tok[2:].isdigit():
        return KeyCode.from_vk(int(tok[2:]))
    if tok.startswith("num") and tok[3:].isdigit():
        return KeyCode.from_vk(0x60 + int(tok[3:]))
    if len(tok) == 1:
        return KeyCode.from_char(tok)
    return None


def describe(action: dict) -> tuple[str, str]:
    t = action.get("type")
    if t == "delay":
        return "Wait", f"{action.get('ms', 0)} ms"
    if t == "move":
        return "Move", f"({action.get('x')}, {action.get('y')})"
    if t == "mouse":
        act = action.get("action", "click")
        btn = action.get("button", "left")
        pos = ""
        if action.get("x") is not None:
            pos = f" @ ({action['x']}, {action['y']})"
        return f"Mouse {act}", f"{btn}{pos}"
    if t == "key":
        return f"Key {action.get('action', 'press')}", key_name(str(action.get("key", "")))
    return t or "?", ""


def duration_ms(actions: list) -> int:
    return int(sum(a.get("ms", 0) for a in actions if a.get("type") == "delay"))


def _sleep(seconds: float, stop: threading.Event):
    end = time.perf_counter() + seconds
    while not stop.is_set():
        remaining = end - time.perf_counter()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.02))


class MacroPlayer:
    def __init__(self):
        self._mouse = MouseController()
        self._kbd = KeyController()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._held_keys: set[str] = set()
        self._held_buttons: set = set()
        self.running = False
        self.on_state = None

    def play(self, actions, repeat=1, loop=False, speed=1.0, key_hold=25):
        if self.running or not actions:
            return
        self._key_hold = key_hold
        self._stop = threading.Event()
        self.running = True
        self._thread = threading.Thread(
            target=self._run, args=(list(actions), repeat, loop, speed),
            daemon=True, name="volt-macro")
        self._thread.start()
        if self.on_state:
            self.on_state(True)

    def stop(self):
        self._stop.set()

    def _run(self, actions, repeat, loop, speed):
        hires.acquire()
        try:
            count = 0
            while not self._stop.is_set():
                for a in actions:
                    if self._stop.is_set():
                        break
                    self._do(a, speed)
                count += 1
                if not loop and count >= max(1, repeat):
                    break
        except Exception as e:
            print(f"[macro] playback error: {e}")
        finally:
            self._release_held()
            hires.release()
            self.running = False
            self._stop.set()
            if self.on_state:
                self.on_state(False)

    def _key_down(self, tok):
        if not winput.key_down(tok):
            k = token_to_key(tok)
            if k is None:
                return
            self._kbd.press(k)
        self._held_keys.add(tok)

    def _key_up(self, tok):
        if not winput.key_up(tok):
            k = token_to_key(tok)
            if k is None:
                return
            self._kbd.release(k)
        self._held_keys.discard(tok)

    def _btn_down(self, btn):
        self._mouse.press(btn)
        self._held_buttons.add(btn)

    def _btn_up(self, btn):
        self._mouse.release(btn)
        self._held_buttons.discard(btn)

    def _release_held(self):
        for tok in list(self._held_keys):
            try:
                self._key_up(tok)
            except Exception:
                pass
        for btn in list(self._held_buttons):
            try:
                self._btn_up(btn)
            except Exception:
                pass

    def _do(self, a, speed):
        t = a.get("type")
        if t == "delay":
            _sleep(a.get("ms", 0) / 1000.0 / max(speed, 0.01), self._stop)
        elif t == "move":
            self._mouse.position = (a["x"], a["y"])
        elif t == "mouse":
            if a.get("x") is not None:
                self._mouse.position = (a["x"], a["y"])
            btn = _BTN.get(a.get("button", "left"), Button.left)
            act = a.get("action", "click")
            if act == "down":
                self._btn_down(btn)
            elif act == "up":
                self._btn_up(btn)
            else:
                self._btn_down(btn)
                self._btn_up(btn)
        elif t == "key":
            tok = a.get("key", "")
            act = a.get("action", "press")
            if act == "down":
                self._key_down(tok)
            elif act == "up":
                self._key_up(tok)
            else:
                hold = a.get("hold_ms", getattr(self, "_key_hold", 25))
                self._key_down(tok)
                _sleep(max(1, hold) / 1000.0, self._stop)
                self._key_up(tok)


class MacroRecorder:
    def __init__(self):
        self.on_complete = None
        self._events: list = []
        self._last = 0.0
        self._k = None
        self._m = None
        self._recording = False
        self._stop_token = "f8"
        self._record_moves = True
        self._last_move = (0, 0)
        self._last_move_t = 0.0
        self._down: set[str] = set()

    @property
    def recording(self) -> bool:
        return self._recording

    def start(self, record_moves=True, record_buttons=True, record_keys=True,
              record_delays=True, stop_token="f8"):
        if self._recording:
            return
        self._events = []
        self._down = set()
        self._last = time.perf_counter()
        self._record_moves = record_moves
        self._record_buttons = record_buttons
        self._record_keys = record_keys
        self._record_delays = record_delays
        self._stop_token = stop_token
        self._recording = True
        self._k = keyboard.Listener(on_press=self._kp, on_release=self._kr)
        self._k.daemon = True
        self._k.start()
        if record_moves or record_buttons:
            self._m = mouse.Listener(on_click=self._mc, on_move=self._mm)
            self._m.daemon = True
            self._m.start()
        else:
            self._m = None

    def stop(self, trim_click=False):
        if not self._recording:
            return
        self._recording = False
        for lst in (self._k, self._m):
            if lst:
                lst.stop()
        if trim_click:
            self._trim_trailing_click()
        if self.on_complete:
            self.on_complete(list(self._events))

    def _trim_trailing_click(self):
        ev = self._events
        i = len(ev)
        while i and ev[i - 1]["type"] in ("mouse", "move", "delay"):
            i -= 1
            if ev[i]["type"] == "mouse" and ev[i].get("action") == "down":
                del ev[i:]
                while ev and ev[-1]["type"] in ("move", "delay"):
                    ev.pop()
                return

    def _gap(self):
        now = time.perf_counter()
        dt = (now - self._last) * 1000.0
        self._last = now
        if self._record_delays and dt >= 1:
            self._events.append({"type": "delay", "ms": int(dt)})

    def _kp(self, key, injected=False):
        if injected:
            return
        tok = _token(key)
        if tok is None:
            return
        if tok == self._stop_token:
            threading.Thread(target=self.stop, daemon=True).start()
            return
        if not self._record_keys or tok in self._down:
            return
        self._down.add(tok)
        self._gap()
        self._events.append({"type": "key", "action": "down", "key": tok})

    def _kr(self, key, injected=False):
        if injected:
            return
        tok = _token(key)
        if tok is None or tok == self._stop_token or not self._record_keys:
            return
        self._down.discard(tok)
        self._gap()
        self._events.append({"type": "key", "action": "up", "key": tok})

    def _mc(self, x, y, button, pressed, injected=False):
        if injected or not self._record_buttons:
            return
        self._gap()
        self._events.append({
            "type": "mouse", "action": "down" if pressed else "up",
            "button": _BTN_NAME.get(button, "left"), "x": int(x), "y": int(y)})

    def _mm(self, x, y, injected=False):
        if injected or not self._record_moves:
            return
        now = time.perf_counter()
        dx = abs(x - self._last_move[0])
        dy = abs(y - self._last_move[1])
        if (now - self._last_move_t) < 0.04 or (dx + dy) < 12:
            return
        self._last_move = (x, y)
        self._last_move_t = now
        self._gap()
        self._events.append({"type": "move", "x": int(x), "y": int(y)})
