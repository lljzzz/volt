from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication,
                           QIcon, QPainter, QPixmap)

_GLYPHS = {
    "dashboard": ("\uECA5", "◈"),
    "autoclicker": ("\uE962", "⊙"),
    "macros": ("\uE768", "▸"),
    "snippets": ("\uE765", "⌗"),
    "clipboard": ("\uE77F", "⧉"),
    "notes": ("\uE70B", "≡"),
    "text": ("\uE8D2", "A"),
    "capture": ("\uE722", "▣"),
    "nudge": ("\uE7C2", "⌖"),
    "picker": ("\uEF3C", "◉"),
    "timers": ("\uE916", "◷"),
    "settings": ("\uE713", "⛭"),
    "bolt": ("\uE945", "◆"),
    "pin": ("\uE718", "▴"),
    "pinned": ("\uE840", "▴"),
    "min": ("\uE921", "–"),
    "max": ("\uE922", "□"),
    "restore": ("\uE923", "▣"),
    "close": ("\uE8BB", "✕"),
    "play": ("\uE768", "▶"),
    "stop": ("\uE71A", "■"),
    "pause": ("\uE769", "‖"),
    "record": ("\uE7C8", "●"),
    "copy": ("\uE8C8", "⧉"),
    "paste": ("\uE77F", "⎘"),
    "search": ("\uE721", "⌕"),
    "add": ("\uE710", "+"),
    "delete": ("\uE74D", "✕"),
    "edit": ("\uE70F", "✎"),
    "folder": ("\uE8B7", "▤"),
    "window": ("\uE737", "▢"),
    "link": ("\uE71B", "↗"),
    "calc": ("\uE8EF", "="),
    "color": ("\uE790", "◐"),
    "power": ("\uE7E8", "⏻"),
    "coffee": ("\uEC32", "☕"),
    "keyboard": ("\uE765", "⌨"),
    "mouse": ("\uE962", "⊙"),
    "target": ("\uE81D", "◎"),
    "history": ("\uE81C", "↺"),
    "check": ("\uE73E", "✓"),
    "info": ("\uE946", "i"),
    "up": ("\uE70E", "▴"),
    "down": ("\uE70D", "▾"),
    "image": ("\uEB9F", "▣"),
}

_family = None


def family() -> str | None:
    global _family
    if _family is None:
        fams = set(QFontDatabase.families())
        _family = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets")
                        if f in fams), "")
    return _family or None


def glyph(name: str) -> str:
    g = _GLYPHS.get(name, ("", "•"))
    return g[0] if family() else g[1]


def font(px: int) -> QFont:
    f = QFont(family()) if family() else QFont()
    f.setPixelSize(px)
    return f


def css(px: int, color: str | None = None) -> str:
    out = f"font-family: '{family()}'; font-size: {px}px;" if family() else \
        f"font-size: {px}px;"
    return out + (f" color: {color};" if color else "")


def pixmap(name: str, color: str, px: int = 16) -> QPixmap:
    dpr = QGuiApplication.primaryScreen().devicePixelRatio() if \
        QGuiApplication.primaryScreen() else 1.0
    pm = QPixmap(int(px * dpr), int(px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setPen(QColor(color))
    p.setFont(font(int(px * 0.9)))
    p.drawText(QRectF(0, 0, px, px), Qt.AlignCenter, glyph(name))
    p.end()
    return pm


def icon(name: str, color: str = "#c9ccd1", px: int = 16,
         on_color: str | None = None) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, px), QIcon.Normal, QIcon.Off)
    if on_color:
        ic.addPixmap(pixmap(name, on_color, px), QIcon.Normal, QIcon.On)
    ic.addPixmap(pixmap(name, "#55585e", px), QIcon.Disabled, QIcon.Off)
    return ic
