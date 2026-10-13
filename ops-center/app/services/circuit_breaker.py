from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CircuitState:
    failures: list[float] = field(default_factory=list)
    open_until: float = 0.0


class SlidingWindowCircuitBreaker:
    def __init__(self) -> None:
        self._state: dict[str, CircuitState] = {}

    def _bucket(self, key: str) -> CircuitState:
        if key not in self._state:
            self._state[key] = CircuitState()
        return self._state[key]

    def is_open(self, key: str, now: float | None = None) -> bool:
        t = now or time.time()
        state = self._bucket(key)
        return state.open_until > t

    def record_success(self, key: str) -> None:
        state = self._bucket(key)
        state.failures.clear()
        state.open_until = 0.0

    def record_failure(
        self,
        key: str,
        *,
        threshold: int,
        window_seconds: int,
        open_seconds: int,
        now: float | None = None,
    ) -> None:
        t = now or time.time()
        state = self._bucket(key)
        state.failures = [x for x in state.failures if x >= t - max(1, window_seconds)]
        state.failures.append(t)
        if len(state.failures) >= max(1, threshold):
            state.open_until = t + max(1, open_seconds)


CIRCUIT_BREAKER = SlidingWindowCircuitBreaker()
