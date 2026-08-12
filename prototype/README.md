# NutraSmart — Chat-first Bot Frontend (wired to the LIVE backend)

A new chat-first UI that talks to the **existing production backend** (`api.nutrasmart.in`) —
real Google login, real presigned upload to the **regional** S3 bucket, real AgentCore/Bedrock
analysis, real chat. Full end-to-end cycle, region residency included.

## Run

```bash
cd prototype/client
npm install
npm run dev            # http://localhost:5173  (use 5173 — it's the OAuth/S3-CORS allowed origin)
```

Open **http://localhost:5173**, **Sign in with Google**, then:
- 📷 attach a food photo → it uploads to your region's bucket → the card shows the analysis
  **and a badge** ("stored & analyzed in <region>").
- Ask "am I low on any minerals?" / "how did I eat this week?" → real agent replies.
- 📊 "My stats" → real nutrition summary from your regional data.

The `.env` sets `VITE_API_URL=https://api.nutrasmart.in/api` and the Google client id.

## Full cycle
```
Google login (ID token)
  → POST /api/upload/presign        → presigned URL to the REGIONAL bucket
  → PUT image bytes → regional S3    (browser → S3 direct; region from viewer country)
  → POST /api/analyze {key}          → regional AgentCore runtime → Bedrock vision
  → nutrition card in chat
```

## Files
- `client/src/api.js` — live backend calls + `regionFromPresign()` (reads region from the URL).
- `client/src/App.jsx` — login gate, chat thread, image flow, region badge.
- `client/src/DashboardPanel.jsx` — stats from `/api/nutrition/summary`.
- `server/` — the earlier **mock** API; **no longer used** by this frontend (kept for reference).

## Note
If Google sign-in errors on localhost, `http://localhost:5173` must be an **Authorized
JavaScript origin** on the OAuth client (Google Cloud console). The S3 buckets already allow
`localhost:5173` for CORS `PUT`.
