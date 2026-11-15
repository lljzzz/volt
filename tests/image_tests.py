from PySide6.QtGui import QColor, QImage, QPainter

from core import clipboard as clipmod
from core.clipboard import ClipboardWatcher, is_image


def demo_image(seed, w=640, h=360):
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor("#202124"))
    p = QPainter(img)
    p.setBrush(QColor(["#e8743b", "#4d8df6", "#1fb5a3", "#e85d8f", "#9776f0"][seed % 5]))
    p.drawRect(20 + seed * 7 % 300, 30, 200, 120)
    p.drawText(40, 300, f"Demo image {seed}")
    p.end()
    return img


watch = ctrl.clipboard
img_dir = os.path.join(DATA, "clipboard_images")
before = len(watch.entries)
cb.setImage(demo_image(1))
app.processEvents()
imgs = [e for e in watch.entries if is_image(e)]
check("image captured", len(imgs) == 1 and watch.entries[0] is imgs[0], len(imgs))
e1 = imgs[0]
check("image fields", e1["w"] == 640 and e1["h"] == 360 and e1["size"] > 0
      and not e1["thumb"].isNull() and e1["thumb"].width() <= 112)
cb.setText("between")
app.processEvents()
cb.setImage(demo_image(1))
app.processEvents()
check("same image deduplicated", sum(1 for e in watch.entries if is_image(e)) == 1
      and watch.entries[0] is e1)
check("text path still works", any(e.get("text") == "between" for e in watch.entries))
watch.cfg["images"] = False
cb.setImage(demo_image(2))
app.processEvents()
check("images toggle off skips", sum(1 for e in watch.entries if is_image(e)) == 1)
watch.cfg["images"] = True

watch.set_pinned(e1, True)
pin_file = os.path.join(img_dir, e1["key"] + ".png")
check("pinned image written", os.path.exists(pin_file))
check("pin stored in config", {"image": e1["key"], "w": 640, "h": 360} in watch.cfg["pinned"])
w2 = ClipboardWatcher({"clipboard": json.loads(json.dumps(watch.cfg))}, lambda: None)
check("pinned image survives restart",
      any(is_image(e) and e["key"] == e1["key"] and e["pinned"] for e in w2.entries))
again = next(e for e in w2.entries if is_image(e))
check("lazy thumb from disk", again["thumb"] is None and not w2.thumb_of(again).isNull())

for i in range(3, 3 + 24):
    cb.setImage(demo_image(i, 320, 200))
    app.processEvents()
unpinned = [e for e in watch.entries if is_image(e) and not e["pinned"]]
check("image budget keeps 20 newest", len(unpinned) == clipmod.MAX_IMAGES, len(unpinned))
check("pinned image never dropped", e1 in watch.entries)

watch.set_remember(True)
watch.flush()
hist = json.load(open(os.path.join(DATA, "clipboard_history.json"), encoding="utf-8"))
img_items = [h for h in hist if "image" in h]
check("remembered images listed", len(img_items) == 20, len(img_items))
check("remembered image files written",
      all(os.path.exists(os.path.join(img_dir, h["image"] + ".png")) for h in img_items))
w3 = ClipboardWatcher({"clipboard": json.loads(json.dumps(watch.cfg))}, lambda: None)
check("history images reload", sum(1 for e in w3.entries if is_image(e)) == 21)
watch.set_remember(False)
left = sorted(os.listdir(img_dir))
check("forgetting history deletes its files", left == [e1["key"] + ".png"], left)
watch.set_pinned(e1, False)
check("unpinning deletes file", not os.path.exists(pin_file))

page = win.pages["Clipboard"]
win.navigate("Clipboard")
app.processEvents()
row = next(i for i, e in enumerate(page._shown) if is_image(e))
page.list.setCurrentRow(row)
app.processEvents()
check("image preview shown", page.preview_stack.currentWidget() is page.image_view
      and page.image_view._img is not None)
check("image buttons", page.save_btn.isVisible() and page.float_btn.isVisible()
      and not any(b.isEnabled() for b in page.transform_btns))
target = page._shown[row]
page._copy_item(page.list.currentItem())
app.processEvents()
check("copy image back", clipmod.image_key(cb.image()) == target["key"])
page.search.setText("image")
app.processEvents()
check("search finds images", page._shown and all(is_image(e) for e in page._shown))
page.search.setText("")
text_row = next(i for i, e in enumerate(page._shown) if not is_image(e))
page.list.setCurrentRow(text_row)
app.processEvents()
check("text preview back", page.preview_stack.currentWidget() is page.preview
      and not page.save_btn.isVisible())
