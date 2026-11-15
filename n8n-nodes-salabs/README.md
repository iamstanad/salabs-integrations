# n8n-nodes-salabs

S.A Labs for [n8n](https://n8n.io): cheap, simple AI tools in one node.

| Resource | Operation | What it does | Price |
|----------|-----------|--------------|-------|
| Web Page | Scrape | Any URL → clean Markdown, text, HTML, links and metadata. JavaScript pages are rendered automatically. | 10 credits/page |
| Speech | Generate | Text → MP3/WAV/Opus/AAC/FLAC (binary file or download link). 41 voices in 7 languages. | 80 credits / 1,000 chars |
| Speech | List Voices | All available voices | free |
| Transcription | Transcribe | Audio/video (binary file or link) → text, timestamps, SRT and VTT subtitles | 15–20 credits/min |
| Account | Get Balance | Credits left and this month's spend | free |

10,000 credits = $1. Failed calls are refunded automatically. The node also works as a **tool for the AI Agent node**.

## Install
In n8n: **Settings → Community nodes → Install**, enter `n8n-nodes-salabs`, and accept the risk prompt.

## Credentials
1. Sign in to the S.A Labs dashboard and click **Create API key**.
2. In n8n, open any S.A Labs node → Credential → **Create new** → paste the key (`sa_live_…`).
3. Leave **Base URL** as it is unless you run your own S.A Labs server.

## Templates
Ready-made workflows (import with **⋯ → Import from file**):
1. Video or audio → transcript → blog post
2. List of URLs → scrape → AI summary → Google Sheets
3. Script → voiceover MP3 (form)
4. Podcast RSS → transcript + SRT/VTT subtitles → Google Drive
5. Competitor website monitor → daily AI summary email
6. AI agent that can read web pages, make audio and transcribe

## Notes
- YouTube links aren't supported for transcription. Use a direct media link or upload the file.
- Generated files stay downloadable for 24 hours.

## Develop
```bash
npm install
npm run build
npm run lint
```

MIT licensed.
