# 04 — Web client (`maitribot/client`)

Read-only review, 2026-10-26. Findings are referenced from the summary as `WEB-n`. Line numbers refer to the working
tree on `feature/w360-full-multiple-models` with the `feature/w360-full` merge staged. `node_modules/` is absent, so no
tooling was run.

## Architecture summary

The client is a Vite 5 + React 18 app with two HTML entrypoints: `index.html → src/main.jsx → App.jsx` (Google login
gate, chat thread, meal-photo flow, stats drawer) and `scan.html → src/senai_scan/scanMain.jsx → ScanPage.jsx` (Shen.AI
on-device vitals scan). The split exists because the SDK needs COOP/COEP cross-origin isolation, which breaks Google
Identity Services on the main document; isolation is per top-level page, so the scan got its own. All backend traffic
goes through `src/api.js`: a `req()` wrapper over `fetch` with an `AbortController` that adds
`Authorization: Bearer <Google ID token>` (read from `localStorage`) and an optional `X-Origin-Verify` header, calling
`/upload/presign`, `/analyze`, `/chat`, `/facescan/analyze`, `/nutrition/summary`, `/weekly-summary/generate`. Verified
against `backend/app/routes/{upload,analyze,chat,facescan,meals}.py` and `backend/app/auth.py`: paths, JSON bodies,
bearer auth and the `{detail}` error envelope match. The backend resolves the data region from
`CloudFront-Viewer-Country`/`X-User-Country` (`regions.py:40-42`), which the client never sends; the client instead
reverse-engineers the region from the presigned S3 host for display. Images/videos are `PUT` straight to the presigned
regional S3 URL. The Shen.AI SDK is a real npm dependency (`@shenai/sdk@3.1.2`), copied into `public/shenai-sdk` at
dev/build time, loaded at runtime via dynamic `import()` in `sdk.js` (module-level singleton), mapped to the app's
vitals shape by `adapter.js`, and handed back to the main page through `sessionStorage` plus a full-page navigation. An
older in-house `FaceScanModal` (MediaRecorder → S3 → `/facescan/analyze`) is still imported and wired but has no live
trigger.

## Findings

### Config / hardcoding

1. **Med** · No config module; settings scattered across call sites · `src/api.js:3,19,80`,
   `src/FaceScanModal.jsx:4,76`, `src/senai_scan/ScanPage.jsx:82,115`, `src/senai_scan/sdk.js:30`,
   `vite.config.js:55`, `src/DashboardPanel.jsx:82,84` · Timeouts (30000, 280000, 45_000), poll/countdown intervals
   (300 ms, 250 ms), record length (30 s), measurement preset, dev port (5174), summary period/window (`"daily"`,
   `slice(-7)`) are each defined where used. → `src/config.js` reading `import.meta.env.VITE_*` with documented
   defaults and typed groups (`api`, `scan`, `storage`, `routes`); add the `.env.example` that `.gitignore:33` already
   whitelists but does not exist.
2. **Med** · Production API URL as silent fallback · `src/api.js:3` · A dev build without `VITE_API_URL` talks to the
   production API and writes real data (root `README.md:84-85` warns about exactly this). → Fail fast at config load
   if unset, or default to localhost only when `import.meta.env.DEV`.
3. **Low** · Storage keys, routes and DOM ids duplicated as literals · `"auth_token"` at `api.js:6`,
   `App.jsx:312,316,372,376`, `ScanPage.jsx:25`; `"nutrasmart_messages"` at `App.jsx:324,364`; `"/scan.html"` at
   `App.jsx:419,466`; return path `"/"` at `ScanPage.jsx:21` and `scanMain.jsx:12`; canvas id `"mxcanvas"` at
   `sdk.js:45` and `ScanPage.jsx:17`; `"N/A"` sentinel at `App.jsx:141,180`. → `storageKeys`/`routes` in the config
   module; pass the canvas id into `initShenai`.
