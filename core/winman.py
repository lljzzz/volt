import sys

from .nudge import HoldGlider

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SW_MAXIMIZE = 3
    SW_RESTORE = 9
    MONITOR_DEFAULTTONEAREST = 2

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    wintypes.UINT)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.IsZoomed.argtypes = (wintypes.HWND,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
    user32.MonitorFromPoint.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)

MIN_W, MIN_H = 140, 90
SNAPS = [
    ("left", "Left half"), ("right", "Right half"),
    ("top", "Top half"), ("bottom", "Bottom half"),
    ("top_left", "Top-left quarter"), ("top_right", "Top-right quarter"),
    ("bottom_left", "Bottom-left quarter"), ("bottom_right", "Bottom-right quarter"),
    ("center", "Center (keep size)"),
    ("maximize", "Maximize"), ("restore", "Restore"),
]
GRID_NAMES = ["Top-left", "Top", "Top-right", "Left", "Center", "Right",
              "Bottom-left", "Bottom", "Bottom-right"]


def available() -> bool:
    return IS_WINDOWS


def active_handle() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        return user32.GetForegroundWindow() or 0
    except Exception:
        return 0


def activate(hwnd: int) -> bool:
    if not IS_WINDOWS or not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(user32.SetForegroundWindow(hwnd))


def _rect(hwnd):
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r


def _monitor_info(hmon):
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not hmon or not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        return None
    return mi


def _work_area(hwnd):
    mi = _monitor_info(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST))
    return mi.rcWork if mi else None


def screen_points() -> dict[str, tuple[int, int]] | None:
    if not IS_WINDOWS:
        return None
    try:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        mi = _monitor_info(user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST))
        if not mi:
            return None
        r = mi.rcMonitor
        left, top, right, bottom = r.left + 1, r.top + 1, r.right - 2, r.bottom - 2
        cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
        xs, ys = (left, cx, right), (top, cy, bottom)
        return {name: (xs[i % 3], ys[i // 3]) for i, name in enumerate(GRID_NAMES)}
    except Exception:
        return None


def move_by(dx: int, dy: int, hwnd: int = 0):
    if not IS_WINDOWS:
        return
    hwnd = hwnd or active_handle()
    if not hwnd:
        return
    r = _rect(hwnd)
    if r:
        user32.SetWindowPos(hwnd, 0, r.left + dx, r.top + dy, 0, 0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


def resize_by(dw: int, dh: int, hwnd: int = 0):
    if not IS_WINDOWS:
        return
    hwnd = hwnd or active_handle()
    if not hwnd:
        return
    r = _rect(hwnd)
    if r:
        w = max(MIN_W, r.right - r.left + dw)
        h = max(MIN_H, r.bottom - r.top + dh)
        user32.SetWindowPos(hwnd, 0, 0, 0, w, h,
                            SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)


def snap(where: str, hwnd: int = 0):
    if not IS_WINDOWS:
        return
    hwnd = hwnd or active_handle()
    if not hwnd:
        return
    if where == "maximize":
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return
    if where == "restore":
        user32.ShowWindow(hwnd, SW_RESTORE)
        return
    if user32.IsZoomed(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    wa = _work_area(hwnd)
    if not wa:
        return
    L, T = wa.left, wa.top
    W, H = wa.right - wa.left, wa.bottom - wa.top
    half_w, half_h = W // 2, H // 2
    rects = {
        "left": (L, T, half_w, H),
        "right": (L + half_w, T, W - half_w, H),
        "top": (L, T, W, half_h),
        "bottom": (L, T + half_h, W, H - half_h),
        "top_left": (L, T, half_w, half_h),
        "top_right": (L + half_w, T, W - half_w, half_h),
        "bottom_left": (L, T + half_h, half_w, H - half_h),
        "bottom_right": (L + half_w, T + half_h, W - half_w, H - half_h),
    }
    if where == "center":
        r = _rect(hwnd)
        if not r:
            return
        w, h = r.right - r.left, r.bottom - r.top
        x, y = L + (W - w) // 2, T + (H - h) // 2
        user32.SetWindowPos(hwnd, 0, x, y, 0, 0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        return
    if where in rects:
        x, y, w, h = rects[where]
        user32.SetWindowPos(hwnd, 0, x, y, w, h,
                            SWP_NOZORDER | SWP_NOACTIVATE)


class WindowNudger(HoldGlider):
    def __init__(self, step_fn, mode_fn):
        super().__init__(0.03)
        self._step_fn = step_fn
        self._mode_fn = mode_fn

    def _apply(self, items):
        ux = sum(d[0] for d, _ in items)
        uy = sum(d[1] for d, _ in items)
        if not (ux or uy):
            return
        try:
            step = max(1, int(self._step_fn()))
        except Exception:
            step = 1
        try:
            if self._mode_fn() == "resize":
                resize_by(ux * step, uy * step)
            else:
                move_by(ux * step, uy * step)
        except Exception:
            pass
