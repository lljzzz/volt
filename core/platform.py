import sys

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    _user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    _user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND,
                                                 ctypes.POINTER(wintypes.DWORD))
    _EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows.argtypes = (_EnumProc, wintypes.LPARAM)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD))
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def available() -> bool:
    return IS_WINDOWS


def foreground_handle() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        return _user32.GetForegroundWindow() or 0
    except Exception:
        return 0


def window_title(hwnd: int) -> str:
    if not IS_WINDOWS or not hwnd:
        return ""
    n = _user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def foreground_title() -> str:
    try:
        return window_title(foreground_handle())
    except Exception:
        return ""


_proc_cache: tuple[int, str] = (0, "")


def foreground_process() -> str:
    global _proc_cache
    if not IS_WINDOWS:
        return ""
    hwnd = foreground_handle()
    if not hwnd:
        return ""
    if _proc_cache[0] == hwnd:
        return _proc_cache[1]
    name = ""
    try:
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False,
                                  pid.value)
        if h:
            try:
                size = wintypes.DWORD(1024)
                buf = ctypes.create_unicode_buffer(size.value)
                if _kernel32.QueryFullProcessImageNameW(h, 0, buf,
                                                        ctypes.byref(size)):
                    name = buf.value.replace("/", "\\").rsplit("\\", 1)[-1]
            finally:
                _kernel32.CloseHandle(h)
    except Exception:
        name = ""
    _proc_cache = (hwnd, name.lower())
    return _proc_cache[1]


def list_windows() -> list[str]:
    if not IS_WINDOWS:
        return []
    titles: list[str] = []

    def _cb(hwnd, _):
        if _user32.IsWindowVisible(hwnd):
            t = window_title(hwnd)
            if t and t not in titles:
                titles.append(t)
        return True

    try:
        _user32.EnumWindows(_EnumProc(_cb), 0)
    except Exception:
        pass
    return sorted(titles, key=str.lower)
