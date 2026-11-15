# S.A Labs integrations

Official open-source integrations for **S.A Labs**: cheap, simple AI tools for your agents (web scraping to Markdown, text-to-speech, and audio/video transcription with subtitles).

| Folder | What it is | Install |
|--------|-----------|---------|
| [`mcp/`](mcp/) | MCP server for Claude Desktop, Claude Code, Cursor and other MCP apps | `uvx salabs-mcp` |
| [`n8n-nodes-salabs/`](n8n-nodes-salabs/) | n8n community node (also works as an AI Agent tool) | n8n → Settings → Community nodes → `n8n-nodes-salabs` |
| [`n8n-templates/`](n8n-templates/) | 6 ready-made n8n workflows | n8n → Import from file |

You need an S.A Labs API key. New accounts get free credits.

> Status: beta. The npm and PyPI packages are being published; until then, build from source (see each folder).

Pricing: scrape 10 credits/page · speech 80 credits per 1,000 characters · transcription 15–20 credits/minute (10,000 credits = $1). Failed calls are refunded automatically.

Questions or problems: open an issue, or email info@stanleyadio.com.

MIT licensed.
