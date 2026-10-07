import ast
import colorsys
import operator

from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication


def _screen_at(x: int, y: int):
    return (QGuiApplication.screenAt(QPoint(x, y))
            or QGuiApplication.primaryScreen())


def pixel_at(x: int, y: int):
    try:
        screen = _screen_at(x, y)
        g = screen.geometry()
        pm = screen.grabWindow(0, x - g.x(), y - g.y(), 1, 1)
        if pm.isNull():
            return None
        c = pm.toImage().pixelColor(0, 0)
        return (c.red(), c.green(), c.blue())
    except Exception:
        return None


def grab_around(x: int, y: int, radius: int = 5):
    try:
        screen = _screen_at(x, y)
        g = screen.geometry()
        side = radius * 2 + 1
        pm = screen.grabWindow(0, x - g.x() - radius, y - g.y() - radius,
                               side, side)
        return None if pm.isNull() else pm
    except Exception:
        return None


def to_hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def from_hex(hx: str):
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def to_hsl(rgb) -> tuple[int, int, int]:
    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return round(h * 360) % 360, round(s * 100), round(l * 100)


FORMATS = [("hex", "HEX"), ("rgb", "RGB"), ("hsl", "HSL")]


def fmt(rgb, kind: str) -> str:
    if kind == "rgb":
        return "rgb({}, {}, {})".format(*rgb)
    if kind == "hsl":
        return "hsl({}, {}%, {}%)".format(*to_hsl(rgb))
    return to_hex(rgb)


def contrast_text(rgb) -> str:
    r, g, b = rgb
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_ALLOWED_CHARS = set("0123456789.+-*/()% eE,")


def calc(text: str):
    expr = text.strip()
    if expr.startswith("="):
        expr = expr[1:].strip()
    expr = expr.replace("^", "**").replace(",", "")
    if not expr or len(expr) > 80 or not any(c.isdigit() for c in expr):
        return None
    if not set(expr) <= _ALLOWED_CHARS:
        return None
    if not any(op in expr for op in "+-*/%") and "(" not in expr:
        return None
    try:
        node = ast.parse(expr, mode="eval")
        value = _eval(node.body)
        if isinstance(value, float):
            if value.is_integer() and abs(value) < 1e15:
                value = int(value)
            else:
                value = round(value, 10)
        out = str(value)
    except Exception:
        return None
    return out if len(out) <= 60 else None


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > 1000 or abs(left) > 10 ** 9:
                raise ValueError("pow too large")
        return _OPS[type(node.op)](left, right)
    raise ValueError(f"disallowed expression: {type(node).__name__}")
