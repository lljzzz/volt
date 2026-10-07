import os
import time

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal

from . import config as cfg_store

HISTORY_FILE = "clipboard_history.json"
MAX_ENTRY_CHARS = 1_000_000
MAX_PERSIST_CHARS = 20_000

_PRIVATE_MARKERS = ("ExcludeClipboardContentFromMonitorProcessing",
                    "Clipboard Viewer Ignore")
_HISTORY_MARKER = "CanIncludeInClipboardHistory"


class ClipboardWatcher(QObject):
    changed = Signal()

    def __init__(self, config: dict, on_change):
        super().__init__()
        self.cfg = config.setdefault("clipboard", {})
        self.cfg.setdefault("enabled", True)
        self.cfg.setdefault("max_items", 100)
        self.cfg.setdefault("pinned", [])
        self._on_change = on_change
        self._clipboard = None
        self._latest = ""
        self._mute_until = 0.0
        self.capture_count = 0
        self.skipped_private = 0

        self.entries: list[dict] = [
            {"text": t, "ts": 0.0, "pinned": True}
            for t in self.cfg["pinned"] if isinstance(t, str) and t
        ]
        if self.cfg.get("remember_history"):
            self._load_history()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1500)
        self._save_timer.timeout.connect(self.flush)

    def attach(self, qclipboard):
        self._clipboard = qclipboard
        qclipboard.dataChanged.connect(self._on_data_changed)
        try:
            self._latest = qclipboard.text() or ""
        except Exception:
            pass

    def latest_text(self) -> str:
        return self._latest

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", True))

    def set_enabled(self, value: bool):
        self.cfg["enabled"] = bool(value)
        self._on_change()

    def mute(self, seconds: float):
        self._mute_until = time.monotonic() + seconds

    def _is_private(self) -> bool:
        if not self.cfg.get("ignore_sensitive", True) or self._clipboard is None:
            return False
        try:
            md = self._clipboard.mimeData()
            if md is None:
                return False
            for f in md.formats():
                if any(m in f for m in _PRIVATE_MARKERS):
                    return True
                if _HISTORY_MARKER in f and bytes(md.data(f))[:4] == b"\0\0\0\0":
                    return True
        except Exception:
            return False
        return False

    def _on_data_changed(self):
        try:
            text = self._clipboard.text() if self._clipboard else ""
        except Exception:
            return
        if not text:
            return
        private = self._is_private()
        if not private:
            self._latest = text
        if (not self.enabled or time.monotonic() < self._mute_until
                or len(text) > MAX_ENTRY_CHARS):
            return
        if private:
            self.skipped_private += 1
            return
        for i, e in enumerate(self.entries):
            if e["text"] == text:
                e["ts"] = time.time()
                self.entries.insert(0, self.entries.pop(i))
                self._history_changed()
                return
        self.entries.insert(0, {"text": text, "ts": time.time(), "pinned": False})
        self.capture_count += 1
        self._trim()
        self._history_changed()

    def _trim(self):
        cap = max(10, int(self.cfg.get("max_items", 100)))
        if len(self.entries) <= cap:
            return
        keep, dropped = [], 0
        overflow = len(self.entries) - cap
        for e in reversed(self.entries):
            if dropped < overflow and not e["pinned"]:
                dropped += 1
                continue
            keep.append(e)
        self.entries = list(reversed(keep))

    def copy(self, text: str):
        if self._clipboard is not None:
            self._clipboard.setText(text)

    def snapshot(self):
        if self._clipboard is None:
            return None
        try:
            md = self._clipboard.mimeData()
            if md is None:
                return None
            snap = QMimeData()
            for f in md.formats():
                snap.setData(f, md.data(f))
            return snap
        except Exception:
            return None

    def set_text_silent(self, text: str):
        self.mute(2.0)
        if self._clipboard is not None:
            self._clipboard.setText(text)

    def restore(self, snap):
        if self._clipboard is None:
            return
        self.mute(0.5)
        if snap is not None:
            self._clipboard.setMimeData(snap)
        else:
            self._clipboard.clear()

    def set_pinned(self, entry: dict, value: bool):
        entry["pinned"] = bool(value)
        self._persist_pins()
        self._history_changed()

    def delete(self, entry: dict):
        if entry in self.entries:
            self.entries.remove(entry)
            if entry.get("pinned"):
                self._persist_pins()
            self._history_changed()

    def clear_unpinned(self):
        self.entries = [e for e in self.entries if e["pinned"]]
        self._history_changed()

    def set_max_items(self, n: int):
        self.cfg["max_items"] = int(n)
        self._trim()
        self._on_change()
        self._history_changed()

    def set_remember(self, value: bool):
        self.cfg["remember_history"] = bool(value)
        self._on_change()
        self.flush()

    def _persist_pins(self):
        self.cfg["pinned"] = [e["text"] for e in self.entries if e["pinned"]]
        self._on_change()

    def _history_changed(self):
        self.changed.emit()
        if self.cfg.get("remember_history"):
            self._save_timer.start()

    def _load_history(self):
        data = cfg_store.read_json(cfg_store.data_path(HISTORY_FILE), [])
        if not isinstance(data, list):
            return
        known = {e["text"] for e in self.entries}
        for item in data:
            if (isinstance(item, dict) and isinstance(item.get("text"), str)
                    and item["text"] and item["text"] not in known):
                self.entries.append({"text": item["text"],
                                     "ts": float(item.get("ts", 0) or 0),
                                     "pinned": False})
                known.add(item["text"])
        self._trim()

    def flush(self):
        self._save_timer.stop()
        path = cfg_store.data_path(HISTORY_FILE)
        if self.cfg.get("remember_history"):
            items = [{"text": e["text"], "ts": e["ts"]} for e in self.entries
                     if not e["pinned"] and len(e["text"]) <= MAX_PERSIST_CHARS]
        elif os.path.exists(path):
            items = []
        else:
            return
        cfg_store.write_json(path, items)
