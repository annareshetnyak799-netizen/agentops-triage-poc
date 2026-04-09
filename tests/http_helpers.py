from __future__ import annotations

from typing import Protocol


class ResponseLike(Protocol):
    headers: dict[str, str]
    text: str

    def json(self) -> dict[str, object]:
        ...


def unwrap_success(response: ResponseLike) -> dict[str, object]:
    payload = response.json()
    assert payload["status"] == "ok"
    assert "data" in payload
    assert "meta" in payload
    return payload["data"]


def parse_metrics_text(response: ResponseLike) -> dict[str, int]:
    """Parse Prometheus text-format metrics into a {name: value} dict.

    Skips comment lines (# HELP / # TYPE) as required by the format spec.
    """
    assert response.headers["content-type"].startswith("text/plain")
    metrics: dict[str, int] = {}

    for raw_line in response.text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, value = line.split(" ", maxsplit=1)
        metrics[name] = int(value)

    return metrics
