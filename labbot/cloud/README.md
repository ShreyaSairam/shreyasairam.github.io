# LabBot cloud parser (optional)

The LabBot page works fully on-device. This Worker adds an LLM parser: Gemini
reads the command and returns tool calls through function calling. The page
checks every call against the lab rules, and falls back to the on-device parser
if the Worker is slow (7 s), down or returns anything invalid.

## Deploy (Cloudflare Workers, free tier)

```bash
npm i -g wrangler
wrangler login
wrangler init labbot-llm --yes          # then replace src/index.js with worker.js
wrangler secret put GEMINI_API_KEY      # key from Google AI Studio
wrangler deploy
```

Then set `LLM_ENDPOINT` near the top of `labbot/index.html` to the Worker URL.
The badge above LabBot's reply switches to "cloud LLM · Gemini" when it is used.

## Safety choices

- Only the command text and sample states are sent. No personal data.
- The key stays in the Worker, never in the page.
- CORS only allows the portfolio origin.
- Output is filtered to a fixed schema (op, sample 1–6, known places) before the page sees it.
