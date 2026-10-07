import queue
import sys
import threading

from pynput import keyboard

from . import winput

IS_WINDOWS = sys.platform.startswith("win")
MODIFIERS = frozenset({"ctrl", "shift", "alt", "cmd"})

_MOD_MAP = {
    keyboard.Key.ctrl: "ctrl", keyboard.Key.ctrl_l: "ctrl", keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.shift: "shift", keyboard.Key.shift_l: "shift", keyboard.Key.shift_r: "shift",
    keyboard.Key.alt: "alt", keyboard.Key.alt_l: "alt", keyboard.Key.alt_gr: "alt", keyboard.Key.alt_r: "alt",
    keyboard.Key.cmd: "cmd", keyboard.Key.cmd_l: "cmd", keyboard.Key.cmd_r: "cmd",
}

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _user32.MapVirtualKeyExW.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.HKL)
    _user32.MapVirtualKeyExW.restype = wintypes.UINT
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.c_void_p)
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
    _user32.GetKeyboardLayout.restype = wintypes.HKL

    _MOD_VK = {0x10: "shift", 0xA0: "shift", 0xA1: "shift",
               0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
               0x12: "alt", 0xA4: "alt", 0xA5: "alt",
               0x5B: "cmd", 0x5C: "cmd"}
    _NUMPAD_OPS = {0x6A: "num_multiply", 0x6B: "num_add", 0x6D: "num_subtract",
                   0x6E: "num_decimal", 0x6F: "num_divide"}
    _VK_NAMES: dict[int, str] = {}
    for _k in keyboard.Key:
        _vk = getattr(_k.value, "vk", None)
        if _vk is not None and _vk not in _MOD_VK:
            _VK_NAMES.setdefault(_vk, _k.name)

    _LLKHF_INJECTED = 0x10 | 0x02
    _WM_KEYDOWN, _WM_SYSKEYDOWN = 0x100, 0x104
    _MASK_VK = 0xE8

    def _vk_char(vk: int):
        try:
            tid = _user32.GetWindowThreadProcessId(_user32.GetForegroundWindow(),
                                                   None)
            c = _user32.MapVirtualKeyExW(vk, 2, _user32.GetKeyboardLayout(tid))
        except Exception:
            return None
        c &= 0xFFFF
        return chr(c).lower() if c >= 32 else None

    def token_from_vk(vk: int) -> str:
        if vk in _MOD_VK:
            return _MOD_VK[vk]
        if 65 <= vk <= 90:
            return chr(vk).lower()
        if 48 <= vk <= 57:
            return chr(vk)
        if 96 <= vk <= 105:
            return f"num{vk - 96}"
        if vk in _NUMPAD_OPS:
            return _NUMPAD_OPS[vk]
        name = _VK_NAMES.get(vk)
        if name:
            return name
        return _vk_char(vk) or f"vk{vk}"


def _clean_token(t: str) -> str:
    if isinstance(t, str) and len(t) == 1 and 1 <= ord(t) <= 26:
        return chr(ord(t) + 96)
    return t


def _token(key) -> str | None:
    if key in _MOD_MAP:
        return _MOD_MAP[key]
    if isinstance(key, keyboard.KeyCode):
        vk = getattr(key, "vk", None)
        if IS_WINDOWS and vk:
            return token_from_vk(vk)
        if vk is not None:
            if 65 <= vk <= 90:
                return chr(vk).lower()
            if 48 <= vk <= 57:
                return chr(vk)
            if 96 <= vk <= 105:
                return f"num{vk - 96}"
        ch = key.char
        if ch:
            if len(ch) == 1 and 1 <= ord(ch) <= 26:
                return chr(ord(ch) + 96)
            return ch.lower()
        if vk is not None:
            return f"vk{vk}"
        return None
    if isinstance(key, keyboard.Key):
        return key.name.lower()
    return None


