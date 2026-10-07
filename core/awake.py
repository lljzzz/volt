import sys

IS_WINDOWS = sys.platform.startswith("win")

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def set_keep_awake(on: bool) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        import ctypes
        flags = ES_CONTINUOUS
        if on:
            flags |= ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
        return True
    except Exception as e:
        print(f"[awake] {e}")
        return False
