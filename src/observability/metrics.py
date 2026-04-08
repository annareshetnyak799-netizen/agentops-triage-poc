from __future__ import annotations

from dataclasses import dataclass, field


LATENCY_BUCKETS_MS = (1000, 5000, 10000, 30000)


@dataclass(slots=True)
class MetricsRegistry:
    counters: dict[str, int] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def observe_latency(
        self,
        name: str,
        value_ms: int,
        buckets_ms: tuple[int, ...] = LATENCY_BUCKETS_MS,
    ) -> None:
        bounded_value = max(0, value_ms)
        self.increment(name, bounded_value)

        for bucket in buckets_ms:
            if bounded_value <= bucket:
                self.increment(f"{name}_bucket_le_{bucket}")

        self.increment(f"{name}_bucket_le_inf")

    def get(self, name: str) -> int:
        return self.counters.get(name, 0)

    def snapshot(self) -> dict[str, int]:
        return dict(self.counters)


metrics_registry = MetricsRegistry()
