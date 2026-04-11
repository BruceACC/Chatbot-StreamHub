"""
spam_engine.py
Controls timing and dispatch of messages to all active BotWorkers.

Modes:
  - simultaneous: all bots send at the same time
  - deferred:     bots send every N seconds, each staggered by index * offset
  - grouped:      bots divided into groups of size G, each group sends together
                  with N seconds between groups
"""

import threading
import time
import logging
import random
from dataclasses import dataclass, field
from enum import Enum

from core.bot_worker import BotWorker
from core.message_pool import MessagePool

logger = logging.getLogger(__name__)


class SpamMode(str, Enum):
    SIMULTANEOUS = "simultaneous"
    DEFERRED = "deferred"
    GROUPED = "grouped"


@dataclass
class SpamConfig:
    mode: SpamMode = SpamMode.SIMULTANEOUS
    delay: float = 3.0        # compatibility alias (same as delay_max)
    delay_min: float = 3.0    # minimum seconds between sends / groups
    delay_max: float = 3.0    # maximum seconds between sends / groups
    group_size: int = 2       # bots per group (grouped mode)
    random_messages: bool = False
    loop: bool = True          # keep repeating until stopped


class SpamEngine:
    def __init__(self):
        self._workers: list[BotWorker] = []
        self._pool: MessagePool = MessagePool()
        self._config: SpamConfig = SpamConfig()
        self._thread: threading.Thread | None = None
        self._running = False
        self.on_log: callable = None

    def configure(self, workers: list[BotWorker], pool: MessagePool, config: SpamConfig):
        self._workers = workers
        self._pool = pool
        self._config = config

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        # Wait briefly for thread to finish naturally
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _log(self, msg: str):
        logger.info(f"[SpamEngine] {msg}")
        if self.on_log:
            self.on_log("SpamEngine", msg)

    def _get_message(self, account_index: int) -> str:
        return self._pool.get_message(account_index, self._config.random_messages)

    def _active_workers(self, shuffle: bool = False) -> list[BotWorker]:
        active = [w for w in self._workers if w.status in ("ready", "sending")]
        if shuffle:
            random.shuffle(active)
        return active

    def _get_delay_range(self) -> tuple[float, float]:
        # Keep backward compatibility with configs that only provide `delay`.
        delay_min = float(getattr(self._config, "delay_min", self._config.delay))
        delay_max = float(getattr(self._config, "delay_max", self._config.delay))
        low = max(0.5, min(delay_min, delay_max))
        high = max(0.5, max(delay_min, delay_max))
        return low, high

    def _pick_delay(self) -> float:
        low, high = self._get_delay_range()
        if abs(high - low) < 1e-9:
            return low

        low_i = int(low)
        high_i = int(high)
        if abs(low - low_i) < 1e-9 and abs(high - high_i) < 1e-9:
            return float(random.randint(low_i, high_i))

        return random.uniform(low, high)

    def _send_all_simultaneous(self):
        """Send to every worker at the same time."""
        active = self._active_workers()
        for i, worker in enumerate(active):
            msg = self._get_message(i)
            if msg:
                worker.send_message(msg)
        self._log(f"Simultaneous: sent to {len(active)} workers.")

    def _send_deferred(self):
        """Send to workers one by one, waiting the configured delay between sends."""
        active = self._active_workers()

        for i, worker in enumerate(active):
            if not self._running:
                break

            msg = self._get_message(i)
            if msg:
                worker.send_message(msg)

            if i < len(active) - 1:
                self._sleep_interruptible(self._pick_delay())

        low, high = self._get_delay_range()
        self._log(f"Deferred: sent {len(active)} workers with random delay {low:.1f}s-{high:.1f}s.")

    def _send_grouped(self):
        """Split workers into groups of size G; each group sends then waits N seconds."""
        active = self._active_workers(shuffle=True)
        g = max(1, self._config.group_size)
        groups = [active[i:i + g] for i in range(0, len(active), g)]

        for gi, group in enumerate(groups):
            if not self._running:
                break

            for j, worker in enumerate(group):
                msg = self._get_message(gi * g + j)
                if msg:
                    worker.send_message(msg)

            self._log(f"Grouped: sent group {gi + 1}/{len(groups)} ({len(group)} workers).")

            if gi < len(groups) - 1:
                self._sleep_interruptible(self._pick_delay())

    def _run(self):
        mode = self._config.mode
        self._log(f"Starting spam engine — mode: {mode}")

        # Give workers time to start
        time.sleep(3)

        while self._running:
            if not self._pool.has_messages():
                time.sleep(1)
                continue

            if mode == SpamMode.SIMULTANEOUS:
                self._send_all_simultaneous()
                if self._config.loop:
                    self._sleep_interruptible(self._pick_delay())
                else:
                    break

            elif mode == SpamMode.DEFERRED:
                self._send_deferred()
                if self._config.loop:
                    self._sleep_interruptible(self._pick_delay())
                else:
                    break

            elif mode == SpamMode.GROUPED:
                self._send_grouped()
                if self._config.loop:
                    # Wait long enough for all groups to finish + random delay estimate
                    g = max(1, self._config.group_size)
                    active = len([w for w in self._workers if w.status in ("ready","sending")])
                    n_groups = max(1, -(-active // g))  # ceiling division
                    total_wait = n_groups * self._pick_delay()
                    self._sleep_interruptible(total_wait)
                else:
                    break

        self._log("Spam engine stopped.")

    def _sleep_interruptible(self, seconds: float):
        """Sleep in small chunks so we can react to stop() quickly."""
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(0.2)
