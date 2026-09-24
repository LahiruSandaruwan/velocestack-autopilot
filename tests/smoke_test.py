"""Offline smoke test (no network, nothing is posted):  python tests/smoke_test.py"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

tmp = Path(tempfile.mkdtemp())
os.environ.update({
    "OFFLINE": "1", "DATA_DIR": str(tmp / "data"), "POSTS_DIR": str(tmp / "posts"), "DOCS_DIR": str(tmp / "docs"),
    "MODE": "auto", "GITHUB_REPOSITORY": "me/repo", "GITHUB_REF_NAME": "main",
    "FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "t", "IG_USER_ID": "2", "IG_REELS": "1",
    "PINTEREST_ACCESS_TOKEN": "p", "PINTEREST_BOARD_ID": "b",
    "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHAT_ID": "1", "TELEGRAM_CHANNEL_ID": "2",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
(tmp / "data").mkdir()
(tmp / "data" / "catalog.json").write_text(json.dumps([{
    "slug": "demo", "title": "Demo Bundle: 100 things", "short": "Demo Bundle", "description": "A demo product.",
    "image": "", "price": "7.0", "url": "https://example.com/products/demo"}]))

from autopilot import publish, render, run  # noqa: E402

calls = []


class R:
    status_code = 200
    ok = True

    def __init__(self, j=None):
        self._j = j or {"id": "123", "status_code": "FINISHED", "post_id": "p1"}

    def json(self):
        return self._j

    def raise_for_status(self):
        pass


def fake_post(url, **kw):
    calls.append(url.split("?")[0])
    return R()


def fake_get(url, **kw):
    return R()


with mock.patch("requests.post", fake_post), mock.patch("requests.get", fake_get), \
        mock.patch("time.sleep", lambda s: None), \
        mock.patch.object(publish, "telegram_send", lambda *a, **k: calls.append("telegram")):
    for i in range(14):
        run.cmd_generate()
        run.cmd_publish()

kinds = [h["type"] for h in json.loads((tmp / "data" / "state.json").read_text())["history"]]
assert kinds == run.config.PATTERN, kinds
assert any("/photos" in c for c in calls) and any("media_publish" in c for c in calls) and any("/pins" in c for c in calls)
assert (tmp / "docs" / "index.html").exists()
print("OK - 14 posts generated and 'published' against mocked APIs. calls:", len(calls))