4. **Low** · Palette triplicated and tokens bypassed · macro colours at `App.jsx:207-209`, `DashboardPanel.jsx:11`,
   `styles.css:138`; raw hex outside the `:root` token block at `styles.css:145,150,151,178,248,262,266,289` and
   `DashboardPanel.jsx:7-10`. → `--macro-protein/--macro-carbs/--macro-fat`, `--danger`, `--ink-black` tokens plus one
   JS export for SVG use.

### Timeouts

5. **High** · S3 upload has no timeout/abort · `src/api.js:60-63` · `putToS3` is a bare `fetch` PUT; a stalled upload
   (especially the 30 s webm from `FaceScanModal.jsx:89-93`) hangs forever and `busy` (`App.jsx:382`) locks the
   composer. → Route through the same abortable helper with its own configurable (larger) timeout; ideally XHR /
   `ReadableStream` for progress.
6. **Med** · WASM runtime load has no deadline · `src/senai_scan/sdk.js:37-47` · Only licence activation is guarded
   (`sdk.js:116-122`); the ~33 MB `import()` is not, so a stalled network leaves the page on "Loading scan engine…"
   (`ScanPage.jsx:70`) indefinitely. → `Promise.race` with a configurable `RUNTIME_LOAD_TIMEOUT_MS`, or a
   progress-stall watchdog driven by `onWasmLoadingProgress`.
7. **Low** · Timeouts expressed as inline literals · `src/api.js:19` (default param) and `:80` (call-site literal with
   a comment). → `config.api.timeoutMs` / `config.api.faceScanTimeoutMs`.

### Component structure / separation of concerns

8. **High** · `App.jsx` is a god module · 484 LOC, 8 components, 6 `useState`, 3 `useEffect`, 2 `useRef`, module-level
   mutable `idc` at `:127` · In one file: metric formatting (`:20-28`), analysis-to-text formatting (`:144-170`), a
   markdown shim (`:139`), an error boundary (`:130-138`), auth decode/persist (`:311-319,370-376`), thread persistence
   and cross-page pickup (`:320-331,347-366`), chat-history shaping for Bedrock (`:386-388`), the upload pipeline
   (`:396-413`), and navigation side effects (`:419,466`). → Split into `components/` (VitalsStrip, VitalsCard, Bubble,
   LoginGate, TypingDots, MessageBoundary), `hooks/useSession.js`, `hooks/useThread.js` (messages + sessionStorage +
   pending-vitals pickup), `lib/formatAnalysis.js`, `lib/vitals.js`; `App.jsx` as composition only.
9. **Med** · Substantial dead code shipped in the bundle · `src/App.jsx:180-278` (`AnalysisCard`, `show`, `num`,
   `MICRO_LABELS`), `:281-289` (`"raw"`/`"analysis"` Bubble branches), `:141` (`_show`, identical to `show` at `:180`),
   `:423-426,475-481` (`handleScanResult`, `FaceScanModal` mount), `src/api.js:5-7` (`getToken` export), `:73-81`
   (`faceScan`), `:91-93` (`generateWeeklySummary`) · Only `type: "vitals"` is ever produced (`App.jsx:356,425`);
   `sendImage` emits text via `formatAnalysis` (`:409`), so `AnalysisCard` is unreachable; `setScanOpen(true)` exists
   only inside comments (`:417,464`), so `FaceScanModal.jsx` (153 LOC) and its API call are unreachable. → Decide per
   path: either make `sendImage` emit `type: "analysis"` and delete `formatAnalysis`, or delete `AnalysisCard`+CSS;
   gate the in-house scan behind `VITE_FACESCAN_PROVIDER=inhouse|shenai` or remove it.
10. **Med** · Identity derived four ways · `src/App.jsx:311-319` (decode + exp check), `:373-374` (decode),
    `src/senai_scan/ScanPage.jsx:23-30` (decode), `src/api.js:5-7` (raw token) · All read `localStorage.auth_token`
    independently; `email` is additionally plumbed as a prop (`App.jsx:403,477`, `FaceScanModal.jsx:92`) and request
    body (`api.js:56`). → `auth/session.js` (`getSession() → {token,email,firstName,picture,exp} | null`,
    `setSession`, `clearSession`) shared by both entrypoints.
