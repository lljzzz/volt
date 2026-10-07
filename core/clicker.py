import random
import threading
import time

from pynput.mouse import Button, Controller

from . import hires, platform

_BUTTONS = {"left": Button.left, "middle": Button.middle, "right": Button.right}

_TICK_INTERVAL = 0.1


class ClickerEngine:
    def __init__(self):
        self._mouse = Controller()
        self._lock = threading.Lock()
        self._emit_lock = threading.Lock()
        self._stop = threading.Event()
        self._gen = 0
        self._running = False
        self._emitted_state = None
        self.cfg: dict = {}
        self.click_count = 0
        self.session_clicks = 0
        self._started_at = 0.0
        self._last_tick = 0.0
        self._shake = (0, 0)
        self._bl_raw = None
        self._bl: list[str] = []

        self.on_state_change = None
        self.on_tick = None
        self.on_limit_reached = None
        self.on_failsafe = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self, cfg: dict):
        with self._lock:
            if self._running:
                return
            self._gen += 1
            gen = self._gen
            self._stop = stop = threading.Event()
            self.cfg = cfg
            self.click_count = 0
            self._started_at = time.perf_counter()
            self._last_tick = 0.0
            self._shake = (0, 0)
            self._running = True
        threading.Thread(target=self._loop, args=(gen, stop), daemon=True,
                         name="volt-clicker").start()
        self._emit_state()

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._stop.set()
            self._running = False
        self._emit_state()

    def toggle(self, cfg: dict):
        if self._running:
            self.stop()
        else:
            self.start(cfg)

    def _emit_state(self):
        with self._emit_lock:
            r = self._running
            if r == self._emitted_state:
                return
            self._emitted_state = r
            if self.on_state_change:
                self.on_state_change(r)

    def _emit_tick(self, force=False):
        if not self.on_tick:
            return
        now = time.perf_counter()
        if force or (now - self._last_tick) >= _TICK_INTERVAL:
            self._last_tick = now
            self.on_tick(self.click_count)

    @staticmethod
    def _base_interval(cfg) -> float:
        if cfg.get("mode") == "delay":
            ms = max(1, int(cfg.get("delay_ms", 40)))
            return ms / 1000.0
        cps = max(float(cfg.get("cps", 1)), 0.0001)
        unit = cfg.get("unit", "second")
        if unit == "minute":
            cps /= 60.0
        elif unit == "hour":
            cps /= 3600.0
        return 1.0 / cps

    def _limit_hit(self, cfg) -> bool:
        if not cfg.get("limit_enabled"):
            return False
        value = int(cfg.get("limit_value", 0))
        if cfg.get("limit_type") == "time":
            return (time.perf_counter() - self._started_at) >= max(1, value)
        return self.click_count >= value

    def _blocklist(self, cfg) -> list[str]:
        raw = str(cfg.get("window_blocklist", ""))
        if raw != self._bl_raw:
            self._bl_raw = raw
            self._bl = [t.strip().lower() for t in raw.split(",") if t.strip()]
        return self._bl

    def _loop(self, gen: int, stop: threading.Event):
        hires.acquire()
        held: list = []
        reason = None
        start_hwnd = None
        try:
            while not stop.is_set():
                cfg = self.cfg
                interval = self._base_interval(cfg)

                if cfg.get("speed_variation"):
                    v = cfg.get("speed_variation_pct", 0) / 100.0
                    interval *= random.uniform(max(0.05, 1 - v), 1 + v)

                if platform.available() and self._window_blocked(cfg):
                    if self._limit_hit(cfg):
                        reason = "limit"
                        break
                    self._sleep(0.05, stop)
                    continue

                if cfg.get("stop_on_focus_change") and platform.available():
                    hwnd = platform.foreground_handle()
                    if start_hwnd is None:
                        start_hwnd = hwnd
                    elif hwnd and hwnd != start_hwnd:
                        reason = "focus"
                        break

                self._do_action(cfg, interval, stop, held)
                self._emit_tick()

                if self._limit_hit(cfg):
                    reason = "limit"
                    break

                self._sleep(interval, stop)
        except Exception as e:
            print(f"[clicker] loop error: {e}")
        finally:
            for btn in held:
                try:
                    self._mouse.release(btn)
                except Exception:
                    pass
            self._undo_shake()
            hires.release()
            with self._lock:
                mine = self._gen == gen
                if mine and self._running:
                    self._running = False
            if mine:
                self._emit_tick(force=True)
                self._emit_state()
                if reason == "limit" and self.on_limit_reached:
                    self.on_limit_reached()
                elif reason == "focus" and self.on_failsafe:
                    self.on_failsafe("focus changed")

    def _window_blocked(self, cfg) -> bool:
        blocklist = self._blocklist(cfg)
        lock_on = cfg.get("window_lock_enabled")
        if not blocklist and not lock_on:
            return False
        title = platform.foreground_title().lower()
        if blocklist:
            proc = platform.foreground_process()
            if any(b in title or (proc and b in proc) for b in blocklist):
                return True
        if lock_on:
            target = (cfg.get("window_lock_title") or "").lower()
            if target and target not in title:
                return True
        return False

    def _do_action(self, cfg, interval: float, stop, held: list):
        pts = cfg.get("sequence_points") or []
        if cfg.get("sequence_enabled") and pts:
            n = self._do_sequence(cfg, list(pts), stop, held)
        else:
            self._do_click(cfg, interval, held)
            n = 1
        self.click_count += n
        self.session_clicks += n

    def _do_sequence(self, cfg, pts, stop, held) -> int:
        btn = _BUTTONS.get(cfg.get("mouse_button", "left"), Button.left)
        delay = cfg.get("sequence_point_delay_ms", 50) / 1000.0
        n = len(pts)
        clicks = 0
        for i, pt in enumerate(pts):
            if stop.is_set():
                break
            self._mouse.position = (int(pt["x"]), int(pt["y"]))
            incoming_drag = i > 0 and pt.get("drag", False) and btn in held
            if not incoming_drag:
                self._mouse.press(btn)
                held.append(btn)
                clicks += 1
            next_drag = (i + 1 < n) and pts[i + 1].get("drag", False)
            if not next_drag:
                self._mouse.release(btn)
                held.remove(btn)
            if delay:
                self._sleep(delay, stop)
        return clicks

    def _do_click(self, cfg, interval: float, held: list):
        btn = _BUTTONS.get(cfg.get("mouse_button", "left"), Button.left)

        if cfg.get("mouse_shake"):
            amt = max(0, int(cfg.get("mouse_shake_px", 2)))
            nx, ny = random.randint(-amt, amt), random.randint(-amt, amt)
            ox, oy = self._shake
            self._mouse.move(nx - ox, ny - oy)
            self._shake = (nx, ny)
        else:
            self._undo_shake()

        hold = self._hold_time(cfg, interval)
        clicks = 2 if cfg.get("double_click") else 1
        for i in range(clicks):
            self._mouse.press(btn)
            held.append(btn)
            if hold:
                time.sleep(hold)
            self._mouse.release(btn)
            held.remove(btn)
            if clicks == 2 and i == 0:
                time.sleep(cfg.get("double_click_ms", 38) / 1000.0)

    def _undo_shake(self):
        ox, oy = self._shake
        if ox or oy:
            try:
                self._mouse.move(-ox, -oy)
            except Exception:
                pass
            self._shake = (0, 0)

    @staticmethod
    def _hold_time(cfg, interval: float) -> float:
        pct = max(0, min(100, int(cfg.get("click_duration", 0)))) / 100.0
        return min(pct * 0.05, interval * 0.4)

    @staticmethod
    def _sleep(interval: float, stop: threading.Event):
        end = time.perf_counter() + interval
        while not stop.is_set():
            remaining = end - time.perf_counter()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.02))
