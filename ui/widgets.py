from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPropertyAnimation,
                            QRect, QRectF, QSize, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox, QFrame,
                               QHBoxLayout, QLabel, QLayout, QMessageBox,
                               QPushButton, QSizePolicy, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from . import icons
from .styles import (ACCENT, BORDER_3, GREEN, SURFACE, SURFACE_3, TEXT_DIM,
                     TEXT_MUTED)

ROLE_SUB = Qt.UserRole + 1
ROLE_GLYPH = Qt.UserRole + 2
ROLE_COLOR = Qt.UserRole + 3
ROLE_RIGHT = Qt.UserRole + 4
ROLE_DIM = Qt.UserRole + 5


def repolish(w: QWidget, object_name: str | None = None):
    if object_name is not None:
        w.setObjectName(object_name)
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def small_label(text, wrap=False):
    lbl = QLabel(text, objectName="Muted")
    lbl.setWordWrap(wrap)
    return lbl


def hint(text):
    lbl = QLabel(text, objectName="Hint")
    lbl.setWordWrap(True)
    return lbl


def button(text, role="Ghost", slot=None, tip=None, icon_name=None):
    b = QPushButton(text, objectName=role)
    b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    if tip:
        b.setToolTip(tip)
    if icon_name:
        b.setIcon(icons.icon(icon_name, "#1a0f08" if role == "Primary" else "#c9ccd1"))
    return b


def icon_button(name, tip, slot=None, px=16):
    b = QPushButton(objectName="IconBtn")
    b.setIcon(icons.icon(name, TEXT_DIM, px))
    b.setIconSize(QSize(px, px))
    b.setFixedSize(px + 14, px + 14)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip(tip)
    if slot:
        b.clicked.connect(slot)
    return b


def confirm(parent, title, text, yes="Delete") -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    ok = box.addButton(yes, QMessageBox.AcceptRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.setDefaultButton(ok)
    box.exec()
    return box.clickedButton() is ok


def page_header(title: str, subtitle: str | None = None):
    box = QVBoxLayout()
    box.setSpacing(3)
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(QLabel(title, objectName="PageTitle"))
    row.addStretch()
    box.addLayout(row)
    if subtitle:
        sub = QLabel(subtitle, objectName="PageSubtitle")
        sub.setWordWrap(True)
        box.addWidget(sub)
    return box, row


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked=False):
        super().__init__()
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self._checked = bool(checked)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def isChecked(self):
        return self._checked

    def setChecked(self, val: bool):
        val = bool(val)
        if val == self._checked:
            return
        self._checked = val
        self._animate()

    def toggle(self):
        self._checked = not self._checked
        self._animate()
        self.toggled.emit(self._checked)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.toggle()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.toggle()
        else:
            super().keyPressEvent(e)

    def _animate(self):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if self._checked else 0.0)
        self._anim.start()

    def getOffset(self):
        return self._offset

    def setOffset(self, v):
        self._offset = v
        self.update()

    offset = Property(float, getOffset, setOffset)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        off, on = QColor("#3a3d42"), QColor(GREEN)
        t = self._offset
        col = QColor(int(off.red() + (on.red() - off.red()) * t),
                     int(off.green() + (on.green() - off.green()) * t),
                     int(off.blue() + (on.blue() - off.blue()) * t))
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        h = self.height()
        p.drawRoundedRect(0, 0, self.width(), h, h / 2, h / 2)
        knob = h - 6
        x = 3 + t * (self.width() - knob - 6)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 3, knob, knob))
        if self.hasFocus():
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(ACCENT))
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, h - 1), h / 2, h / 2)