_NAMES = {"cmd": "Win", "esc": "Esc", "page_up": "PgUp", "page_down": "PgDn",
          "print_screen": "PrtSc", "caps_lock": "Caps Lock", "backspace": "Backspace",
          "delete": "Del", "insert": "Ins", "num_lock": "Num Lock",
          "scroll_lock": "Scroll Lock", "num_multiply": "Num *", "num_add": "Num +",
          "num_subtract": "Num -", "num_decimal": "Num .", "num_divide": "Num /",
          "space": "Space", "enter": "Enter", "tab": "Tab"}


def key_name(tok: str) -> str:
    tok = _clean_token(tok)
    if tok in _NAMES:
        return _NAMES[tok]
    if tok.startswith("num") and tok[3:].isdigit():
        return f"Num {tok[3:]}"
    if len(tok) == 1:
        return tok.upper()
    return tok.replace("_", " ").title()


def combo_to_text(combo: list[str]) -> str:
    combo = [_clean_token(t) for t in combo]
    order = {"ctrl": 0, "shift": 1, "alt": 2, "cmd": 3}
    parts = sorted(combo, key=lambda t: order.get(t, 9))
    return " + ".join(key_name(p) for p in parts)


def normalize(combo) -> frozenset:
    return frozenset(_clean_token(str(t).lower()) for t in combo)


