import time
import uuid

from PySide6.QtCore import QObject, QTimer, Signal

from . import config as cfg_store

NOTES_FILE = "notes.json"


class NotesStore(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        data = cfg_store.read_json(cfg_store.data_path(NOTES_FILE), [])
        self.items: list[dict] = [self._clean(n) for n in
                                  (data if isinstance(data, list) else [])
                                  if isinstance(n, dict)]
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self.flush)

    @staticmethod
    def _clean(n: dict) -> dict:
        try:
            updated = float(n.get("updated", 0) or 0)
        except (TypeError, ValueError):
            updated = 0.0
        return {"id": str(n.get("id") or uuid.uuid4().hex[:8]),
                "text": str(n.get("text", "")),
                "pinned": bool(n.get("pinned", False)),
                "updated": updated}

    def merge(self, items) -> int:
        ids = {n["id"] for n in self.items}
        texts = {n["text"] for n in self.items}
        added = 0
        for raw in items if isinstance(items, list) else []:
            if not isinstance(raw, dict):
                continue
            n = self._clean(raw)
            if not n["text"].strip() or n["text"] in texts:
                continue
            if n["id"] in ids:
                n["id"] = uuid.uuid4().hex[:8]
            self.items.append(n)
            ids.add(n["id"])
            texts.add(n["text"])
            added += 1
        if added:
            self._dirty()
        return added

    @staticmethod
    def title_of(note: dict) -> str:
        for line in note["text"].splitlines():
            if line.strip():
                return line.strip()[:80]
        return "Untitled note"

    def sorted(self) -> list[dict]:
        return sorted(self.items, key=lambda n: (not n["pinned"], -n["updated"]))

    def get(self, nid: str) -> dict | None:
        return next((n for n in self.items if n["id"] == nid), None)

    def add(self, text: str = "") -> dict:
        n = {"id": uuid.uuid4().hex[:8], "text": text, "pinned": False,
             "updated": time.time()}
        self.items.append(n)
        self._dirty()
        return n

    def update(self, nid: str, text: str):
        n = self.get(nid)
        if n and n["text"] != text:
            n["text"] = text
            n["updated"] = time.time()
            self._dirty()

    def set_pinned(self, nid: str, value: bool):
        n = self.get(nid)
        if n:
            n["pinned"] = bool(value)
            self._dirty()

    def delete(self, nid: str):
        self.items = [n for n in self.items if n["id"] != nid]
        self._dirty()

    def _dirty(self):
        self._timer.start()
        self.changed.emit()

    def flush(self):
        self._timer.stop()
        cfg_store.write_json(cfg_store.data_path(NOTES_FILE), self.items)