class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str = None):
        super().__init__()
        wrap = QFrame(objectName="SegWrap")
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._btns = {}
        for key, label in options:
            b = QPushButton(label, objectName="Seg", checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            self._group.addButton(b)
            lay.addWidget(b)
            self._btns[key] = b
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(wrap)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setValue(value or options[0][0])

    def _pick(self, key):
        self.changed.emit(key)

    def value(self):
        for k, b in self._btns.items():
            if b.isChecked():
                return k
        return None

    def setValue(self, key):
        if key in self._btns:
            self._btns[key].setChecked(True)


class Card(QFrame):
    def __init__(self, title: str, header_widget: QWidget = None,
                 subtitle: str | None = None):
        super().__init__(objectName="Card")
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(18, 15, 18, 17)
        self._v.setSpacing(12)
        head = QVBoxLayout()
        head.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title_label = QLabel(title, objectName="CardTitle")
        top.addWidget(self.title_label)
        top.addStretch()
        if header_widget:
            top.addWidget(header_widget)
        self.header_row = top
        head.addLayout(top)
        if subtitle:
            head.addWidget(hint(subtitle))
        self._v.addLayout(head)

    def body(self) -> QVBoxLayout:
        return self._v

    def add(self, w):
        self._v.addWidget(w)
        return w

    def add_row(self, *widgets, stretch_last=False):
        row = QHBoxLayout()
        row.setSpacing(10)
        for i, w in enumerate(widgets):
            if isinstance(w, str):
                w = QLabel(w)
            row.addWidget(w)
            if stretch_last and i == 0:
                row.addStretch()
        self._v.addLayout(row)
        return row

    def setting(self, label: str, *widgets, tip: str | None = None):
        lbl = small_label(label)
        if tip:
            lbl.setToolTip(tip)
        row = self.add_row(lbl, stretch_last=True)
        for w in widgets:
            row.addWidget(w)
        return row


class RefreshingCombo(QComboBox):
    def __init__(self, provider):
        super().__init__()
        self._provider = provider
        self.setMinimumWidth(180)
        self.setMaximumWidth(320)

    def showPopup(self):
        current = self.currentText()
        self.blockSignals(True)
        self.clear()
        items = self._provider() or []
        self.addItems(items)
        if current in items:
            self.setCurrentText(current)
        self.blockSignals(False)
        super().showPopup()


class NavButton(QAbstractButton):
    def __init__(self, icon_name: str, text: str, shortcut_hint: str = ""):
        super().__init__()
        self._icon = icon_name
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setAttribute(Qt.WA_Hover)
        self._badge = None
        self._badge_color = GREEN
        if shortcut_hint:
            self.setToolTip(f"{text}  ({shortcut_hint})")

    def set_badge(self, value=None, color=GREEN):
        if value == self._badge and color == self._badge_color:
            return
        self._badge, self._badge_color = value, color
        self.update()

    def sizeHint(self):
        return QSize(150, 36)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        hover, checked = self.underMouse(), self.isChecked()
        if checked or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#1e2024" if checked else "#17191c"))
            p.drawRoundedRect(r, 8, 8)
        if checked:
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(QRectF(0, 10, 3, r.height() - 20), 1.5, 1.5)
        fg = "#ffffff" if checked else ("#d4d6da" if hover else TEXT_DIM)
        p.setPen(QColor(ACCENT if checked else fg))
        p.setFont(icons.font(15))
        p.drawText(QRectF(12, 0, 22, r.height()), Qt.AlignCenter,
                   icons.glyph(self._icon))
        f = QFont(self.font())
        f.setPixelSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(fg))
        right_pad = 30 if self._badge is not None else 8
        text_rect = QRectF(42, 0, r.width() - 42 - right_pad, r.height())
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                   QFontMetrics(f).elidedText(self.text(), Qt.ElideRight,
                                              int(text_rect.width())))
        if self._badge is not None:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self._badge_color))
            if self._badge == "":
                p.drawEllipse(QRectF(r.width() - 18, r.height() / 2 - 4, 8, 8))
            else:
                bf = QFont(f)
                bf.setPixelSize(10)
                bf.setWeight(QFont.Bold)
                w = max(18, QFontMetrics(bf).horizontalAdvance(self._badge) + 10)
                pill = QRectF(r.width() - w - 8, r.height() / 2 - 8, w, 16)
                p.drawRoundedRect(pill, 8, 8)
                p.setFont(bf)
                p.setPen(QColor("#06140b"))
                p.drawText(pill, Qt.AlignCenter, self._badge)


class StatTile(QFrame):
    clicked = Signal()

    def __init__(self, icon_name: str, label: str):
        super().__init__(objectName="Tile")
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 13, 16, 14)
        v.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(7)
        self._glyph = QLabel(icons.glyph(icon_name))
        self._glyph.setStyleSheet(icons.css(14, TEXT_DIM))
        top.addWidget(self._glyph)
        top.addWidget(QLabel(label, objectName="TileLabel"))
        top.addStretch()
        self.extra = top
        v.addLayout(top)
        self.value = QLabel("-", objectName="TileValue")
        v.addWidget(self.value)
        self.sub = small_label("")
        v.addWidget(self.sub)

    def set(self, value: str, sub: str = "", accent: str | None = None):
        self.value.setText(value)
        self.sub.setText(sub)
        self._glyph.setStyleSheet(icons.css(14, accent or TEXT_DIM))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class Toast(QLabel):
    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self._fade)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(220)
        self._anim.finished.connect(self._done)

    def show_message(self, text: str, anchor: QWidget | None = None, ms=1900):
        self._anim.stop()
        self.setWindowOpacity(1.0)
        self.setText(text)
        self.adjustSize()
        if anchor is not None and anchor.isVisible() and not anchor.isMinimized():
            g = anchor.frameGeometry()
            x = g.x() + (g.width() - self.width()) // 2
            y = g.y() + g.height() - self.height() - 26
        else:
            screen = (QGuiApplication.screenAt(QCursor.pos())
                      or QGuiApplication.primaryScreen())
            a = screen.availableGeometry()
            x = a.x() + (a.width() - self.width()) // 2
            y = a.y() + a.height() - self.height() - 48
        self.move(QPoint(x, y))
        self.show()
        self.raise_()
        self._hide.start(ms)

    def _fade(self):
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _done(self):
        if self.windowOpacity() < 0.05:
            self.hide()


class RichDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.compact = compact

    def sizeHint(self, option, index):
        if self.compact:
            return QSize(option.rect.width(), 38)
        return QSize(option.rect.width(), 52 if index.data(ROLE_SUB) else 38)

    def paint(self, p, option, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(2, 1, -2, -1)
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        enabled = bool(index.flags() & Qt.ItemIsEnabled)
        if selected or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(SURFACE_3 if selected else SURFACE))
            p.drawRoundedRect(r, 7, 7)

        title = index.data(Qt.DisplayRole) or ""
        sub = index.data(ROLE_SUB) or ""
        glyph = index.data(ROLE_GLYPH)
        right = index.data(ROLE_RIGHT) or ""
        dim = bool(index.data(ROLE_DIM)) or not enabled

        x = r.left() + 10
        if glyph:
            p.setFont(icons.font(15))
            p.setPen(QColor(index.data(ROLE_COLOR) or TEXT_DIM))
            p.drawText(QRectF(x, r.top(), 20, r.height()), Qt.AlignCenter,
                       icons.glyph(glyph))
            x += 30
        base = QFont(option.font)
        base.setPixelSize(13)
        small = QFont(option.font)
        small.setPixelSize(12)
        fm, fms = QFontMetrics(base), QFontMetrics(small)

        right_w = fms.horizontalAdvance(right) + 14 if right else 0
        avail = r.right() - 10 - right_w - x
        title_col = QColor("#ffffff" if selected else ("#7b7f85" if dim else "#d8dade"))
        if self.compact or not sub:
            line = QRectF(x, r.top(), avail, r.height())
            p.setFont(base)
            p.setPen(title_col)
            tw = min(fm.horizontalAdvance(title), int(avail))
            p.drawText(line, Qt.AlignVCenter | Qt.AlignLeft,
                       fm.elidedText(title, Qt.ElideRight, int(avail)))
            if sub and self.compact and avail - tw > 40:
                p.setFont(small)
                p.setPen(QColor(TEXT_MUTED))
                sub_rect = QRectF(x + tw + 12, r.top(), avail - tw - 12, r.height())
                p.drawText(sub_rect, Qt.AlignVCenter | Qt.AlignLeft,
                           fms.elidedText(sub, Qt.ElideRight, int(sub_rect.width())))
        else:
            p.setFont(base)
            p.setPen(title_col)
            p.drawText(QRectF(x, r.top() + 7, avail, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(title, Qt.ElideRight, int(avail)))
            p.setFont(small)
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(QRectF(x, r.top() + 26, avail, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       fms.elidedText(sub, Qt.ElideRight, int(avail)))
        if right:
            p.setFont(small)
            p.setPen(QColor(TEXT_DIM))
            p.drawText(QRectF(r.right() - right_w - 8, r.top(), right_w, r.height()),
                       Qt.AlignVCenter | Qt.AlignRight, right)
        p.restore()


def rich_list(view, compact=False):
    view.setItemDelegate(RichDelegate(view, compact))
    view.setMouseTracking(True)
    view.viewport().setAttribute(Qt.WA_Hover)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setUniformItemSizes(False)
    return view


def set_item(item, title, sub="", glyph=None, color=None, right="", dim=False):
    item.setText(title)
    item.setData(ROLE_SUB, sub)
    item.setData(ROLE_GLYPH, glyph)
    item.setData(ROLE_COLOR, color)
    item.setData(ROLE_RIGHT, right)
    item.setData(ROLE_DIM, dim)
    item.setToolTip("")
    return item


def separator():
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{BORDER_3}; border:none;")
    return line


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self._sp = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, width, 0), dry=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, dry=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect, dry):
        lines, line, x = [], [], rect.x()
        for it in self._items:
            if it.widget() is not None and it.widget().isHidden():
                continue
            w = it.sizeHint().width()
            if line and x + w > rect.right() + 1:
                lines.append(line)
                line, x = [], rect.x()
            line.append(it)
            x += w + self._sp
        if line:
            lines.append(line)
        y = rect.y()
        for i, line in enumerate(lines):
            line_h = max(it.sizeHint().height() for it in line)
            if not dry:
                x = rect.x()
                for it in line:
                    s = it.sizeHint()
                    it.setGeometry(QRect(QPoint(x, y + (line_h - s.height()) // 2), s))
                    x += s.width() + self._sp
            y += line_h + (self._sp if i < len(lines) - 1 else 0)
        return y - rect.y()


def pair(label: str, *widgets) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addWidget(small_label(label))
    for child in widgets:
        lay.addWidget(child)
    return w


def flow_row(*widgets, spacing=6) -> QWidget:
    w = QWidget()
    lay = FlowLayout(w, spacing)
    for child in widgets:
        if isinstance(child, str):
            child = small_label(child)
        lay.addWidget(child)
    return w
