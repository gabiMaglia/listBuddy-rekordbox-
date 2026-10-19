"""SEC-10: el worker nunca emite una URL fuera de las releases del repo."""
from __future__ import annotations

import io
import json

import update_checker

_OK = "https://github.com/gabiMaglia/listbuddy/releases/tag/v9.0.0"


def _run_with_payload(monkeypatch, payload: dict) -> list[object]:
    monkeypatch.setattr(
        update_checker.urllib.request, "urlopen",
        lambda *a, **k: io.BytesIO(json.dumps(payload).encode()),
    )
    emitted: list[object] = []
    w = update_checker.UpdateCheckWorker("1.0.0")
    w.update_available.connect(emitted.append)
    w.run()
    return emitted


def test_malicious_url_falls_back_to_releases_page(monkeypatch) -> None:
    got = _run_with_payload(monkeypatch, {"tag_name": "v9.0.0", "html_url": "file:///etc/passwd"})
    assert [i.url for i in got] == [update_checker._RELEASES_PAGE_URL]


def test_valid_url_is_kept(monkeypatch) -> None:
    got = _run_with_payload(monkeypatch, {"tag_name": "v9.0.0", "html_url": _OK})
    assert [i.url for i in got] == [_OK]
