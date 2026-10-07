import os

ONEDIR = os.environ.get("VOLT_ONEDIR") == "1"

EXCLUDES = [
    "tkinter", "unittest", "pydoc",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtNetwork",
    "PySide6.QtWebEngineCore", "PySide6.QtTest", "PySide6.QtPdf",
    "PySide6.QtSvg", "PySide6.QtOpenGL",
    "win32com", "pythoncom", "pywintypes",
]

DROP = (
    "opengl32sw.dll", "qt6quick", "qt6qml", "qt6pdf", "qt6opengl",
    "qt6network", "qt6svg", "qt6virtualkeyboard", "qdirect2d", "qpdf",
    "qsvg", "qtvirtualkeyboard", "/translations/",
)


def _keep(entry):
    name = entry[0].replace("\\", "/").lower()
    return not any(d in name for d in DROP)


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]
pyz = PYZ(a.pure)

if ONEDIR:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="Volt",
        debug=False,
        strip=False,
        upx=False,
        console=False,
        icon=["assets/volt.ico"],
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Volt")
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="Volt",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=["assets/volt.ico"],
    )