11. **Low** · `DashboardPanel` mixes fetch, transform, chart math and has data-honesty bugs ·
    `src/DashboardPanel.jsx:81-98` (fetch + reshape inside an effect, no abort on unmount), `:15` (`Math.max` of
    all-zero data → divide by zero → `NaN` bar heights), `:95` + `:122` (`rows.length` labelled "day streak"),
    `:117-118` (latest-day protein labelled "avg protein"), `:86` (dates forced to UTC while backend accepts a
    `timezone` query param, `meals.py:277`). → `useNutritionSummary()` hook returning typed `{week, macros}`; guard
    `max === 0`; fix the labels or compute the real values.
12. **Low** · Imperative DOM timing hacks · `src/FaceScanModal.jsx:45` (`setTimeout(…,0)` to set `srcObject`);
    `ScanPage.jsx:51-54` manual canvas (justified and documented, keep). → Effect keyed on `[phase]` for the video element.

### SDK boundary (`senai_scan/`)

13. **Med** · SDK correctly a dependency, but it leaks past the adapter into the page · `package.json:7,14`,
    `.gitignore:37`, `src/senai_scan/ScanPage.jsx:82-115`, `adapter.js:69-91` · `sdk.js` is first-party wrapper code,
    not vendored SDK (good). But `ScanPage.jsx` calls `setMeasurementPreset`, `attachToCanvas`,
    `getMeasurementState/FaceState/ProgressPercentage`, `setOperatingMode`, `getMeasurementResults` and compares
    `sdk.MeasurementState.*`/`OperatingMode.*` enums directly; `statusText` takes the raw `sdk` object. → `sdk.js`
    exposes a facade: `startMeasurement({canvasId, preset, pollMs, onStatus, onProgress, onFinished, onFailed}) →
    stop()` so React never sees SDK enums; move `statusText` and the auto-start logic (`ScanPage.jsx:93-102`) inside it.
14. **Med** · Module-level singletons, import-time env read, scan module bleeds into the main bundle graph ·
    `src/senai_scan/sdk.js:23,25-26`; `src/App.jsx:6` · `App.jsx` imports `PENDING_KEY` from `ScanPage.jsx`, which
    imports `sdk.js` (and therefore `VITE_SHENAI_API_KEY`) and `adapter.js` into the chat page's module graph for one
    string constant. → Move `PENDING_KEY` to `senai_scan/handoff.js` (or the config module); turn the loader into
    `createShenaiRuntime(config)` instantiated in `scanMain.jsx`, preserving once-per-page semantics there.
15. **Low** · `prepare:shenai` is a shell copy on every `dev`/`build` · `package.json:7-9` · `rm -rf`/`cp -R` are not
    portable, copy ~33 MB each start, nothing verifies `public/shenai-sdk` matches `node_modules/@shenai/sdk`; the
    runtime `import()` at `sdk.js:37` bypasses Vite so there is no version coupling. → `vite-plugin-static-copy`
    (installed via npm) targeting `@shenai/sdk/**`, or at minimum an npm `prepare` lifecycle hook.
16. **Low** · Error class has no `name`/`code`; developer instructions reach end users ·
    `src/senai_scan/sdk.js:60,76-81,92,118-120,140`; rendered verbatim at `ScanPage.jsx:119,163` · Messages cite
    `src/senai_scan/README.md`, `.env`, `VITE_SHENAI_API_KEY`. → `ShenaiInitError` with a `code` (`MISSING_KEY`,
    `NO_SAB`, `LICENCE_TIMEOUT`, `INVALID_KEY`, …); the page maps codes to user copy and logs detail.

### Typing / contracts

17. **Med** · Response and message shapes are implicit · `src/api.js:31` (`req` returns untyped JSON),
    `src/App.jsx:20-28` (metric shape documented in a comment), `:176-179` (API fields in a comment), `:281-296`
    (messages discriminated by ad-hoc `type/text/thumb/data/region/label` fields), `src/senai_scan/adapter.js:12-62`
    (the de-facto `Vitals` schema) · → JSDoc `@typedef`s in `src/types.js` for `Vitals`, `MetricResult`, `ChatMessage`
    (discriminated union), `AnalyzeResponse`, `PresignResponse`, `NutritionSummaryRow`, with `// @ts-check` in
    `api.js` and `adapter.js`. A TypeScript migration is not justified at ~1.4 kLOC (YAGNI).
