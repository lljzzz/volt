import base64
import hashlib
import html
import json
import re
import urllib.parse


def upper(t: str) -> str:
    return t.upper()


def lower(t: str) -> str:
    return t.lower()


def title(t: str) -> str:
    return t.title()


def sentence(t: str) -> str:
    out = t.lower()
    return re.sub(r"(^\s*|[.!?]\s+)([a-zà-ÿ])",
                  lambda m: m.group(1) + m.group(2).upper(), out)


def _words(t: str) -> list[str]:
    t = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", t)
    return [w for w in re.split(r"[^0-9A-Za-zÀ-ÿ]+", t) if w]


def camel(t: str) -> str:
    w = _words(t)
    return (w[0].lower() + "".join(x.capitalize() for x in w[1:])) if w else ""


def pascal(t: str) -> str:
    return "".join(x.capitalize() for x in _words(t))


def snake(t: str) -> str:
    return "_".join(x.lower() for x in _words(t))


def kebab(t: str) -> str:
    return "-".join(x.lower() for x in _words(t))


def trim(t: str) -> str:
    lines = [line.strip() for line in t.strip().splitlines()]
    return "\n".join(lines)


def one_line(t: str) -> str:
    return " ".join(t.split())


def sort_lines(t: str) -> str:
    return "\n".join(sorted(t.splitlines(), key=str.casefold))


def unique_lines(t: str) -> str:
    return "\n".join(dict.fromkeys(t.splitlines()))


def reverse_lines(t: str) -> str:
    return "\n".join(reversed(t.splitlines()))


def remove_blank_lines(t: str) -> str:
    return "\n".join(line for line in t.splitlines() if line.strip())


def b64_encode(t: str) -> str:
    return base64.b64encode(t.encode("utf-8")).decode("ascii")


def b64_decode(t: str) -> str:
    s = "".join(t.split())
    if not s or not re.fullmatch(r"[A-Za-z0-9+/_-]+={0,2}", s):
        raise ValueError("not valid Base64 text")
    s = s.rstrip("=").replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s, validate=True).decode("utf-8")
    except Exception:
        raise ValueError("not valid Base64 text") from None


def url_encode(t: str) -> str:
    return urllib.parse.quote(t, safe="")


def url_decode(t: str) -> str:
    return urllib.parse.unquote(t)


def html_escape(t: str) -> str:
    return html.escape(t)


def html_unescape(t: str) -> str:
    return html.unescape(t)


def json_pretty(t: str) -> str:
    try:
        return json.dumps(json.loads(t), indent=2, ensure_ascii=False)
    except ValueError:
        raise ValueError("not valid JSON") from None


def json_minify(t: str) -> str:
    try:
        return json.dumps(json.loads(t), separators=(",", ":"), ensure_ascii=False)
    except ValueError:
        raise ValueError("not valid JSON") from None


def md5(t: str) -> str:
    return hashlib.md5(t.encode("utf-8")).hexdigest()


def sha1(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def sha256(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


TRANSFORMS = [
    ("upper", "UPPER", upper, "Case"),
    ("lower", "lower", lower, "Case"),
    ("title", "Title", title, "Case"),
    ("trim", "Trim", trim, "Lines"),
    ("one_line", "One line", one_line, "Lines"),
    ("sentence", "Sentence case", sentence, "Case"),
    ("camel", "camelCase", camel, "Case"),
    ("pascal", "PascalCase", pascal, "Case"),
    ("snake", "snake_case", snake, "Case"),
    ("kebab", "kebab-case", kebab, "Case"),
    ("sort", "Sort lines", sort_lines, "Lines"),
    ("unique", "Unique lines", unique_lines, "Lines"),
    ("reverse", "Reverse lines", reverse_lines, "Lines"),
    ("noblank", "Remove blank lines", remove_blank_lines, "Lines"),
    ("b64e", "Base64 encode", b64_encode, "Encode"),
    ("b64d", "Base64 decode", b64_decode, "Encode"),
    ("urle", "URL encode", url_encode, "Encode"),
    ("urld", "URL decode", url_decode, "Encode"),
    ("htmle", "HTML escape", html_escape, "Encode"),
    ("htmld", "HTML unescape", html_unescape, "Encode"),
    ("jsonp", "JSON pretty", json_pretty, "Format"),
    ("jsonm", "JSON minify", json_minify, "Format"),
    ("md5", "MD5", md5, "Hash"),
    ("sha1", "SHA-1", sha1, "Hash"),
    ("sha256", "SHA-256", sha256, "Hash"),
]
QUICK = TRANSFORMS[:5]
GROUPS = ["Case", "Lines", "Encode", "Format", "Hash"]


def apply(fn, text: str):
    try:
        return fn(text), None
    except ValueError as e:
        return None, str(e) or "can't transform this text"
    except Exception as e:
        return None, f"failed: {e}"


def stats(t: str) -> dict:
    return {
        "chars": len(t),
        "words": len(t.split()),
        "lines": (t.count("\n") + 1) if t else 0,
        "bytes": len(t.encode("utf-8")),
    }