class HotkeyManager:
    def __init__(self):
        self._pressed: set[str] = set()
        self._lock = threading.RLock()
        self._listener: keyboard.Listener | None = None

        self._hotkeys: dict[str, dict] = {}
        self._capture: dict | None = None
        self._paused = False
        self.suppress = True
        self._swallowed: set[str] = set()
        self._vk_of: dict[str, int] = {}

        self._jobs: queue.SimpleQueue = queue.SimpleQueue()
        self._worker: threading.Thread | None = None

    def is_pressed(self, tok: str) -> bool:
        with self._lock:
            return tok in self._pressed

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def start(self):
        if self._listener:
            return
        self._worker = threading.Thread(target=self._work, daemon=True,
                                        name="volt-hotkeys")
        self._worker.start()
        kwargs = {"on_press": self._on_press, "on_release": self._on_release}
        if IS_WINDOWS:
            kwargs["win32_event_filter"] = self._win_filter
        self._listener = keyboard.Listener(**kwargs)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._jobs.put(None)

    def register(self, hid: str, combo: list[str], mode: str,
                 on_activate, on_deactivate=None, loose=False):
        with self._lock:
            old = self._hotkeys.get(hid)
            if not combo:
                self._drop(hid)
                return
            c = normalize(combo)
            keep = bool(old and old["combo"] == c and old["mode"] == mode)
            if old and not keep:
                self._drop(hid)
            self._hotkeys[hid] = {
                "combo": c,
                "mods": c & MODIFIERS,
                "mode": mode,
                "loose": loose,
                "active": bool(keep and old["active"]),
                "on_activate": on_activate,
                "on_deactivate": on_deactivate,
            }

    def unregister(self, hid: str):
        with self._lock:
            self._drop(hid)

    def _drop(self, hid):
        hk = self._hotkeys.pop(hid, None)
        if hk and hk["active"] and hk["mode"] == "hold":
            self._dispatch(hk.get("on_deactivate"))

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._hotkeys)

    def combo_of(self, hid: str):
        with self._lock:
            hk = self._hotkeys.get(hid)
            return set(hk["combo"]) if hk else None

    def find_conflicts(self, combo, exclude=None) -> list[str]:
        c = normalize(combo)
        with self._lock:
            return [hid for hid, hk in self._hotkeys.items()
                    if hid != exclude and hk["combo"] == c]

    def begin_capture(self, callback, on_cancel=None):
        with self._lock:
            prev = self._capture
            self._capture = {"cb": callback, "cancel": on_cancel, "keys": set()}
        if prev and prev["cancel"]:
            self._dispatch(prev["cancel"])

    def cancel_capture(self, callback=None):
        with self._lock:
            cap = self._capture
            if cap is None or (callback is not None and cap["cb"] is not callback):
                return
            self._capture = None
        if cap["cancel"]:
            self._dispatch(cap["cancel"])

    def _capture_event(self, cap, tok, is_press) -> bool:
        keys = cap["keys"]
        if is_press:
            keys.add(tok)
            if tok not in MODIFIERS:
                self._swallowed.add(tok)
                return True
            return False
        if not keys:
            return False
        if not (keys - MODIFIERS):
            keys.discard(tok)
            return False
        self._capture = None
        if keys == {"esc"}:
            if cap["cancel"]:
                self._dispatch(cap["cancel"])
        else:
            result = [] if keys in ({"backspace"}, {"delete"}) else sorted(keys)
            cb = cap["cb"]
            self._dispatch(lambda: cb(result))
        return False

    def _handle(self, tok: str, is_press: bool, vk: int = 0) -> bool:
        with self._lock:
            repeat = was_swallowed = False
            if is_press:
                if vk:
                    self._prune(tok)
                    self._vk_of[tok] = vk
                repeat = tok in self._pressed
                self._pressed.add(tok)
            else:
                self._pressed.discard(tok)
                was_swallowed = tok in self._swallowed
                self._swallowed.discard(tok)
            pressed = frozenset(self._pressed)

            cap = self._capture
            if cap is not None:
                return self._capture_event(cap, tok, is_press) or was_swallowed
            if is_press and repeat:
                return tok in self._swallowed

            fired = self._evaluate(pressed)
            if not is_press:
                return was_swallowed
            if (fired and self.suppress and not self._paused
                    and tok not in MODIFIERS
                    and any(tok in hk["combo"] for hk in fired)):
                self._swallowed.add(tok)
                if pressed & {"alt", "cmd"}:
                    self._dispatch(winput.send_mask)
                return True
            return False

    def _matches(self, hk, pressed: frozenset) -> bool:
        if not hk["combo"] <= pressed:
            return False
        if hk["loose"]:
            return True
        return (pressed & MODIFIERS) == hk["mods"]

    def _evaluate(self, pressed: frozenset) -> list:
        fired = []
        if self._paused:
            return fired
        for hk in list(self._hotkeys.values()):
            matched = self._matches(hk, pressed)
            if matched and not hk["active"]:
                hk["active"] = True
                fired.append(hk)
                self._dispatch(hk["on_activate"])
            elif not matched and hk["active"]:
                hk["active"] = False
                if hk["mode"] == "hold":
                    self._dispatch(hk.get("on_deactivate"))
        return fired

    def _prune(self, current: str):
        for t in list(self._pressed):
            if t == current or t in self._swallowed:
                continue
            vk = self._vk_of.get(t)
            if vk and not (_user32.GetAsyncKeyState(vk) & 0x8000):
                self._pressed.discard(t)

    def _win_filter(self, msg, data):
        try:
            if data.flags & _LLKHF_INJECTED or data.vkCode == _MASK_VK:
                return False
            swallow = self._handle(token_from_vk(data.vkCode),
                                   msg in (_WM_KEYDOWN, _WM_SYSKEYDOWN),
                                   data.vkCode)
        except Exception as e:
            print(f"[hotkey] filter error: {e}")
            return False
        if swallow and self._listener is not None:
            self._listener.suppress_event()
        return False

    def _on_press(self, key, injected=False):
        if injected:
            return
        tok = _token(key)
        if tok is not None:
            self._handle(tok, True)

    def _on_release(self, key, injected=False):
        if injected:
            return
        tok = _token(key)
        if tok is not None:
            self._handle(tok, False)

    def _dispatch(self, fn):
        if fn:
            self._jobs.put(fn)

    def _work(self):
        while True:
            fn = self._jobs.get()
            if fn is None:
                return
            try:
                fn()
            except Exception as e:
                print(f"[hotkey] callback error: {e}")