18. **Low** · Contract drift against the backend · `src/api.js:79` sends `content_type` to `/facescan/analyze`, which
    the backend accepts but never forwards (`backend/app/routes/facescan.py:16-18,37-43`);
    `backend/app/routes/facescan.py:31-32` says only heart rate is returned while `formatMetric` renders bp/spo2;
    `api.js:56` sends `email` which `upload.py:37` uses for the S3 key even though `auth.py:18` already has the
    verified email. → Drop `email` and `content_type` from client payloads once the backend reads them from the token;
    optionally a `VITE_DEV_USER_COUNTRY` header hook so the README's region test (`README.md:150`) is reachable from the UI.

### Errors / logging

19. **Med** · 401/403 does not clear the session · `src/api.js:28`, `src/App.jsx:311-319` · The error is rewritten to
    "Session expired" but the token stays in `localStorage` and `user` stays set; expiry is only checked at mount, so
    after ~1 h every action fails until a manual reload. → `api` accepts an injected `onUnauthorized` callback (from
    `App`/session hook) that calls `clearSession()` and resets `user`.
20. **Low** · Console debris and swallowed errors · `src/api.js:32` logs every response body (emails, vitals, meals) in
    production; `sdk.js:71-73` logs the full user agent; `sdk.js:106,127` timings; empty `catch {}` at `api.js:27`,
    `App.jsx:318,327,355,365`, `ScanPage.jsx:27-29,134-137`; `alert()` at `App.jsx:305`. → `log.js`
    (`debug/info/warn/error`) gated on `import.meta.env.DEV`; a login error state instead of `alert`.
21. **Low** · `URL.createObjectURL` never revoked · `src/App.jsx:398`. → Revoke on unmount/removal or store a small
    data-URL thumbnail.

### Build / entrypoints

22. **Med** · Multi-page setup is justified, but only half-implemented · `vite.config.js:14-40,46-52`, `scan.html:9-11`
    · Both pages are correctly listed in `rollupOptions.input`; the COOP/COEP/CORP headers that make `/scan.html` work
    are set only in `configureServer` (dev), with production deferred to "CloudFront/ALB" in a comment (`:11-13`) and
    no artifact in the repo. `url.startsWith("/scan")` (`:21`) is a prefix match. → Codify the response headers in IaC
    (CloudFront response-headers policy) or a hosting `_headers` file, match `/scan.html` exactly, and add a smoke
    check that `crossOriginIsolated === true` on the deployed scan page.
23. **Low** · Page hand-off via hard navigation + sessionStorage · `src/App.jsx:419,466`,
    `src/senai_scan/ScanPage.jsx:131-140`, `scanMain.jsx:7` · Acceptable given the isolation constraint; costs are
    documented (thumbs lost). The scan page imports the entire chat stylesheet. → `scan.css` split and a `?return=`
    query param instead of the hardcoded `"/"`.

### Dependencies / tooling

24. **High** · No lint, format or test tooling; zero tests · `package.json:6-22` · No `eslint`/`prettier`/`vitest`/
    testing-library, no `lint`/`test` scripts, yet `// eslint-disable-next-line` comments exist (`App.jsx:357`,
    `FaceScanModal.jsx:27`). No `*.test.*`/`*.spec.*` files under `src/`. Pure functions ready for unit tests:
    `regionFromPresign`, `formatAnalysis`, `formatMetric`, `toVitals`, `statusText`, `roundedTop`. → Add `eslint`
    (+`eslint-plugin-react-hooks`), `prettier`, `vitest` + `jsdom` via npm; start with adapter/formatter tests.