page.list.setCurrentRow(row)
shot("dark_clipboard_images")

win.palette.open("image")
app.processEvents()
items = [it for it in win.palette._display if it.image is not None]
check("palette lists images", bool(items))
cb.setText("x")
app.processEvents()
win.palette.list.setCurrentRow(win.palette._display.index(items[0]))
win.palette._execute(copy_only=True)
app.processEvents()
check("palette copies image", clipmod.image_key(cb.image()) == items[0].image["key"])

# Test storage and budget boundaries separately from the UI's shared history.
from unittest.mock import patch
from PySide6.QtCore import QMimeData


class ImageClipboard:
    def __init__(self):
        self.img = QImage()
        self.md = QMimeData()

    def image(self):
        return self.img

    def mimeData(self):
        return self.md

    def put(self, img, private=False):
        self.img = img
        self.md = QMimeData()
        self.md.setImageData(img)
        if private:
            self.md.setData("ExcludeClipboardContentFromMonitorProcessing", b"1")


def small_image(seed):
    img = QImage(64, 40, QImage.Format_ARGB32)
    img.fill(QColor.fromHsv(seed % 360, 200, 200))
    return img


edge_data = os.path.join(OUT, "image-edge-data")
os.makedirs(edge_data)
edge_cb = ImageClipboard()
with patch.object(cfg_store, "CONFIG_PATH", os.path.join(edge_data, "volt_config.json")):
    edge = ClipboardWatcher({"clipboard": {}}, lambda: None)
    edge._clipboard = edge_cb
    a, b = small_image(101), small_image(102)
    edge_cb.put(a)
    edge._capture_image()
    entry = edge.entries[0]
    edge.flush()
    check("unpinned image stays off disk by default", not os.listdir(edge_data))
    saved = os.path.join(edge_data, "saved.png")
    check("saved PNG roundtrip", edge.save_image(entry, saved)
          and clipmod.image_key(QImage(saved)) == entry["key"])

    edge_cb.put(b, private=True)
    edge._capture_image()
    check("private image skipped", len(edge.entries) == 1 and edge.skipped_private == 1)
    edge.cfg["enabled"] = False
    edge_cb.put(b)
    edge._capture_image()
    check("disabled watcher skips image", len(edge.entries) == 1)
    edge.cfg["enabled"] = True

    with patch.object(clipmod, "MAX_IMAGE_BYTES", len(clipmod.encode_png(a))
                      + len(clipmod.encode_png(b)) - 1):
        edge._capture_image()
        check("byte budget evicts oldest image", len(edge.entries) == 1
              and edge.entries[0]["key"] == clipmod.image_key(b))
    edge.clear_unpinned()
    with patch.object(clipmod, "MAX_IMAGE_BYTES", 1):
        edge._capture_image()
        check("single oversized image rejected", not edge.entries)

    edge_cb.put(a)
    edge._capture_image()
    first = edge.entries[0]
    edge.set_pinned(first, True)
    with patch.object(clipmod, "MAX_IMAGES", 2):
        for seed in (103, 104):
            edge_cb.put(small_image(seed))
            edge._capture_image()
        check("pins excluded from history budget", len(edge.entries) == 3
              and first in edge.entries)
        edge.set_pinned(first, False)
        check("unpin reapplies image budget", len(edge.entries) == 2
              and first not in edge.entries)
        check("evicted unpinned image file removed",
              not os.path.exists(edge._image_path(first["key"])))

    with patch.object(clipmod, "MAX_PERSIST_IMAGE_BYTES", 1):
        edge.set_remember(True)
        history = cfg_store.read_json(cfg_store.data_path("clipboard_history.json"), [])
        check("large unpinned images stay memory only", len(edge.entries) == 2
              and not history and not os.listdir(cfg_store.data_path("clipboard_images")))
        edge.set_pinned(edge.entries[0], True)
        edge.flush()
        check("explicit pin persists above automatic save limit",
              os.path.isfile(edge._image_path(edge.entries[0]["key"])))
        edge.delete(edge.entries[0])
        check("deleting pin removes PNG", not os.listdir(cfg_store.data_path("clipboard_images")))
    edge.set_remember(False)

win.palette.open("image")
app.processEvents()
image_item = next(it for it in win.palette._display if it.image is not None)
win.palette.list.setCurrentRow(win.palette._display.index(image_item))
win.palette._target_hwnd = 12345
with patch.object(ctrl, "paste_image_into") as paste:
    win.palette._execute(copy_only=False)
    check("palette pastes image into original target",
          paste.call_count == 1 and paste.call_args.args[0] == 12345
          and paste.call_args.args[1] is image_item.image)
