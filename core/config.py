import copy
import json
import os
import sys
import time

APP_NAME = "Volt"
CONFIG_VERSION = 2


def _base_dir() -> str:
    override = os.environ.get("VOLT_DATA_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(exe_dir, "portable")):
            d = os.path.join(exe_dir, "VoltData")
            os.makedirs(d, exist_ok=True)
            return d
        if sys.platform.startswith("win"):
            root = os.environ.get("APPDATA") or os.path.expanduser("~")
            d = os.path.join(root, APP_NAME)
        else:
            d = os.path.join(os.path.expanduser("~"), ".config", APP_NAME.lower())
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            d = os.path.dirname(sys.executable)
        return d
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_PATH = os.path.join(_base_dir(), "volt_config.json")

LOAD_WARNING = ""


def data_dir() -> str:
    return os.path.dirname(CONFIG_PATH)


def data_path(name: str) -> str:
    return os.path.join(data_dir(), name)


DEFAULTS = {
    "config_version": CONFIG_VERSION,
    "settings": {
        "launch_on_startup": False,
        "start_minimized": False,
        "minimize_to_tray_on_close": True,
        "always_on_top": False,
        "keep_awake": False,
        "suppress_hotkeys": True,
        "palette_hotkey": ["ctrl", "alt", "space"],
        "palette_paste": True,
        "palette_recent": [],
        "dark_mode": True,
        "panic_hotkey": ["ctrl", "shift", "m"],
        "macros_armed": True,
        "rec_moves": False,
        "rec_buttons": True,
        "rec_keys": True,
        "rec_delays": True,
        "window_geometry": [],
        "window_maximized": False,
        "last_page": "Dashboard",
    },
    "autoclicker": {
        "armed": True,
        "stop_on_focus_change": False,
        "window_blocklist": "",
        "cps": 25,
        "unit": "second",
        "mode": "rate",
        "delay_ms": 40,
        "hotkey": ["ctrl", "y"],
        "hotkey_mode": "toggle",
        "mouse_button": "left",
        "click_duration": 45,
        "double_click": False,
        "double_click_ms": 38,
        "speed_variation": True,
        "speed_variation_pct": 35,
        "mouse_shake": False,
        "mouse_shake_px": 2,
        "limit_enabled": False,
        "limit_type": "click",
        "limit_value": 1000,
        "window_lock_enabled": False,
        "window_lock_title": "",
        "sequence_enabled": False,
        "sequence_points": [],
        "sequence_point_delay_ms": 50,
    },
    "macros": [],
    "nudge": {
        "enabled": True,
        "modifiers": ["ctrl", "alt"],
        "step_px": 1,
        "fast_enabled": True,
        "fast_step_px": 10,
        "anchors": [],
        "window": {
            "enabled": True,
            "modifiers": ["cmd", "alt"],
            "step_px": 20,
            "resize_with_shift": True,
        },
    },
    "picker": {
        "enabled": True,
        "hotkey": ["ctrl", "alt", "c"],
        "format": "hex",
        "auto_copy": True,
        "notify": True,
        "history": [],
    },
    "capture": {
        "enabled": True,
        "hotkey": ["ctrl", "shift", "x"],
        "copy": True,
        "save": True,
        "folder": "",
        "notify": True,
    },
    "snippets": {
        "enabled": True,
        "insert_mode": "auto",
        "items": [
            {"id": "s_date", "trigger": ";date", "text": "{date}", "enabled": True},
            {"id": "s_time", "trigger": ";time", "text": "{time}", "enabled": True},
            {"id": "s_dt", "trigger": ";dt", "text": "{datetime}", "enabled": True},
            {"id": "s_day", "trigger": ";day", "text": "{day}", "enabled": True},
            {"id": "s_clip", "trigger": ";clip", "text": "{clipboard}", "enabled": True},
            {"id": "s_shrug", "trigger": ";shrug", "text": r"¯\_(ツ)_/¯", "enabled": True},
            {"id": "s_flip", "trigger": ";flip", "text": "(╯°□°)╯︵ ┻━┻", "enabled": True},
            {"id": "s_brb", "trigger": ";brb", "text": "be right back, give me 5 minutes",
             "enabled": True},
            {"id": "s_mail", "trigger": ";sig",
             "text": "Best regards,\n<your name here - edit me in the Snippets tab>",
             "enabled": True},
        ],
    },
    "clipboard": {
        "enabled": True,
        "max_items": 100,
        "remember_history": False,
        "ignore_sensitive": True,
        "paste_plain_hotkey": ["ctrl", "shift", "v"],
        "pinned": [],
    },
    "timers": {
        "running": [],
    },
}


def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        d = out.get(k)
        if isinstance(v, dict) and isinstance(d, dict):
            out[k] = _merge(d, v)
        elif d is None or v is None:
            out[k] = copy.deepcopy(v)
        elif isinstance(d, bool):
            out[k] = v if isinstance(v, bool) else d
        elif isinstance(d, (int, float)):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
            out[k] = v if ok else d
        elif type(d) is type(v):
            out[k] = copy.deepcopy(v)
    return out


def _migrate(cfg: dict) -> dict:
    ver = cfg.get("config_version", 1)
    if ver < 2:
        pass
    cfg["config_version"] = CONFIG_VERSION
    return cfg


def _migrate_legacy():
    if not getattr(sys, "frozen", False) or os.path.exists(CONFIG_PATH):
        return
    legacy = os.path.join(os.path.dirname(sys.executable), "volt_config.json")
    if os.path.exists(legacy):
        try:
            import shutil
            shutil.copy2(legacy, CONFIG_PATH)
        except Exception:
            pass


_last_written: dict[str, str] = {}


def write_json(path: str, data) -> bool:
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        print(f"[config] not serialisable: {e}")
        return False
    if _last_written.get(path) == text:
        return True
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        _last_written[path] = text
        return True
    except Exception as e:
        print(f"[config] save failed ({path}): {e}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def read_json(path: str, default=None):
    global LOAD_WARNING
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(path, "r", encoding="utf-8") as f:
            _last_written[path] = f.read()
        return data
    except Exception as e:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        root, ext = os.path.splitext(path)
        aside = f"{root}.corrupt-{stamp}{ext}"
        try:
            os.replace(path, aside)
            LOAD_WARNING = (f"{os.path.basename(path)} couldn't be read ({e}). "
                            f"It was kept as {os.path.basename(aside)}.")
        except OSError:
            LOAD_WARNING = f"{os.path.basename(path)} couldn't be read ({e})."
        print(f"[config] {LOAD_WARNING}")
        return default


def load() -> dict:
    _migrate_legacy()
    data = read_json(CONFIG_PATH, None)
    cfg = _merge(DEFAULTS, data) if isinstance(data, dict) else defaults()
    if isinstance(data, dict) and "config_version" not in data:
        cfg["config_version"] = 1
        if "palette_hotkey" not in data.get("settings", {}):
            cfg["settings"]["palette_hotkey"] = ["ctrl", "shift", "p"]
    return _migrate(cfg)


def save(data: dict) -> bool:
    return write_json(CONFIG_PATH, data)
