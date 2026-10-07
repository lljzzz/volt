import sys

IS_WINDOWS = sys.platform.startswith("win")
_MUTEX = "Local\\VoltMultitool.SingleInstance"
_PROP = "VoltMultitool.Main"
_MSG = "VoltMultitool.Activate"
_handle = None

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _k32.CreateMutexW.restype = wintypes.HANDLE
    _k32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _u32.RegisterWindowMessageW.argtypes = (wintypes.LPCWSTR,)
    _u32.RegisterWindowMessageW.restype = wintypes.UINT
    _u32.SetPropW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.HANDLE)
    _u32.GetPropW.argtypes = (wintypes.HWND, wintypes.LPCWSTR)
    _u32.GetPropW.restype = wintypes.HANDLE
    _u32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                  wintypes.LPARAM)
    _EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _u32.EnumWindows.argtypes = (_EnumProc, wintypes.LPARAM)
    _u32.AllowSetForegroundWindow.argtypes = (wintypes.DWORD,)


def acquire() -> bool:
    global _handle
    if not IS_WINDOWS:
        return True
    h = _k32.CreateMutexW(None, False, _MUTEX)
    if ctypes.get_last_error() == 183:
        if h:
            _k32.CloseHandle(h)
        return False
    _handle = h
    return True


def release():
    global _handle
    if IS_WINDOWS and _handle:
        _k32.CloseHandle(_handle)
        _handle = None


def activate_message() -> int:
    return _u32.RegisterWindowMessageW(_MSG) if IS_WINDOWS else 0


def mark_window(hwnd: int):
    if IS_WINDOWS and hwnd:
        _u32.SetPropW(hwnd, _PROP, 1)


def signal_existing() -> bool:
    if not IS_WINDOWS:
        return False
    found = []

    def cb(hwnd, _):
        if _u32.GetPropW(hwnd, _PROP):
            found.append(hwnd)
            return False
        return True

    _u32.EnumWindows(_EnumProc(cb), 0)
    if not found:
        return False
    _u32.AllowSetForegroundWindow(0xFFFFFFFF)
    return bool(_u32.PostMessageW(found[0], activate_message(), 0, 0))
