import sys
import threading
import time
from datetime import datetime

from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyController, Key

IS_WINDOWS = sys.platform.startswith("win")

_RESET_KEYS = {
    Key.enter, Key.tab, Key.esc, Key.up, Key.down, Key.left, Key.right,
    Key.home, Key.end, Key.page_up, Key.page_down, Key.delete,
}
_MOD_NAMES = {
    Key.ctrl: "ctrl", Key.ctrl_l: "ctrl", Key.ctrl_r: "ctrl",
    Key.alt: "alt", Key.alt_l: "alt", Key.alt_r: "altgr", Key.alt_gr: "altgr",
    Key.cmd: "cmd", Key.cmd_l: "cmd", Key.cmd_r: "cmd",
}
_BUFFER_MAX = 64
_PASTE_THRESHOLD = 80

if IS_WINDOWS:
    import ctypes
    _user32 = ctypes.WinDLL("user32")
    _user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _user32.GetForegroundWindow.restype = ctypes.c_void_p


def render(text: str, clipboard_provider=None) -> str:
    now = datetime.now()
    out = (text
           .replace("{date}", now.strftime("%Y-%m-%d"))
           .replace("{time}", now.strftime("%H:%M"))
           .replace("{datetime}", now.strftime("%Y-%m-%d %H:%M"))
           .replace("{day}", now.strftime("%A")))
    if "{clipboard}" in out:
        clip = ""
        if clipboard_provider:
            try:
                clip = clipboard_provider() or ""
            except Exception:
                clip = ""
        out = out.replace("{clipboard}", clip)
    return out


def split_cursor(text: str) -> tuple[str, int]:
    before, sep, after = text.partition("{cursor}")
    if not sep:
        return text, 0
    after = after.replace("{cursor}", "")
    return before + after, len(after)


class SnippetEngine:
    def __init__(self):
        self._kbd = KeyController()
        self._listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None
        self._buffer = ""
        self._lock = threading.Lock()
        self._injecting = False
        self._ignore_until = 0.0
        self._paused = False
        self._enabled = True
        self._active: list[dict] = []
        self._mods: set[str] = set()
        self._last_hwnd = None
        self.insert_mode = "auto"
        self.clipboard_provider = None
        self.paster = None
        self.on_expand = None
        self.expand_count = 0

    def start(self):
        if self._listener:
            return
        self._listener = keyboard.Listener(on_press=self._on_press,
                                           on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()
        self._sync_mouse_listener()

    def stop(self):
        for lst in (self._listener, self._mouse_listener):
            if lst:
                lst.stop()
        self._listener = self._mouse_listener = None

    def _sync_mouse_listener(self):
        want = bool(self._listener and self._enabled and self._active)
        if want and self._mouse_listener is None:
            self._mouse_listener = mouse.Listener(on_click=self._on_click)
            self._mouse_listener.daemon = True
            self._mouse_listener.start()
        elif not want and self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False
        self._reset()

    def configure(self, cfg: dict):
        self._enabled = bool(cfg.get("enabled", True))
        self.insert_mode = cfg.get("insert_mode", "auto")
        items = [s for s in cfg.get("items", [])
                 if s.get("enabled", True) and s.get("trigger") and s.get("text")]
        self._active = sorted(items, key=lambda s: len(s["trigger"]), reverse=True)
        self._sync_mouse_listener()

    def _reset(self):
        with self._lock:
            self._buffer = ""

    def _on_click(self, x, y, button, pressed, injected=False):
        if pressed:
            self._reset()

    def _on_release(self, key, injected=False):
        name = _MOD_NAMES.get(key)
        if name and not injected:
            self._mods.discard(name)

    def _chord_held(self) -> bool:
        mods = self._mods
        if not mods:
            return False
        if IS_WINDOWS and not any(_user32.GetAsyncKeyState(vk) & 0x8000
                                  for vk in (0x11, 0x12, 0x5B, 0x5C)):
            mods.clear()
            return False
        if "altgr" in mods:
            return False
        return bool(mods & {"ctrl", "alt", "cmd"})

    def _on_press(self, key, injected=False):
        if injected:
            return
        name = _MOD_NAMES.get(key)
        if name:
            self._mods.add(name)
            return
        if (not self._enabled or self._paused or self._injecting
                or not self._active or time.monotonic() < self._ignore_until):
            return
        if IS_WINDOWS:
            hwnd = _user32.GetForegroundWindow()
            if hwnd != self._last_hwnd:
                self._last_hwnd = hwnd
                self._reset()
        if key in _RESET_KEYS or self._chord_held():
            self._reset()
            return
        if key == Key.backspace:
            with self._lock:
                self._buffer = self._buffer[:-1]
            return
        if key == Key.space:
            ch = " "
        else:
            ch = getattr(key, "char", None)
            if not ch or len(ch) != 1:
                return
            if ord(ch) < 32:
                self._reset()
                return
        with self._lock:
            self._buffer = (self._buffer + ch)[-_BUFFER_MAX:]
            buf = self._buffer
        for snip in self._active:
            if buf.endswith(snip["trigger"]):
                self._reset()
                threading.Thread(target=self._expand, args=(snip,),
                                 daemon=True).start()
                break

    def _tap(self, key, n=1):
        for _ in range(n):
            self._kbd.press(key)
            self._kbd.release(key)
            time.sleep(0.004)

    def _expand(self, snip: dict):
        self._injecting = True
        try:
            trigger = snip["trigger"]
            text, back = split_cursor(render(snip["text"], self.clipboard_provider))
            mode = self.insert_mode
            paste = mode == "paste" or (
                mode == "auto" and ("\n" in text or len(text) > _PASTE_THRESHOLD))
            self._tap(Key.backspace, len(trigger))
            if not (paste and text and self.paster and self.paster(text)):
                self._kbd.type(text)
            if back:
                self._tap(Key.left, back)
            self.expand_count += 1
            if self.on_expand:
                try:
                    self.on_expand(trigger)
                except Exception:
                    pass
        except Exception as e:
            print(f"[snippets] expansion failed: {e}")
        finally:
            self._ignore_until = time.monotonic() + 0.15
            self._injecting = False
