import hashlib
import os
import re
import time

from PySide6.QtCore import (QBuffer, QIODevice, QMimeData, QObject, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QImage, QImageWriter

from . import config as cfg_store

HISTORY_FILE = "clipboard_history.json"
IMAGE_DIR = "clipboard_images"
MAX_ENTRY_CHARS = 1_000_000
MAX_PERSIST_CHARS = 20_000
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGES = 20
MAX_IMAGE_BYTES = 48 * 1024 * 1024
MAX_PERSIST_IMAGE_BYTES = 12 * 1024 * 1024
THUMB_W, THUMB_H = 112, 72

_PRIVATE_MARKERS = ("ExcludeClipboardContentFromMonitorProcessing",
                    "Clipboard Viewer Ignore")
_HISTORY_MARKER = "CanIncludeInClipboardHistory"
_KEY = re.compile(r"[0-9a-f]{40}")


def is_image(entry: dict) -> bool:
    return entry.get("kind") == "image"


def image_key(img: QImage) -> str:
    img = img.convertToFormat(QImage.Format_ARGB32)
    h = hashlib.sha1(f"{img.width()}x{img.height()}".encode())
    h.update(bytes(img.constBits()))
    return h.hexdigest()


def encode_png(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    writer = QImageWriter(buf, b"png")
    writer.setQuality(80)
    return bytes(buf.data()) if writer.write(img) else b""


def make_thumb(img: QImage) -> QImage:
    return img.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{max(1, round(n / 1024))} KB"


class ClipboardWatcher(QObject):
    changed = Signal()

    def __init__(self, config: dict, on_change):
        super().__init__()
        self.cfg = config.setdefault("clipboard", {})
        self.cfg.setdefault("enabled", True)
        self.cfg.setdefault("images", True)
        self.cfg.setdefault("max_items", 100)
        self.cfg.setdefault("pinned", [])
        self._on_change = on_change
        self._clipboard = None
        self._latest = ""
        self._mute_until = 0.0
        self._decoded = (None, None)
        self.capture_count = 0
        self.skipped_private = 0

        self.entries: list[dict] = []
        for p in self.cfg["pinned"]:
            if isinstance(p, str) and p:
                self.entries.append({"text": p, "ts": 0.0, "pinned": True})
            elif isinstance(p, dict):
                e = self._load_image(p, pinned=True)
                if e:
                    self.entries.append(e)
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

    def current_text(self) -> str:
        if self._clipboard is None:
            return ""
        try:
            return self._clipboard.text() or ""
        except Exception:
            return ""

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", True))

    def set_enabled(self, value: bool):
        self.cfg["enabled"] = bool(value)
        self._on_change()

    def set_images(self, value: bool):
        self.cfg["images"] = bool(value)
        self._on_change()

    def mute(self, seconds: float):
        self._mute_until = time.monotonic() + seconds

    def _is_private(self) -> bool:
        if not self.cfg.get("ignore_sensitive", True):
            return False
        return self.flagged_private()

    def flagged_private(self) -> bool:
        if self._clipboard is None:
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
            self._capture_image()
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
            if not is_image(e) and e["text"] == text:
                e["ts"] = time.time()
                self.entries.insert(0, self.entries.pop(i))
                self._history_changed()
                return
        self.entries.insert(0, {"text": text, "ts": time.time(), "pinned": False})
        self.capture_count += 1
        self._trim()
        self._history_changed()

    def _capture_image(self):
        if (self._clipboard is None or not self.enabled
                or not self.cfg.get("images", True)
                or time.monotonic() < self._mute_until):
            return
        try:
            md = self._clipboard.mimeData()
            if md is None or not md.hasImage():
                return
            if self._is_private():
                self.skipped_private += 1
                return
            img = self._clipboard.image()
        except Exception:
            return
        if img.isNull() or img.width() * img.height() > MAX_IMAGE_PIXELS:
            return
        key = image_key(img)
        for i, e in enumerate(self.entries):
            if is_image(e) and e["key"] == key:
                e["ts"] = time.time()
                self.entries.insert(0, self.entries.pop(i))
                self._history_changed()
                return
        png = encode_png(img)
        if not png or len(png) > MAX_IMAGE_BYTES:
            return
        self.entries.insert(0, {"kind": "image", "text": "", "key": key, "png": png,
                                "w": img.width(), "h": img.height(), "size": len(png),
                                "thumb": make_thumb(img), "ts": time.time(),
                                "pinned": False})
        self._decoded = (key, img)
        self.capture_count += 1
        self._trim()
        self._history_changed()

    def _trim(self):
        cap = max(10, int(self.cfg.get("max_items", 100)))
        if len(self.entries) > cap:
            keep, dropped = [], 0
            overflow = len(self.entries) - cap
            for e in reversed(self.entries):
                if dropped < overflow and not e["pinned"]:
                    dropped += 1
                    continue
                keep.append(e)
            self.entries = list(reversed(keep))
        images = [e for e in self.entries if is_image(e) and not e["pinned"]]
        total, drop = 0, set()
        for n, e in enumerate(images):
            total += e["size"]
            if n >= MAX_IMAGES or total > MAX_IMAGE_BYTES:
                drop.add(id(e))
        if drop:
            self.entries = [e for e in self.entries if id(e) not in drop]
        if not any(is_image(e) and e["key"] == self._decoded[0] for e in self.entries):
            self._decoded = (None, None)

    def copy(self, text: str):
        if self._clipboard is not None:
            self._clipboard.setText(text)

    def image_of(self, entry: dict) -> QImage:
        key, img = self._decoded
        if key == entry["key"] and img is not None:
            return img
        img = QImage.fromData(entry["png"], "PNG")
        if not img.isNull():
            self._decoded = (entry["key"], img)
        return img

    def thumb_of(self, entry: dict) -> QImage:
        if entry.get("thumb") is None:
            img = self.image_of(entry)
            entry["thumb"] = make_thumb(img) if not img.isNull() else QImage()
        return entry["thumb"]

    def copy_image(self, entry: dict):
        if self._clipboard is not None:
            img = self.image_of(entry)
            if not img.isNull():
                self._clipboard.setImage(img)

    def save_image(self, entry: dict, path: str) -> bool:
        try:
            with open(path, "wb") as f:
                f.write(entry["png"])
            return True
        except OSError as e:
            print(f"[clipboard] save failed: {e}")
            return False

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
        self._trim()
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
        pins = []
        for e in self.entries:
            if e["pinned"]:
                pins.append({"image": e["key"], "w": e["w"], "h": e["h"]}
                            if is_image(e) else e["text"])
        self.cfg["pinned"] = pins
        self._sync_images()
        self._on_change()

    def _history_changed(self):
        self.changed.emit()
        if self.cfg.get("remember_history"):
            self._save_timer.start()

    def _image_path(self, key: str) -> str:
        return os.path.join(cfg_store.data_path(IMAGE_DIR), key + ".png")

    def _load_image(self, item: dict, pinned=False, ts=0.0):
        key = item.get("image")
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            return None
        try:
            with open(self._image_path(key), "rb") as f:
                png = f.read()
        except OSError:
            return None

        def num(name):
            try:
                return max(0, int(item.get(name) or 0))
            except (TypeError, ValueError):
                return 0

        return {"kind": "image", "text": "", "key": key, "png": png,
                "w": num("w"), "h": num("h"), "size": len(png), "thumb": None,
                "ts": ts, "pinned": pinned}

    def _sync_images(self):
        remember = self.cfg.get("remember_history")
        keep = {e["key"]: e for e in self.entries if is_image(e) and (
            e["pinned"] or (remember and e["size"] <= MAX_PERSIST_IMAGE_BYTES))}
        folder = cfg_store.data_path(IMAGE_DIR)
        try:
            if keep:
                os.makedirs(folder, exist_ok=True)
            for key, e in keep.items():
                path = self._image_path(key)
                if not os.path.exists(path):
                    tmp = path + ".tmp"
                    with open(tmp, "wb") as f:
                        f.write(e["png"])
                    os.replace(tmp, path)
            if os.path.isdir(folder):
                for name in os.listdir(folder):
                    stem, ext = os.path.splitext(name)
                    if ext == ".png" and _KEY.fullmatch(stem) and stem not in keep:
                        os.remove(os.path.join(folder, name))
        except OSError as e:
            print(f"[clipboard] image files: {e}")

    def _load_history(self):
        data = cfg_store.read_json(cfg_store.data_path(HISTORY_FILE), [])
        if not isinstance(data, list):
            return
        known = {e["text"] for e in self.entries if not is_image(e)}
        keys = {e["key"] for e in self.entries if is_image(e)}
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                ts = float(item.get("ts", 0) or 0)
            except (TypeError, ValueError):
                ts = 0.0
            if "image" in item:
                if item.get("image") in keys:
                    continue
                e = self._load_image(item, ts=ts)
                if e:
                    self.entries.append(e)
                    keys.add(e["key"])
            elif (isinstance(item.get("text"), str) and item["text"]
                    and item["text"] not in known):
                self.entries.append({"text": item["text"], "ts": ts, "pinned": False})
                known.add(item["text"])
        self._trim()

    def flush(self):
        self._save_timer.stop()
        path = cfg_store.data_path(HISTORY_FILE)
        items = None
        if self.cfg.get("remember_history"):
            items = []
            for e in self.entries:
                if e["pinned"]:
                    continue
                if is_image(e):
                    if e["size"] <= MAX_PERSIST_IMAGE_BYTES:
                        items.append({"image": e["key"], "w": e["w"], "h": e["h"],
                                      "ts": e["ts"]})
                elif len(e["text"]) <= MAX_PERSIST_CHARS:
                    items.append({"text": e["text"], "ts": e["ts"]})
        elif os.path.exists(path):
            items = []
        self._sync_images()
        if items is not None:
            cfg_store.write_json(path, items)