25. **Low** · Caret ranges, no `engines`, stale docs · `package.json:13-21` (lockfile resolves vite 5.4.21,
    plugin-react 4.7.0, @react-oauth/google 0.12.2; all five deps used); `@shenai/sdk` license is "SEE LICENSE IN
    LICENSE.md" so redistribution via `public/shenai-sdk` should be confirmed. Docs contradict code:
    `src/senai_scan/README.md:41-59` says "we do NOT set COOP/COEP" while `vite.config.js:5-13`, `sdk.js:63-83`,
    `ScanPage.jsx:3-6` require and set them; `README.md:67` references a non-existent `SenaiScanModal.jsx`;
    `README.md:22` says `.env` while `.gitignore:26-33` steers to `.env.*`; `maitribot/README.md:21` references a
    `.env` not in the repo. → Rewrite the senai_scan README to match the page-based design; add `.env.example`.

### Security

26. **High** · Model/backend text rendered as HTML · `src/App.jsx:139` (`mdBold`), `:294` (`dangerouslySetInnerHTML`)
    · Chat replies (`d.reply`, `:390`), backend `detail` error strings (`api.js:27-29` → `:392,411`) and
    `formatAnalysis` output built from vision-model fields (`description`, `recommendation`, dish names) are injected
    unescaped; a prompt-injected food photo or a malicious error body can execute script. → Render `**bold**` by
    splitting into React text/`<strong>` nodes (no innerHTML), or run output through a sanitizer; never HTML-render
    error text.
27. **High** · `VITE_ORIGIN_VERIFY_SECRET` ships in the public bundle · `src/api.js:11-15` · `backend/app/main.py:19-24`
    itself notes the secret "would be extractable from public JS, defeating its purpose"; any `VITE_*` value is public.
    → Remove it from the client entirely and rely on the CloudFront-injected header.
28. **Med** · Privacy copy contradicts behaviour · `src/senai_scan/ScanPage.jsx:149` ("On-device · private"),
    `:178-179` ("Nothing is uploaded") vs `sdk.js:124` which sends the API key plus `userId` = the user's email
    (`ScanPage.jsx:57` via `currentEmail()`) to the Shen.AI licence server. → Pass an opaque per-user hash/UUID as
    `userId`; reword to "video never leaves your device; a licence check contacts Shen.AI".
29. **Med** · ID token in `localStorage`, read by both pages · `src/api.js:6`, `src/App.jsx:312,372`,
    `src/senai_scan/ScanPage.jsx:25` · Combined with #26 this is a token-exfiltration path. Google ID tokens expire in
    about an hour, which bounds the blast radius; `sessionStorage` would still survive the same-tab `/scan.html` round
    trip. → `sessionStorage` plus the 401 handling in #19.
30. **Low** · Camera permission handling is coarse · `src/FaceScanModal.jsx:46-50` one generic message for every
    `getUserMedia` failure (`NotAllowedError`, `NotFoundError`, `NotReadableError`); `:64-65` constructs
    `MediaRecorder` without feature-detecting it; `ScanPage.jsx` relies entirely on the SDK's prompt. → Branch on
    `e.name` and feature-detect before use.
31. **Low** · Shen.AI key is a public `VITE_*` value · `src/senai_scan/sdk.js:23` · Unavoidable for a browser SDK, but
    it must be origin-restricted in the vendor portal and documented as public in `.env.example`.

### Styling

32. **Low** · Roughly 70–80 of 334 lines are dead; iteration-suffix naming · `src/styles.css` · Never referenced from
    any JSX: `.cal-row/.cal-big/.cal-sub` (131-133), `.macros/.macro/.dot/.m-*/.macro-val/.macro-label` (135-140),
    `.dishes/.dish/.dish-name` (142-144), `.micros/.micro-chip` (147-148), `.raw` (154-156), `.card-actions/.chip`
    (158-164), `.gate-note` (244). Referenced only from the dead `AnalysisCard`/raw bubble: 90, 95-130, 145, 150-152,
    247-250. Naming is flat kebab-case with iteration leftovers (`.macro-legend2`, `.dish2*`), a duplicated section
    header (300-301) and a misplaced comment (270-273 describes `.senai-canvas` but sits above `.scan-page`). → Prune
    after resolving #9, settle on `block-element` naming, split a `scan.css` for the second entrypoint.

## Quick wins vs structural changes

