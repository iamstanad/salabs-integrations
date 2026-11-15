# ruff: noqa: E501  (long template strings are clearer unwrapped)
"""Generates the ready-made n8n templates (JSON files you import into n8n).

Run: python3 integrations/n8n-templates/build_templates.py
Templates target n8n 2.x with the n8n-nodes-salabs community node installed.
"""

import json
import uuid
from pathlib import Path

HERE = Path(__file__).parent
SA = "n8n-nodes-salabs.saLabs"
GEMINI = "@n8n/n8n-nodes-langchain.lmChatGoogleGemini"


def nid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "salabs/" + name))


class WF:
    def __init__(self, name: str):
        self.name = name
        self.nodes: list[dict] = []
        self.conns: dict = {}
        self.x = 0

    def add(self, name, type_, ver, params=None, pos=None, **extra):
        if pos is None:
            pos = [self.x, 300]
            self.x += 260
        node = {
            "id": nid(self.name + name),
            "name": name,
            "type": type_,
            "typeVersion": ver,
            "position": pos,
            "parameters": params or {},
            **extra,
        }
        if type_.endswith(("formTrigger", "chatTrigger")):
            node["webhookId"] = nid(self.name + name + "/webhook")
        self.nodes.append(node)
        return name

    def link(self, a, b, kind="main"):
        self.conns.setdefault(a, {}).setdefault(kind, [[]])[0].append(
            {"node": b, "type": kind, "index": 0}
        )

    def chain(self, *names):
        for a, b in zip(names, names[1:], strict=False):
            self.link(a, b)

    def note(self, text, pos, w=420, h=260):
        self.add(
            f"Note {len(self.nodes)}",
            "n8n-nodes-base.stickyNote",
            1,
            {"content": text, "width": w, "height": h},
            pos=pos,
        )

    def dump(self, filename, description):
        data = {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.conns,
            "settings": {"executionOrder": "v1"},
            "pinData": {},
            "meta": {"templateCredsSetupCompleted": False, "description": description},
        }
        (HERE / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def gemini(wf: WF, name: str, target: str, pos):
    wf.add(name, GEMINI, 1.2, {"modelName": "models/gemini-2.5-flash", "options": {}}, pos=pos)
    wf.link(name, target, "ai_languageModel")


def llm(wf: WF, name: str, prompt: str):
    return wf.add(
        name,
        "@n8n/n8n-nodes-langchain.chainLlm",
        1.9,
        {"promptType": "define", "text": prompt, "batching": {}},
    )


SETUP = (
    "## Setup (2 minutes)\n"
    "1. Install the **S.A Labs** node: Settings → Community nodes → `n8n-nodes-salabs`.\n"
    "2. Open each **S.A Labs** node → Credential → *Create new* → paste your API key "
    "from the S.A Labs dashboard.\n"
)
GEMINI_SETUP = (
    "3. The AI step uses **Google Gemini** (free API key from aistudio.google.com). "
    "You can swap it for OpenAI, Claude or any other chat model.\n"
)


# ---- 1. Video/audio → transcript → blog post ---------------------------------------


def t1():
    wf = WF("S.A Labs: Video or audio → transcript → blog post")
    form = wf.add(
        "Upload video or audio",
        "n8n-nodes-base.formTrigger",
        2.5,
        {
            "formTitle": "Turn a video into a blog post",
            "formDescription": "Upload a video or audio file. You'll get a ready-to-edit blog post.",
            "formFields": {
                "values": [
                    {
                        "fieldLabel": "Video or audio file",
                        "fieldName": "media",
                        "fieldType": "file",
                        "multipleFiles": False,
                        "acceptFileTypes": ".mp4,.mov,.mkv,.webm,.mp3,.wav,.m4a,.aac,.ogg",
                        "requiredField": True,
                    },
                    {
                        "fieldLabel": "Target keyword (optional)",
                        "fieldName": "keyword",
                        "placeholder": "e.g. cinematic lighting tips",
                    },
                ]
            },
            "responseMode": "lastNode",
            "options": {},
        },
    )
    tr = wf.add(
        "Transcribe",
        SA,
        1,
        {
            "resource": "transcription",
            "operation": "transcribe",
            "source": "binary",
            "binaryPropertyName": "media",
            "model": "accurate",
            "transcribeOptions": {},
        },
    )
    post = llm(
        wf,
        "Write blog post",
        "=Write an engaging, well-structured blog post (Markdown, with a title, intro, "
        "H2 sections and a short conclusion) based on this transcript. Keep the speaker's "
        "ideas and voice; remove filler words.\n"
        "{{ $('Upload video or audio').item.json.keyword ? 'Target SEO keyword: ' + "
        "$('Upload video or audio').item.json.keyword : '' }}\n\nTranscript:\n{{ $json.text }}",
    )
    gemini(wf, "Gemini", post, [wf.x - 260, 520])
    done = wf.add(
        "Show the blog post",
        "n8n-nodes-base.form",
        2.5,
        {"operation": "completion", "respondWith": "showText", "responseText": "={{ $json.text }}"},
    )
    wf.chain(form, tr, post, done)
    wf.note(
        "# Video → blog post\nUpload a video/podcast in the form. S.A Labs transcribes it "
        "(20 credits/min), then the AI writes a blog post.\n\n"
        + SETUP
        + GEMINI_SETUP
        + "4. Click **Test workflow**, upload a file, wait for the post.",
        [-40, -60],
        560,
        320,
    )
    wf.dump(
        "01-video-to-blog-post.json",
        "Upload a video or audio file in a form, transcribe it with S.A Labs and get an AI-written blog post.",
    )


# ---- 2. URL list → scrape → AI summary → Google Sheet --------------------------------


def t2():
    wf = WF("S.A Labs: Scrape a list of URLs → AI summary → Google Sheets")
    start = wf.add("Start", "n8n-nodes-base.manualTrigger", 1)
    urls = wf.add(
        "URLs to scrape",
        "n8n-nodes-base.set",
        3.4,
        {
            "assignments": {
                "assignments": [
                    {
                        "id": nid("urls"),
                        "name": "url",
                        "type": "array",
                        "value": '["https://example.com", "https://www.iana.org/help/example-domains"]',
                    }
                ]
            },
            "options": {},
        },
    )
    split = wf.add(
        "One item per URL",
        "n8n-nodes-base.splitOut",
        1.1,
        {"fieldToSplitOut": "url", "options": {}},
    )
    scrape = wf.add(
        "Scrape page",
        SA,
        1,
        {
            "resource": "web",
            "operation": "scrape",
            "url": "={{ $json.url }}",
            "formats": ["markdown"],
            "scrapeOptions": {"onlyMainContent": True},
        },
    )
    summ = llm(
        wf,
        "Summarise",
        "=Summarise this web page in 3 short bullet points for a busy reader. Plain text, no intro.\n\n"
        "Title: {{ $json.metadata.title }}\n\n{{ $json.markdown.slice(0, 20000) }}",
    )
    gemini(wf, "Gemini", summ, [wf.x - 260, 520])
    row = wf.add(
        "Make the row",
        "n8n-nodes-base.set",
        3.4,
        {
            "assignments": {
                "assignments": [
                    {
                        "id": nid("r1"),
                        "name": "URL",
                        "type": "string",
                        "value": "={{ $('Scrape page').item.json.metadata.url }}",
                    },
                    {
                        "id": nid("r2"),
                        "name": "Title",
                        "type": "string",
                        "value": "={{ $('Scrape page').item.json.metadata.title }}",
                    },
                    {
                        "id": nid("r3"),
                        "name": "Summary",
                        "type": "string",
                        "value": "={{ $json.text }}",
                    },
                    {
                        "id": nid("r4"),
                        "name": "Scraped at",
                        "type": "string",
                        "value": "={{ $now.toISO() }}",
                    },
                ]
            },
            "options": {},
        },
    )
    sheet = wf.add(
        "Add to Google Sheet",
        "n8n-nodes-base.googleSheets",
        4.7,
        {
            "operation": "append",
            "documentId": {"__rl": True, "mode": "url", "value": ""},
            "sheetName": {"__rl": True, "mode": "name", "value": "Sheet1"},
            "columns": {
                "mappingMode": "autoMapInputData",
                "value": {},
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
    )
    wf.chain(start, urls, split, scrape, summ, row, sheet)
    wf.note(
        "# URLs → summaries → Google Sheet\nPut your URLs in **URLs to scrape**. Each page is "
        "scraped to Markdown (10 credits/page), summarised by AI, and added as a row.\n\n"
        + SETUP
        + GEMINI_SETUP
        + "4. Make a Google Sheet with headers **URL, Title, Summary, Scraped at** and paste its link "
        "into **Add to Google Sheet**.",
        [-40, -60],
        560,
        340,
    )
    wf.dump(
        "02-urls-to-ai-summary-google-sheet.json",
        "Scrape a list of web pages to Markdown, summarise each with AI and save them to Google Sheets.",
    )


# ---- 3. Text → voiceover --------------------------------------------------------------


VOICES = [
    "af_heart",
    "am_michael",
    "bf_emma",
    "bm_george",
    "af_bella",
    "am_adam",
    "ef_dora",
    "ff_siwis",
]


def t3():
    wf = WF("S.A Labs: Script → voiceover for Reels, TikTok and YouTube")
    form = wf.add(
        "Voiceover form",
        "n8n-nodes-base.formTrigger",
        2.5,
        {
            "formTitle": "Make a voiceover",
            "formDescription": "Paste your script, pick a voice, get an MP3.",
            "formFields": {
                "values": [
                    {
                        "fieldLabel": "Script",
                        "fieldName": "script",
                        "fieldType": "textarea",
                        "requiredField": True,
                    },
                    {
                        "fieldLabel": "Voice",
                        "fieldName": "voice",
                        "fieldType": "dropdown",
                        "fieldOptions": {"values": [{"option": v} for v in VOICES]},
                        "requiredField": True,
                    },
                    {
                        "fieldLabel": "Speed",
                        "fieldName": "speed",
                        "fieldType": "dropdown",
                        "fieldOptions": {
                            "values": [{"option": s} for s in ["1.0", "1.1", "1.2", "0.9"]]
                        },
                    },
                ]
            },
            "responseMode": "lastNode",
            "options": {},
        },
    )
    speak = wf.add(
        "Generate voiceover",
        SA,
        1,
        {
            "resource": "speech",
            "operation": "generate",
            "text": "={{ $json.script }}",
            "voice": "={{ $json.voice }}",
            "speechOutput": "binary",
            "binaryPropertyOutput": "data",
            "speechOptions": {
                "format": "mp3",
                "speed": "={{ Number($json.speed || 1) }}",
                "fileName": "voiceover.mp3",
            },
        },
    )
    done = wf.add(
        "Download the MP3",
        "n8n-nodes-base.form",
        2.5,
        {
            "operation": "completion",
            "respondWith": "returnBinary",
            "inputDataFieldName": "data",
            "completionTitle": "Your voiceover is ready",
            "completionMessage": "The download starts automatically.",
            "options": {},
        },
    )
    wf.chain(form, speak, done)
    wf.note(
        "# Script → voiceover\nPaste a script in the form and download a natural-sounding MP3 "
        "(80 credits per 1,000 characters, about $0.008).\n\n"
        + SETUP
        + "3. Click **Test workflow** and fill in the form.\n\nVoices: af_ = US female, am_ = US male, "
        "bf_/bm_ = UK, ef_ = Spanish, ff_ = French. See all with the *List Voices* operation.",
        [-40, -60],
        520,
        320,
    )
    wf.dump(
        "03-script-to-voiceover.json",
        "A form that turns a script into an MP3 voiceover with S.A Labs text-to-speech.",
    )


# ---- 4. Podcast → transcript + SRT ----------------------------------------------------


def t4():
    wf = WF("S.A Labs: Podcast episode → transcript + SRT/VTT subtitles")
    start = wf.add("Start", "n8n-nodes-base.manualTrigger", 1)
    rss = wf.add(
        "Read podcast feed",
        "n8n-nodes-base.rssFeedRead",
        1.2,
        {"url": "https://feeds.npr.org/510289/podcast.xml", "options": {}},
    )
    latest = wf.add("Latest episode", "n8n-nodes-base.limit", 1, {"maxItems": 1})
    tr = wf.add(
        "Transcribe episode",
        SA,
        1,
        {
            "resource": "transcription",
            "operation": "transcribe",
            "source": "url",
            "mediaUrl": "={{ $json.enclosure.url }}",
            "model": "fast",
            "transcribeOptions": {"attachSubtitles": "both"},
        },
    )
    drive = wf.add(
        "Save SRT to Google Drive",
        "n8n-nodes-base.googleDrive",
        3,
        {
            "resource": "file",
            "operation": "upload",
            "inputDataFieldName": "srt",
            "name": "={{ $('Latest episode').item.json.title }}.srt",
            "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
            "folderId": {
                "__rl": True,
                "mode": "list",
                "value": "root",
                "cachedResultName": "/ (Root folder)",
            },
            "options": {},
        },
    )
    wf.chain(start, rss, latest, tr, drive)
    wf.note(
        "# Podcast → transcript + subtitles\nReads a podcast RSS feed, transcribes the latest "
        "episode (15 credits/min with the *fast* model) and saves the SRT to Google Drive. "
        "The transcript text and VTT are in the **Transcribe episode** output too.\n\n"
        + SETUP
        + "3. Put your podcast's RSS feed in **Read podcast feed**.\n"
        "4. Connect Google Drive (or replace that node with Dropbox, Notion, email…).\n\n"
        "Tip: swap **Start** for a Schedule trigger to transcribe every new episode.",
        [-40, -60],
        560,
        340,
    )
    wf.dump(
        "04-podcast-to-transcript-and-subtitles.json",
        "Transcribe the latest podcast episode from an RSS feed and save SRT subtitles to Google Drive.",
    )


# ---- 5. Competitor website monitor → summary email ------------------------------------


COMPARE = r"""// Compares each page with the copy saved last time and outputs ONE item
// describing what changed (or nothing, which stops the workflow).
// Note: saved copies persist only when the workflow is *active* (not in test runs).
const store = $getWorkflowStaticData('global');
store.pages = store.pages || {};
const changes = [];
for (const item of $input.all()) {
  const url = item.json.metadata.url;
  const now = (item.json.markdown || '').slice(0, 15000);
  const before = store.pages[url];
  if (before === undefined) {
    changes.push(`### ${url}\n(First check: now watching this page.)\n\n${now.slice(0, 1500)}`);
  } else if (before !== now) {
    changes.push(`### ${url}\nBEFORE:\n${before.slice(0, 4000)}\n\nNOW:\n${now.slice(0, 4000)}`);
  }
  store.pages[url] = now;
}
if (changes.length === 0) return [];
return [{ json: { changedPages: changes.length, changes: changes.join('\n\n---\n\n') } }];
"""


def t5():
    wf = WF("S.A Labs: Competitor website monitor → daily summary email")
    sched = wf.add(
        "Every morning",
        "n8n-nodes-base.scheduleTrigger",
        1.2,
        {"rule": {"interval": [{"field": "days", "triggerAtHour": 8}]}},
    )
    urls = wf.add(
        "Pages to watch",
        "n8n-nodes-base.set",
        3.4,
        {
            "assignments": {
                "assignments": [
                    {
                        "id": nid("watch"),
                        "name": "url",
                        "type": "array",
                        "value": '["https://example.com", "https://www.iana.org/help/example-domains"]',
                    }
                ]
            },
            "options": {},
        },
    )
    split = wf.add(
        "One item per page",
        "n8n-nodes-base.splitOut",
        1.1,
        {"fieldToSplitOut": "url", "options": {}},
    )
    scrape = wf.add(
        "Scrape page",
        SA,
        1,
        {
            "resource": "web",
            "operation": "scrape",
            "url": "={{ $json.url }}",
            "formats": ["markdown"],
            "scrapeOptions": {},
        },
    )
    cmp_ = wf.add("Find changes", "n8n-nodes-base.code", 2, {"jsCode": COMPARE})
    summ = llm(
        wf,
        "Summarise changes",
        "=You monitor competitor websites. In a short email body (HTML, a few bullet points per site), "
        "explain what changed and why it might matter: prices, offers, products, messaging.\n\n"
        "{{ $json.changes }}",
    )
    gemini(wf, "Gemini", summ, [wf.x - 260, 520])
    mail = wf.add(
        "Email me",
        "n8n-nodes-base.gmail",
        2.2,
        {
            "sendTo": "you@example.com",
            "subject": "={{ 'Competitor watch: ' + $('Find changes').item.json.changedPages + ' page(s) changed' }}",
            "emailType": "html",
            "message": "={{ $json.text }}",
            "options": {},
        },
    )
    wf.chain(sched, urls, split, scrape, cmp_, summ, mail)
    wf.note(
        "# Competitor monitor\nEvery morning, scrapes the pages you list (10 credits/page), "
        "compares them with yesterday, and emails an AI summary only when something changed.\n\n"
        + SETUP
        + GEMINI_SETUP
        + "4. Put the pages in **Pages to watch**, your address in **Email me**, connect Gmail.\n"
        "5. **Activate** the workflow (the first run just saves a copy of each page).",
        [-40, -60],
        580,
        340,
    )
    wf.dump(
        "05-competitor-website-monitor.json",
        "Scrape competitor pages daily, detect changes and email an AI summary.",
    )


# ---- 6. AI Agent with S.A Labs tools ----------------------------------------------------


def t6():
    wf = WF("S.A Labs: AI research agent that can browse, speak and transcribe")
    chat = wf.add("Chat", "@n8n/n8n-nodes-langchain.chatTrigger", 1.3, {"options": {}})
    agent = wf.add(
        "AI Agent",
        "@n8n/n8n-nodes-langchain.agent",
        3.1,
        {
            "options": {
                "systemMessage": (
                    "You are a helpful research assistant. Use the 'Read web page' tool to read any URL "
                    "the user mentions or that you need, and cite the URL. Use 'Make audio' when the user "
                    "asks for audio or a voiceover and give them the audio link. Use 'Transcribe media link' "
                    "for direct links to audio/video files."
                )
            }
        },
    )
    wf.link(chat, agent)
    gemini(wf, "Gemini", agent, [300, 560])
    wf.add(
        "Memory",
        "@n8n/n8n-nodes-langchain.memoryBufferWindow",
        1.3,
        {},
        pos=[460, 560],
    )
    wf.link("Memory", agent, "ai_memory")
    tools = [
        (
            "Read web page",
            {
                "resource": "web",
                "operation": "scrape",
                "url": "={{ $fromAI('url', 'Full https address of the page to read', 'string') }}",
                "formats": ["markdown"],
                "scrapeOptions": {},
            },
        ),
        (
            "Make audio",
            {
                "resource": "speech",
                "operation": "generate",
                "text": "={{ $fromAI('text', 'The exact text to speak', 'string') }}",
                "voice": "af_heart",
                "speechOutput": "url",
                "speechOptions": {},
            },
        ),
        (
            "Transcribe media link",
            {
                "resource": "transcription",
                "operation": "transcribe",
                "source": "url",
                "mediaUrl": "={{ $fromAI('media_url', 'Direct link to an audio or video file', 'string') }}",
                "model": "fast",
                "transcribeOptions": {},
            },
        ),
    ]
    for i, (name, params) in enumerate(tools):
        wf.add(name, SA + "Tool", 1, params, pos=[620 + i * 180, 560])
        wf.link(name, agent, "ai_tool")
    wf.note(
        "# AI agent with S.A Labs tools\nChat with an agent that can read any web page, "
        "make audio and transcribe media links, all through S.A Labs.\n\n"
        + SETUP
        + GEMINI_SETUP
        + "4. Click **Open chat** and try: *“Read https://example.com and give me a 30-second "
        "audio summary.”*",
        [-40, -60],
        560,
        320,
    )
    wf.dump(
        "06-ai-agent-with-salabs-tools.json",
        "A chat AI agent that uses S.A Labs as tools to read web pages, make audio and transcribe media.",
    )


if __name__ == "__main__":
    for fn in (t1, t2, t3, t4, t5, t6):
        fn()
    print("templates written to", HERE)
