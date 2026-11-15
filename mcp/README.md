# S.A Labs MCP server

Gives Claude, Cursor, Windsurf and any other MCP app five tools:

| Tool | What it does |
|------|--------------|
| `scrape_url` | Reads a web page and returns clean Markdown. JavaScript pages are rendered. |
| `text_to_speech` | Turns text into natural speech and saves an MP3 (or WAV/Opus/AAC/FLAC) on your computer. |
| `list_voices` | Lists the 41 voices in English (US/UK), Spanish, French, Hindi, Italian and Portuguese. |
| `transcribe` | Turns an audio/video file (or a direct link) into text and saves `.srt` + `.vtt` subtitles. |
| `check_balance` | Shows your remaining credits. |

You need an S.A Labs API key from your dashboard. Sign-up includes free credits.

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) (one command to install).

### Claude Desktop
Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "salabs": {
      "command": "uvx",
      "args": ["salabs-mcp"],
      "env": { "SALABS_API_KEY": "sa_live_your_key_here" }
    }
  }
}
```
Restart Claude Desktop. Then try: *"Read https://example.com and summarise it"*, or *"Make an MP3 of this paragraph in a British male voice"*.

### Claude Code
```bash
claude mcp add salabs --env SALABS_API_KEY=sa_live_your_key_here -- uvx salabs-mcp
```

### Cursor
Settings → MCP → Add new global MCP server, and paste the same `mcpServers` block as for Claude Desktop.

## Settings (environment variables)

| Variable | Default | |
|----------|---------|--|
| `SALABS_API_KEY` | (required) | Your key from the dashboard |
| `SALABS_BASE_URL` | the S.A Labs API | Change only if you run your own server |
| `SALABS_OUTPUT_DIR` | `~/Downloads/salabs` | Where audio files are saved. Subtitles are saved next to the source file. |

## Prices
Scrape 10 credits/page · Speech 80 credits per 1,000 characters · Transcription 15 (fast) or 20 (accurate) credits per minute. 10,000 credits = $1. Failed calls are refunded automatically.

## Develop
```bash
uv sync
uv run pytest                                         # unit tests
SALABS_LIVE_KEY=sa_live_... uv run pytest tests/test_live.py -s   # against a running API
```

MIT licensed.
