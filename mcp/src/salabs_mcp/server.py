"""S.A Labs MCP server: scrape, text-to-speech and transcription tools for AI apps.

Configure with environment variables:
  SALABS_API_KEY     your key from the S.A Labs dashboard (required)
  SALABS_BASE_URL    API address (default: the public S.A Labs API)
  SALABS_OUTPUT_DIR  where audio/subtitle files are saved (default: ~/Downloads/salabs)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from salabs_mcp import __version__

# TODO(Phase 7): set to the real public URL once the domain is chosen.
DEFAULT_BASE_URL = "http://localhost:8000"

mcp = MCPServer(
    name="salabs",
    instructions=(
        "S.A Labs tools. Use scrape_url to read a web page as clean Markdown, "
        "text_to_speech to turn text into an audio file, transcribe to turn an audio/video "
        "file or link into text and subtitles, and check_balance to see remaining credits. "
        "Files are saved on the user's computer; mention the saved path in your answer."
    ),
)


# ---- HTTP client ---------------------------------------------------------------


def _config() -> tuple[str, str]:
    key = os.environ.get("SALABS_API_KEY", "").strip()
    if not key:
        raise ToolError(
            "SALABS_API_KEY is not set. Create a key in the S.A Labs dashboard and add it to "
            "this MCP server's environment settings."
        )
    base = os.environ.get("SALABS_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    return base, key


def output_dir() -> Path:
    d = Path(os.environ.get("SALABS_OUTPUT_DIR") or Path.home() / "Downloads" / "salabs")
    d = d.expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _client(timeout: float = 180) -> httpx.AsyncClient:
    base, key = _config()
    return httpx.AsyncClient(
        base_url=base,
        timeout=timeout,
        headers={"Authorization": f"Bearer {key}", "User-Agent": f"salabs-mcp/{__version__}"},
    )


def _raise_for(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    try:
        err = r.json()["error"]
        msg = f"{err.get('message')} ({err.get('code')})"
    except (ValueError, KeyError, TypeError, AttributeError):
        msg = f"HTTP {r.status_code}: {r.text[:200]}"
    raise ToolError(f"S.A Labs API error: {msg}")


async def _request(client: httpx.AsyncClient, method: str, url: str, **kw) -> httpx.Response:
    try:
        r = await client.request(method, url, **kw)
    except httpx.HTTPError as e:
        raise ToolError(f"Could not reach S.A Labs at {client.base_url}: {e}") from e
    _raise_for(r)
    return r


async def _wait_job(client: httpx.AsyncClient, job: dict, max_wait_s: float = 3600) -> dict:
    """Poll a job until it finishes."""
    delay, waited = 2.0, 0.0
    while job.get("status") not in ("succeeded", "failed"):
        if waited > max_wait_s:
            raise ToolError(f"Job {job.get('id')} is still running; check it later.")
        await asyncio.sleep(delay)
        waited += delay
        delay = min(delay * 1.5, 10)
        job = (await _request(client, "GET", f"/v1/jobs/{job['id']}")).json()
    if job["status"] == "failed":
        raise ToolError(f"The job failed: {job.get('error')}")
    return job


def _safe_name(text: str, fallback: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:40]
    return name or fallback


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    i = 2
    while True:
        p = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not p.exists():
            return p
        i += 1


# ---- tools ------------------------------------------------------------------


@mcp.tool()
async def scrape_url(
    url: str,
    only_main_content: bool = True,
    include_links: bool = False,
    max_chars: int = 40000,
) -> str:
    """Read a web page and return it as clean Markdown (JavaScript pages are rendered).

    Args:
        url: The page address, e.g. https://example.com/blog/post
        only_main_content: True drops menus, footers and sidebars.
        include_links: Also list every link found on the page.
        max_chars: Cut the Markdown to this many characters to keep answers short.
    """
    formats = ["markdown"] + (["links"] if include_links else [])
    async with _client(timeout=90) as c:
        r = await _request(
            c,
            "POST",
            "/v1/scrape",
            json={"url": url, "formats": formats, "onlyMainContent": only_main_content},
        )
    data = r.json()["data"]
    meta = data.get("metadata", {})
    md = data.get("markdown") or ""
    cut = len(md) > max_chars
    md = md[:max_chars]
    out = [f"# {meta.get('title', url)}", f"Source: {meta.get('url', url)}", "", md]
    if cut:
        out.append(f"\n[…truncated to {max_chars} characters]")
    if include_links and data.get("links"):
        out += ["", "## Links", *(f"- {link}" for link in data["links"][:300])]
    return "\n".join(out)


@mcp.tool()
async def text_to_speech(
    text: str,
    voice: str = "af_heart",
    speed: float = 1.0,
    format: Literal["mp3", "wav", "opus", "aac", "flac"] = "mp3",
    filename: str | None = None,
) -> dict:
    """Turn text into natural speech and save it as an audio file on this computer.

    Args:
        text: What to say (up to 100,000 characters).
        voice: Voice id, e.g. af_heart (US female), am_michael (US male), bf_emma (UK female),
            bm_george (UK male), ef_dora (Spanish), ff_siwis (French). See list_voices.
        speed: 0.5 (slow) to 2.0 (fast).
        format: Audio file type.
        filename: Optional file name (without folder). Saved in the S.A Labs output folder.
    """
    body = {"text": text, "voice": voice, "speed": speed, "format": format}
    async with _client(timeout=300) as c:
        if len(text) <= 4000:
            r = await _request(c, "POST", "/v1/tts", params={"output": "url"}, json=body)
            if r.status_code == 202:  # still generating: wait for the job
                job = await _wait_job(c, r.json())
                res, credits = job["result"], job.get("credits_charged")
            else:
                res = r.json()
                credits = res.get("credits_charged")
        else:
            job = (await _request(c, "POST", "/v1/tts/async", json=body)).json()
            job = await _wait_job(c, job)
            res, credits = job["result"], job.get("credits_charged")
        audio = await c.get(res["audio_url"])
        _raise_for(audio)
    name = filename or f"{_safe_name(text[:40], 'speech')}.{format}"
    if not name.endswith(f".{format}"):
        name += f".{format}"
    path = _unique(output_dir() / Path(name).name)
    path.write_bytes(audio.content)
    return {
        "saved_to": str(path),
        "duration_seconds": res.get("duration_seconds"),
        "voice": res.get("voice", voice),
        "download_url_valid_24h": res["audio_url"],
        "credits_charged": credits,
    }


@mcp.tool()
async def list_voices(language: str | None = None) -> list[dict]:
    """List the available text-to-speech voices.

    Args:
        language: Optional filter, e.g. "en-us", "en-gb", "es", "fr", "hi", "it", "pt-br".
    """
    async with _client(timeout=30) as c:
        voices = (await _request(c, "GET", "/v1/tts/voices")).json()["data"]
    if language:
        voices = [v for v in voices if v.get("language", "").lower().startswith(language.lower())]
    return [
        {k: v.get(k) for k in ("id", "name", "language", "gender") if v.get(k) is not None}
        for v in voices
    ]


@mcp.tool()
async def transcribe(
    source: str,
    model: Literal["fast", "accurate"] = "accurate",
    language: str | None = None,
    translate_to_english: bool = False,
    save_subtitles: bool = True,
) -> dict:
    """Transcribe an audio or video file to text, with SRT/VTT subtitles.

    Args:
        source: A file path on this computer (e.g. /Users/me/Movies/interview.mp4) or a
            direct https link to an audio/video file. YouTube links are not supported.
        model: "fast" (cheaper, quicker) or "accurate".
        language: Spoken language code like "en" or "fr". Leave empty to auto-detect.
        translate_to_english: Translate the speech to English.
        save_subtitles: Save .srt and .vtt files (next to a local file, else in the output folder).
    """
    opts = {"model": model, "wait": True, "translate": translate_to_english}
    if language:
        opts["language"] = language
    local = Path(source).expanduser()
    is_url = source.startswith(("http://", "https://"))
    if not is_url and not local.is_file():
        raise ToolError(f"File not found: {source}")
    async with _client(timeout=600) as c:
        if is_url:
            r = await _request(c, "POST", "/v1/transcribe", json={"url": source, **opts})
        else:
            with local.open("rb") as fh:
                r = await _request(
                    c,
                    "POST",
                    "/v1/transcribe",
                    files={"file": (local.name, fh)},
                    data={k: str(v).lower() if isinstance(v, bool) else v for k, v in opts.items()},
                )
        job = r.json()
        job = await _wait_job(c, job)
    res = job["result"]
    out: dict = {
        "text": res.get("text", ""),
        "language": res.get("language"),
        "duration_seconds": res.get("duration_seconds"),
        "credits_charged": job.get("credits_charged"),
    }
    if save_subtitles:
        folder = local.parent if not is_url else output_dir()
        stem = local.stem if not is_url else _safe_name(source.rsplit("/", 1)[-1], "transcript")
        saved = {}
        for ext in ("srt", "vtt"):
            if res.get(ext):
                p = _unique(folder / f"{stem}.{ext}")
                try:
                    p.write_text(res[ext], encoding="utf-8")
                except OSError:
                    p = _unique(output_dir() / f"{stem}.{ext}")
                    p.write_text(res[ext], encoding="utf-8")
                saved[ext] = str(p)
        out["subtitles_saved_to"] = saved
    return out


@mcp.tool()
async def check_balance() -> dict:
    """Show the remaining S.A Labs credits (10,000 credits = $1) and this month's spend."""
    async with _client(timeout=30) as c:
        a = (await _request(c, "GET", "/v1/account")).json()
    return {
        "credits": a["credits"],
        "credits_in_usd": round(a["credits"] / 10000, 2),
        "spent_this_month": a["spent_this_month"],
        "monthly_cap": a.get("monthly_cap"),
    }


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        print(f"salabs-mcp {__version__}")
        return
    logging.getLogger("httpx").setLevel(logging.WARNING)
    mcp.run()


if __name__ == "__main__":
    main()
