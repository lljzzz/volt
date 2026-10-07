import threading
import time

from pynput.mouse import Controller

INITIAL_DELAY = 0.26
INTERVAL = 0.02


class HoldGlider:
    def __init__(self, interval=INTERVAL):
        self._lock = threading.Lock()
        self._active: dict[tuple[int, int], object] = {}
        self._alive = False
        self._hold_started = 0.0
        self._interval = interval

    def start_hold(self, dx: int, dy: int, payload=None):
        with self._lock:
            if not self._active:
                self._hold_started = time.monotonic()
            fresh = (dx, dy) not in self._active
            self._active[(dx, dy)] = payload
            spawn = not self._alive
            self._alive = True
        if fresh:
            self._apply([((dx, dy), payload)])
        if spawn:
            threading.Thread(target=self._loop, daemon=True,
                             name="volt-glide").start()

    def stop_hold(self, dx: int, dy: int):
        with self._lock:
            self._active.pop((dx, dy), None)

    def stop_all(self):
        with self._lock:
            self._active.clear()

    def _loop(self):
        while True:
            with self._lock:
                if not self._active:
                    self._alive = False
                    return
                items = list(self._active.items())
                gliding = time.monotonic() - self._hold_started >= INITIAL_DELAY
            if gliding:
                self._apply(items)
            time.sleep(self._interval)

    def _apply(self, items):
        raise NotImplementedError


class NudgeEngine(HoldGlider):
    def __init__(self):
        super().__init__(INTERVAL)
        self._mouse = Controller()
        self.move_count = 0

    def _apply(self, items):
        mx = my = 0
        for (dx, dy), step_fn in items:
            step = self._step(step_fn)
            mx += dx * step
            my += dy * step
        if mx or my:
            try:
                self._mouse.move(mx, my)
                self.move_count += 1
            except Exception:
                pass

    @staticmethod
    def _step(step_fn) -> int:
        try:
            return max(1, int(step_fn()))
        except Exception:
            return 1

    def jump(self, x, y):
        try:
            self._mouse.position = (int(x), int(y))
            self.move_count += 1
        except Exception:
            pass

    def position(self) -> tuple[int, int]:
        x, y = self._mouse.position
        return int(x), int(y)
