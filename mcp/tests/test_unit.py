import json

import httpx
import pytest
from mcp import Client

from salabs_mcp import server


def _data(r):
    return json.loads(r.content[0].text)


@pytest.fixture
def api(monkeypatch, tmp_path):
    """Fake S.A Labs API."""
    monkeypatch.setenv("SALABS_API_KEY", "sa_live_test")
    monkeypatch.setenv("SALABS_BASE_URL", "http://fake")
    monkeypatch.setenv("SALABS_OUTPUT_DIR", str(tmp_path))
    calls = []
    jobs = {"n": 0}

    def handler(req: httpx.Request):
        calls.append((req.method, req.url.path, req.headers.get("authorization")))
        p = req.url.path
        if p == "/v1/account":
            return httpx.Response(
                200, json={"credits": 25000, "spent_this_month": 10, "monthly_cap": None}
            )
        if p == "/v1/scrape":
            body = json.loads(req.content)
            if "bad" in body["url"]:
                return httpx.Response(
                    403,
                    json={
                        "error": {
                            "code": "blocked_by_robots",
                            "message": "Blocked. You were not charged.",
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {"markdown": "x" * 100, "metadata": {"title": "T", "url": body["url"]}},
                },
            )
        if p == "/v1/tts":
            return httpx.Response(202, json={"id": "job_1", "status": "running"})
        if p == "/v1/jobs/job_1":
            jobs["n"] += 1
            if jobs["n"] < 2:
                return httpx.Response(200, json={"id": "job_1", "status": "running"})
            return httpx.Response(
                200,
                json={
                    "id": "job_1",
                    "status": "succeeded",
                    "credits_charged": 3,
                    "result": {
                        "audio_url": "http://fake/files/a.mp3",
                        "duration_seconds": 1.5,
                        "voice": "af_heart",
                    },
                },
            )
        if p == "/files/a.mp3":
            return httpx.Response(200, content=b"ID3fakeaudio")
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "nope"}})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        server.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )

    async def no_sleep(_):
        return None

    monkeypatch.setattr(server.asyncio, "sleep", no_sleep)
    return calls


async def test_balance_sends_key(api):
    async with Client(server.mcp) as c:
        d = _data(await c.call_tool("check_balance", {}))
    assert d["credits_in_usd"] == 2.5
    assert api[0][2] == "Bearer sa_live_test"


async def test_scrape_truncates_and_reports_errors(api):
    async with Client(server.mcp) as c:
        r = await c.call_tool("scrape_url", {"url": "https://ok.com", "max_chars": 10})
        assert "truncated to 10" in r.content[0].text
        r = await c.call_tool("scrape_url", {"url": "https://bad.com"})
        assert r.is_error and "blocked_by_robots" in r.content[0].text


async def test_tts_waits_for_job_and_saves(api, tmp_path):
    async with Client(server.mcp) as c:
        d = _data(await c.call_tool("text_to_speech", {"text": "Hi there", "filename": "greeting"}))
    assert d["saved_to"] == str(tmp_path / "greeting.mp3")
    assert (tmp_path / "greeting.mp3").read_bytes() == b"ID3fakeaudio"
    assert d["credits_charged"] == 3


async def test_missing_key(monkeypatch):
    monkeypatch.delenv("SALABS_API_KEY", raising=False)
    async with Client(server.mcp) as c:
        r = await c.call_tool("check_balance", {})
    assert r.is_error and "SALABS_API_KEY" in r.content[0].text
