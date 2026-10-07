import sys
import time

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    ULONG_PTR = wintypes.WPARAM

    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    INPUT_KEYBOARD = 1
    MAPVK_VK_TO_VSC = 0

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.c_void_p, ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.VkKeyScanExW.argtypes = (wintypes.WCHAR, wintypes.HKL)
    user32.VkKeyScanExW.restype = ctypes.c_short
    user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
    user32.GetKeyboardLayout.restype = wintypes.HKL
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.c_void_p)
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short

    _VK = {
        "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "cmd": 0x5B,
        "ctrl_l": 0xA2, "ctrl_r": 0xA3, "shift_l": 0xA0, "shift_r": 0xA1,
        "alt_l": 0xA4, "alt_r": 0xA5, "alt_gr": 0xA5, "cmd_l": 0x5B, "cmd_r": 0x5C,
        "enter": 0x0D, "space": 0x20, "tab": 0x09, "esc": 0x1B,
        "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
        "home": 0x24, "end": 0x23, "page_up": 0x21, "page_down": 0x22,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "caps_lock": 0x14, "num_lock": 0x90, "scroll_lock": 0x91,
        "print_screen": 0x2C, "pause": 0x13, "menu": 0x5D,
        "num_multiply": 0x6A, "num_add": 0x6B, "num_subtract": 0x6D,
        "num_decimal": 0x6E, "num_divide": 0x6F,
        "media_play_pause": 0xB3, "media_next": 0xB0, "media_previous": 0xB1,
        "media_stop": 0xB2, "media_volume_up": 0xAF,
        "media_volume_down": 0xAE, "media_volume_mute": 0xAD,
    }
    for _i in range(1, 25):
        _VK[f"f{_i}"] = 0x70 + (_i - 1)

    _EXTENDED = {"up", "down", "left", "right", "home", "end",
                 "page_up", "page_down", "insert", "delete", "num_divide",
                 "ctrl_r", "alt_r", "alt_gr", "cmd", "cmd_l", "cmd_r", "menu",
                 "num_lock", "print_screen"}

    def _layout():
        try:
            tid = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),
                                                  None)
            return user32.GetKeyboardLayout(tid)
        except Exception:
            return None

    def _vk_for(tok: str):
        if not tok:
            return None, False
        if tok in _VK:
            return _VK[tok], tok in _EXTENDED
        if tok.startswith("vk") and tok[2:].isdigit():
            return int(tok[2:]), False
        if tok.startswith("num") and tok[3:].isdigit():
            return 0x60 + int(tok[3:]), False
        if len(tok) == 1:
            ch = tok.upper()
            if "A" <= ch <= "Z" or "0" <= ch <= "9":
                return ord(ch), False
            res = user32.VkKeyScanExW(tok, _layout())
            if res != -1 and (res & 0xFF) not in (0, 0xFF):
                return res & 0xFF, False
        return None, False

    def _send_scan(vk: int, extended: bool, up: bool):
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        flags = KEYEVENTF_SCANCODE
        if extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        if up:
            flags |= KEYEVENTF_KEYUP
        if scan == 0:
            flags = (KEYEVENTF_KEYUP if up else 0) | (
                KEYEVENTF_EXTENDEDKEY if extended else 0)
            ki = KEYBDINPUT(vk, 0, flags, 0, 0)
        else:
            ki = KEYBDINPUT(0, scan, flags, 0, 0)
        inp = INPUT(INPUT_KEYBOARD, _U(ki))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _send_vk(vk: int, up: bool):
        ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
        inp = INPUT(INPUT_KEYBOARD, _U(ki))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def available() -> bool:
    return IS_WINDOWS


def can_send(tok: str) -> bool:
    return IS_WINDOWS and _vk_for(tok)[0] is not None


def key_down(tok: str) -> bool:
    if not IS_WINDOWS:
        return False
    vk, ext = _vk_for(tok)
    if vk is None:
        return False
    _send_scan(vk, ext, up=False)
    return True


def key_up(tok: str) -> bool:
    if not IS_WINDOWS:
        return False
    vk, ext = _vk_for(tok)
    if vk is None:
        return False
    _send_scan(vk, ext, up=True)
    return True


def tap(tok: str, hold_ms: int = 25) -> bool:
    if not key_down(tok):
        return False
    time.sleep(max(1, hold_ms) / 1000.0)
    key_up(tok)
    return True


_MODIFIER_VKS = (0x10, 0x11, 0x12, 0x5B, 0x5C)


def modifiers_down() -> bool:
    if not IS_WINDOWS:
        return False
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in _MODIFIER_VKS)


def wait_modifiers_released(timeout: float = 1.0):
    end = time.monotonic() + timeout
    while modifiers_down() and time.monotonic() < end:
        time.sleep(0.01)


def send_paste():
    if IS_WINDOWS:
        key_down("ctrl")
        tap("v", 20)
        key_up("ctrl")
        return
    try:
        from pynput.keyboard import Controller, Key
        k = Controller()
        mod = Key.cmd if sys.platform == "darwin" else Key.ctrl
        with k.pressed(mod):
            k.press("v")
            k.release("v")
    except Exception as e:
        print(f"[paste] {e}")


def send_mask():
    if IS_WINDOWS:
        _send_vk(0xE8, up=False)
        _send_vk(0xE8, up=True)
