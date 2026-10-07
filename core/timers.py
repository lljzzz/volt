import datetime as _dt
import time
import uuid

from PySide6.QtCore import QObject, QTimer, Signal


class TimerManager(QObject):
    updated = Signal()
    finished = Signal(str)

    def __init__(self, store: dict | None = None, on_persist=None):
        super().__init__()
        self.items: list[dict] = []
        self._store = store if store is not None else {}
        self._on_persist = on_persist
        self._qt = QTimer(self)
        self._qt.setInterval(500)
        self._qt.timeout.connect(self._tick)

    def start(self, seconds: int, label: str = "") -> dict:
        seconds = max(1, int(seconds))
        t = {"id": uuid.uuid4().hex[:8],
             "label": label or self._auto_label(seconds),
             "total": seconds,
             "end": time.monotonic() + seconds,
             "paused": False, "left": seconds}
        self.items.append(t)
        self._changed()
        return t

    def start_at(self, hour: int, minute: int, label: str = "") -> dict:
        now = _dt.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += _dt.timedelta(days=1)
        secs = int((target - now).total_seconds())
        return self.start(secs, label or f"Alarm {hour:02d}:{minute:02d}")

    def cancel(self, tid: str):
        self.items = [t for t in self.items if t["id"] != tid]
        self._changed()

    def toggle_pause(self, tid: str):
        t = self.get(tid)
        if not t:
            return
        if t["paused"]:
            t["end"] = time.monotonic() + t["left"]
            t["paused"] = False
        else:
            t["left"] = max(0.0, t["end"] - time.monotonic())
            t["paused"] = True
        self._changed()

    def add_time(self, tid: str, seconds: int):
        t = self.get(tid)
        if not t:
            return
        if t["paused"]:
            t["left"] += seconds
        else:
            t["end"] += seconds
        t["total"] += seconds
        self._changed()

    def get(self, tid: str) -> dict | None:
        return next((t for t in self.items if t["id"] == tid), None)

    def remaining(self, t: dict) -> int:
        if t["paused"]:
            return max(0, int(round(t["left"])))
        return max(0, int(round(t["end"] - time.monotonic())))

    def progress(self, t: dict) -> float:
        total = max(1, t["total"])
        return min(1.0, max(0.0, 1 - self.remaining(t) / total))

    def restore(self):
        now_wall, now_mono = time.time(), time.monotonic()
        missed = []
        for s in self._store.get("running", []):
            try:
                total = int(s["total"])
                if s.get("paused"):
                    left = float(s["left"])
                    end = now_mono + left
                else:
                    left = float(s["wall_end"]) - now_wall
                    end = now_mono + left
                if left <= 0:
                    missed.append(s.get("label", "Timer"))
                    continue
                self.items.append({"id": uuid.uuid4().hex[:8],
                                   "label": s.get("label", "Timer"),
                                   "total": total, "end": end,
                                   "paused": bool(s.get("paused")), "left": left})
            except (KeyError, TypeError, ValueError):
                continue
        self._changed()
        for label in missed:
            self.finished.emit(f"{label} (finished while Volt was closed)")

    def _persist(self):
        now_wall, now_mono = time.time(), time.monotonic()
        self._store["running"] = [
            {"label": t["label"], "total": t["total"],
             "paused": t["paused"],
             "left": round(self.remaining(t), 1),
             "wall_end": round(now_wall + (t["end"] - now_mono), 1)}
            for t in self.items]
        if self._on_persist:
            self._on_persist()

    def _changed(self):
        if any(not t["paused"] for t in self.items):
            if not self._qt.isActive():
                self._qt.start()
        else:
            self._qt.stop()
        self._persist()
        self.updated.emit()

    def _tick(self):
        now = time.monotonic()
        done = [t for t in self.items if not t["paused"] and t["end"] <= now]
        if done:
            self.items = [t for t in self.items if t not in done]
            self._changed()
            for t in done:
                self.finished.emit(t["label"])
            return
        self.updated.emit()

    @staticmethod
    def _auto_label(seconds: int) -> str:
        if seconds % 3600 == 0:
            return f"{seconds // 3600} h timer"
        if seconds % 60 == 0:
            return f"{seconds // 60} min timer"
        if seconds > 60:
            return f"{seconds // 60} min {seconds % 60} s timer"
        return f"{seconds} s timer"


def fmt_remaining(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_duration(text: str) -> int | None:
    import re
    t = text.strip().lower().replace(" ", "")
    if not t:
        return None
    if re.fullmatch(r"\d+", t):
        return int(t) * 60
    if re.fullmatch(r"\d+(:\d{1,2}){1,2}", t):
        parts = [int(p) for p in t.split(":")]
        secs = 0
        for p in parts:
            secs = secs * 60 + p
        return secs
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m(?:in)?)?(?:(\d+)s)?", t)
    if m and any(m.groups()):
        h, mi, s = (int(g) if g else 0 for g in m.groups())
        return h * 3600 + mi * 60 + s
    m = re.fullmatch(r"(\d+)h(\d+)", t)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    return None
