"""Live test against a running S.A Labs API, over real stdio like Claude Desktop uses.

Run: SALABS_LIVE_KEY=sa_live_... uv run pytest tests/test_live.py -s
"""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

KEY = os.environ.get("SALABS_LIVE_KEY")
BASE = os.environ.get("SALABS_LIVE_BASE_URL", "http://localhost:8000")
VIDEO = Path(__file__).resolve().parents[3] / "samples" / "test_video.mp4"

pytestmark = pytest.mark.skipif(not KEY, reason="set SALABS_LIVE_KEY to run")


def _data(result):
    assert not result.is_error, result.content
    if result.structured_content is not None:
        sc = result.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    text = result.content[0].text
    try:
        return json.loads(text)
    except ValueError:
        if len(result.content) > 1:  # lists come back as one content item per entry
            return [json.loads(c.text) for c in result.content]
        return text


async def test_all_tools_over_stdio(tmp_path):
    video = tmp_path / "clip.mp4"
    shutil.copy(VIDEO, video)
    from_pypi = os.environ.get("SALABS_LIVE_FROM_PYPI")  # test the published package
    params = StdioServerParameters(
        command="uvx" if from_pypi else sys.executable,
        args=["--refresh", "salabs-mcp"] if from_pypi else ["-m", "salabs_mcp.server"],
        env={
            "SALABS_API_KEY": KEY,
            "SALABS_BASE_URL": BASE,
            "SALABS_OUTPUT_DIR": str(tmp_path / "out"),
            "PATH": os.environ["PATH"],
        },
    )
    async with Client(params, read_timeout_seconds=600) as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert names == {
            "scrape_url",
            "text_to_speech",
            "list_voices",
            "transcribe",
            "check_balance",
        }

        before = _data(await c.call_tool("check_balance", {}))["credits"]

        md = _data(await c.call_tool("scrape_url", {"url": "https://example.com"}))
        assert "Example Domain" in md

        voices = _data(await c.call_tool("list_voices", {"language": "en-gb"}))
        assert voices and all(v["language"] == "en-gb" for v in voices)

        tts = _data(await c.call_tool("text_to_speech", {"text": "Hello from the MCP test."}))
        assert Path(tts["saved_to"]).stat().st_size > 1000

        tr = _data(await c.call_tool("transcribe", {"source": str(video), "model": "fast"}))
        assert "cinematography" in tr["text"].lower()
        assert Path(tr["subtitles_saved_to"]["srt"]).read_text().startswith("1\n")

        bad = await c.call_tool("transcribe", {"source": "/nope/missing.mp3"})
        assert bad.is_error

        after = _data(await c.call_tool("check_balance", {}))["credits"]
        assert after < before
        print(
            json.dumps(
                {"tts": tts, "transcribe_text": tr["text"][:80], "spent": before - after}, indent=1
            )
        )