**Quick wins (hours)**
- Replace `dangerouslySetInnerHTML` with a node-splitting bold renderer (#26); drop `X-Origin-Verify` from the client (#27).
- Give `putToS3` an abort/timeout and move all timeouts/intervals into a `config.js` with `.env.example` (#1, #5, #7).
- Clear the session on 401/403 (#19); remove the production-URL fallback (#2).
- Delete the dead `AnalysisCard`/raw-bubble/`FaceScanModal` paths and their CSS, or gate them (#9, #32).
- Move `PENDING_KEY` to `senai_scan/handoff.js` (#14); pass an opaque `userId` to Shen.AI and fix the privacy copy (#28).
- Strip `console.log` of response bodies/UA (#20); fix `NaN` bars and dashboard labels (#11).
- Add `eslint` + `prettier` + `vitest` with tests for `adapter.js`, `regionFromPresign`, `formatMetric`, `formatAnalysis` (#24).
- Fix stale READMEs (#25).

**Structural changes (days)**
- Decompose `App.jsx` into `components/`, `hooks/useSession`, `hooks/useThread`, `lib/` (#8, #10).
- Shen.AI facade in `sdk.js` so `ScanPage.jsx` has no SDK enum knowledge; instantiate the runtime loader via DI in `scanMain.jsx` (#13, #14).
- JSDoc typedefs + `// @ts-check` for API/vitals/message contracts (#17).
- Codify production COOP/COEP/CORP headers for `/scan.html` in infrastructure and add a deployed smoke check (#22); replace the shell copy with a Vite static-copy plugin (#15).
- Trim client payloads once the backend reads identity from the token (#18).

## Metrics

| File | LOC |
|---|---|
| `src/App.jsx` | 484 |
| `src/styles.css` | 334 |
| `src/senai_scan/ScanPage.jsx` | 186 |
| `src/senai_scan/sdk.js` | 154 |
| `src/FaceScanModal.jsx` | 153 |
| `src/DashboardPanel.jsx` | 144 |
| `src/api.js` | 97 |
| `src/senai_scan/adapter.js` | 91 |
| `src/senai_scan/README.md` | 76 |
| `vite.config.js` | 58 |
| `src/senai_scan/ScanBoundary.jsx` | 45 |
| `package.json` | 23 |
| `src/main.jsx` / `src/senai_scan/scanMain.jsx` / `scan.html` | 15 each |
| `index.html` | 12 |
| **JS/JSX total** | **1,384** (+334 CSS, +108 HTML/config) |

- Components: 14 — `App.jsx` 8 (VitalsStrip, VitalsCard, MessageBoundary, TypingDots, AnalysisCard, Bubble,
  LoginGate, App), `DashboardPanel.jsx` 3, `FaceScanModal.jsx` 1, `ScanBoundary.jsx` 1, `ScanPage.jsx` 1.
  Dead/unreachable: AnalysisCard, FaceScanModal.
- `App.jsx` hooks: `useState` × 6 (`:311,320,332,333,334,335`), `useEffect` × 3 (`:343,347,360`), `useRef` × 2
  (`:336,337`); 1 module-level mutable (`idc`, `:127`).
- Network calls: 2 `fetch` sites (`api.js:23` with AbortController; `api.js:61` without) → **1 of 2 lacks a timeout**.
  Other I/O without a deadline: dynamic WASM `import()` at `sdk.js:37`. SDK licence call guarded at `sdk.js:116` (45 s).
- Hardcoded URL/literal settings: ≈27 distinct values across ≈45 occurrences (1 production URL, 2 request timeouts,
  1 licence timeout, 3 intervals/durations, 1 port, 5 storage keys/routes/DOM ids, 1 S3 host regex, 1 period + 1 window
  size, 1 measurement preset + 6-field settings block, 1 mime string, 3 chart-dimension groups, ≈12 raw hex colours,
  emoji-prefix command routing at `App.jsx:416,419`).
- Tests: 0. Lint/format config files: 0. Unused npm dependencies: 0 (all five used). Unused API exports: 2
  (`getToken`, `generateWeeklySummary`).
