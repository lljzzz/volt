import time

from PySide6.QtCore import QTime, QTimer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QProgressBar,
                               QTimeEdit, QVBoxLayout, QWidget)

from core.timers import fmt_remaining, parse_duration
from .widgets import Card, button, flow_row, page_header, small_label

PRESETS = [1, 5, 10, 15, 25, 45, 60]


def _fmt_watch(secs: float) -> str:
    m, s = divmod(secs, 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:05.2f}" if h else f"{m:02d}:{s:05.2f}"


class TimersPage(QWidget):
    def __init__(self, controller, on_change):
        super().__init__()
        self.ctrl = controller
        self.mgr = controller.timers
        self._rows = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)
        head, _right = page_header(
            "Timers", "Volt keeps running in the tray, so you'll get a "
                      "notification and a beep wherever you are.")
        root.addLayout(head)

        quick = Card("Start a timer")
        quick.add(flow_row(*[button(f"{m} min", "Ghost",
                                    lambda _=False, m=m: self._start(m * 60))
                             for m in PRESETS], spacing=8))
        self.dur = QLineEdit()
        self.dur.setPlaceholderText("Duration: 25 · 1h30 · 90s · 1:30")
        self.dur.setFixedWidth(230)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Label (optional): tea, laundry, standup…")
        self.dur.returnPressed.connect(self._start_custom)
        self.label_edit.returnPressed.connect(self._start_custom)
        crow = quick.add_row(self.dur, self.label_edit)
        crow.addWidget(button("Start", "Primary", self._start_custom))
        self.alarm = QTimeEdit(QTime.currentTime().addSecs(3600))
        self.alarm.setDisplayFormat("HH:mm")
        self.alarm.setFixedWidth(110)
        arow = quick.add_row(small_label("Alarm at"), self.alarm)
        arow.addWidget(button("Set alarm", "Ghost", self._start_alarm))
        arow.addStretch()
        self.err = QLabel("", objectName="Error")
        self.err.setVisible(False)
        quick.add(self.err)
        root.addWidget(quick)

        self.active = Card("Running")
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(8)
        self.active.body().addLayout(self.list_box)
        root.addWidget(self.active)

        root.addWidget(self._stopwatch_card())
        root.addStretch()

        self.mgr.updated.connect(self._refresh)
        self._rebuild()

    def _start(self, secs, label=""):
        self.mgr.start(secs, label)
        self.ctrl.toast.emit(f"Timer set: {fmt_remaining(secs)}")

    def _start_custom(self):
        secs = parse_duration(self.dur.text())
        if not secs:
            self.err.setText("Try a duration like 25 (minutes), 1h30, 90s or 1:30.")
            self.err.setVisible(True)
            return
        self.err.setVisible(False)
        self._start(secs, self.label_edit.text().strip())
        self.dur.clear()
        self.label_edit.clear()

    def _start_alarm(self):
        t = self.alarm.time()
        self.mgr.start_at(t.hour(), t.minute(), self.label_edit.text().strip())
        self.label_edit.clear()
        self.ctrl.toast.emit(f"Alarm set for {t.toString('HH:mm')}")

    def _rebuild(self):
        while self.list_box.count():
            w = self.list_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._rows = {}
        if not self.mgr.items:
            self.list_box.addWidget(small_label("No timers running."))
            return
        for t in self.mgr.items:
            row = QFrame(objectName="Row")
            lay = QVBoxLayout(row)
            lay.setContentsMargins(14, 10, 12, 10)
            lay.setSpacing(6)
            top = QHBoxLayout()
            time_lbl = QLabel("")
            time_lbl.setStyleSheet("font-size:18px; font-weight:800;")
            top.addWidget(time_lbl)
            top.addWidget(small_label(t["label"]))
            top.addStretch()
            pause = button("", "GhostSmall", lambda _=False, i=t["id"]: self.mgr.toggle_pause(i))
            top.addWidget(pause)
            top.addWidget(button("+1 min", "GhostSmall",
                                 lambda _=False, i=t["id"]: self.mgr.add_time(i, 60)))
            top.addWidget(button("Cancel", "GhostSmall",
                                 lambda _=False, i=t["id"]: self.mgr.cancel(i)))
            lay.addLayout(top)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            lay.addWidget(bar)
            self.list_box.addWidget(row)
            self._rows[t["id"]] = (time_lbl, pause, bar)
        self._refresh_values()

    def _refresh(self):
        if set(self._rows) != {t["id"] for t in self.mgr.items}:
            self._rebuild()
        else:
            self._refresh_values()

    def _refresh_values(self):
        for t in self.mgr.items:
            widgets = self._rows.get(t["id"])
            if not widgets:
                continue
            time_lbl, pause, bar = widgets
            time_lbl.setText(fmt_remaining(self.mgr.remaining(t)))
            time_lbl.setStyleSheet("font-size:18px; font-weight:800;"
                                   + (" color:#6f7378;" if t["paused"] else ""))
            pause.setText("Resume" if t["paused"] else "Pause")
            bar.setValue(int(self.mgr.progress(t) * 1000))

    def _stopwatch_card(self):
        c = Card("Stopwatch")
        self._sw_start = None
        self._sw_acc = 0.0
        self._laps: list[float] = []
        row = QHBoxLayout()
        self.sw_lbl = QLabel("00:00.00")
        self.sw_lbl.setStyleSheet("font-size:28px; font-weight:800; "
                                  "font-family:'Cascadia Mono','Consolas',monospace;")
        row.addWidget(self.sw_lbl)
        row.addStretch()
        self.sw_go = button("Start", "Primary", self._sw_toggle)
        self.sw_lap = button("Lap", "Ghost", self._sw_lap_add)
        self.sw_reset = button("Reset", "Ghost", self._sw_reset_all)
        for b in (self.sw_go, self.sw_lap, self.sw_reset):
            row.addWidget(b)
        c.body().addLayout(row)
        self.laps = QListWidget()
        self.laps.setFixedHeight(110)
        self.laps.setVisible(False)
        c.add(self.laps)
        self._sw_timer = QTimer(self)
        self._sw_timer.setInterval(31)
        self._sw_timer.timeout.connect(self._sw_tick)
        self._sw_update_buttons()
        return c

    def _sw_elapsed(self) -> float:
        run = (time.perf_counter() - self._sw_start) if self._sw_start else 0.0
        return self._sw_acc + run

    def _sw_toggle(self):
        if self._sw_start is None:
            self._sw_start = time.perf_counter()
            self._sw_timer.start()
        else:
            self._sw_acc = self._sw_elapsed()
            self._sw_start = None
            self._sw_timer.stop()
            self._sw_tick()
        self._sw_update_buttons()

    def _sw_lap_add(self):
        if self._sw_start is None:
            return
        total = self._sw_elapsed()
        split = total - (self._laps[-1] if self._laps else 0.0)
        self._laps.append(total)
        it = QListWidgetItem(f"Lap {len(self._laps)}    {_fmt_watch(split)}    "
                             f"total {_fmt_watch(total)}")
        self.laps.insertItem(0, it)
        self.laps.setVisible(True)

    def _sw_reset_all(self):
        self._sw_start = None
        self._sw_acc = 0.0
        self._laps = []
        self._sw_timer.stop()
        self.laps.clear()
        self.laps.setVisible(False)
        self._sw_tick()
        self._sw_update_buttons()

    def _sw_tick(self):
        self.sw_lbl.setText(_fmt_watch(self._sw_elapsed()))

    def _sw_update_buttons(self):
        running = self._sw_start is not None
        self.sw_go.setText("Pause" if running else ("Resume" if self._sw_acc else "Start"))
        self.sw_lap.setEnabled(running)
        self.sw_reset.setEnabled(running or self._sw_acc > 0)

    def hideEvent(self, e):
        self._sw_timer.stop()
        super().hideEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        if self._sw_start is not None:
            self._sw_timer.start()
        self._sw_tick()
