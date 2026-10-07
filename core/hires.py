import sys
import threading

_lock = threading.Lock()
_users = 0


def _set(on: bool):
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        winmm = ctypes.windll.winmm
        (winmm.timeBeginPeriod if on else winmm.timeEndPeriod)(1)
    except Exception:
        pass


def acquire():
    global _users
    with _lock:
        _users += 1
        if _users == 1:
            _set(True)


def release():
    global _users
    with _lock:
        if _users == 0:
            return
        _users -= 1
        if _users == 0:
            _set(False)
