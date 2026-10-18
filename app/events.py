"""Barra de eventos em memoria (pub/sub) usada pelo SSE da interface web.

Leve o suficiente para um Raspberry Pi 3 B+: nada de threads por cliente,
apenas um ``threading.Condition`` e um buffer circular com os ultimos
eventos (para que um navegador que acaba de conectar ja veja o estado).
"""
from __future__ import annotations

import itertools
import queue
import threading
import time
from typing import Any, Dict, List


class EventBus:
    def __init__(self, history: int = 64) -> None:
        self._cond = threading.Condition()
        self._seq = itertools.count(1)
        self._history: List[Dict[str, Any]] = []
        self._history_size = history
        self._subscribers: List["queue.Queue[Dict[str, Any]]"] = []

    def publish(self, kind: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        event = {
            "seq": next(self._seq),
            "ts": time.time(),
            "kind": kind,
            "data": payload or {},
        }
        with self._cond:
            self._history.append(event)
            if len(self._history) > self._history_size:
                del self._history[: len(self._history) - self._history_size]
            for sub in list(self._subscribers):
                try:
                    sub.put_nowait(event)
                except queue.Full:
                    pass
            self._cond.notify_all()
        return event

    def history(self, since: int = 0) -> List[Dict[str, Any]]:
        with self._cond:
            return [e for e in self._history if e["seq"] > since]

    def subscribe(self) -> "queue.Queue[Dict[str, Any]]":
        q: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=256)
        with self._cond:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[Dict[str, Any]]") -> None:
        with self._cond:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def wait(self, timeout: float) -> bool:
        with self._cond:
            return self._cond.wait(timeout)


bus = EventBus()
