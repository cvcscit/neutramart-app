# Refactoring roadmap: what is done, what is in progress and what is left

**Last updated:** 2026-10-26
**Base:** branch `dev`, commit `26eecb6`. Everything marked done is **uncommitted** working-tree change on top of
that commit; line numbers in the *Where* column refer to the working tree on 2026-10-26.
**Tracks:** every finding in the refactoring review
([00-refactoring-review-summary.md](00-refactoring-review-summary.md) and its parts 01–04, 172 findings) through the
five phases of its §5, plus findings made while implementing (`NEW-n`).

Related: [00 summary](00-refactoring-review-summary.md) (roadmap and decisions) ·
[01 repo layout and infra](01-repo-layout-and-infra.md) (`INF-n`) · [02 backend API](02-backend-api.md) (`API-n`) ·
[03 agent service](03-agent-service.md) (`AGT-n`) · [04 web client](04-web-client.md) (`WEB-n`) ·
[MIGRATION_OUTSTANDING_TASKS.md](../MIGRATION_OUTSTANDING_TASKS.md) (AWS account migration; CloudFront still blocked).

## Short answer

| Phase | Findings | Done | Partial | Left (of which blocked or waiting) |
|---|---|---|---|---|
| 0 — safety and hygiene | 27 | 23 | 3 | 1 (`INF-21` needs your yes) |
| 1 — collapse duplication | 23 (+`NEW-1`) | 0 | 2 | 21 (+1) (`INF-1`, `INF-2` on D7; `INF-4` on D2) |
| 2 — settings, DI, typed contracts | 48 | 0 | 14 | 34 |
| 3 — god modules, test gap, docs | 43 | 0 | 8 | 35 |
| 4 — client decomposition | 25 | 0 | 2 | 23 (`WEB-9`, `WEB-32` on D4/D5) |
| Decisions only / no action | 6 | — | — | 2 wait on decisions (`INF-35` on D1, `INF-23` on D6); 4 need no action |

- **Phase 0 is done in code but not live.** Nothing was committed or deployed. The agent fixes are in the canonical
  package only; the four deployed AgentCore projects build from their own copies (§9, R1). The edge and client must
  be deployed in a set order (§9, R2–R4).
- **Tests:** edge 0 → 44 tests (`backend/tests/`); agent 60 → 71 passing, 2 opt-in skipped. Both services start and
  answer their health checks locally; the client builds.
- **Your input is needed on:** deleting the root Node files (`INF-21`), syncing or collapsing the agent copies
  (R1), confirming decision D3 (face-scan exposes BP/SpO2, flagged experimental), and adding `BUCKET_*` to your
  local `backend/.env` (R4).

## 1. How to read this file

- Every finding ID from parts 01–04 appears exactly once, in the phase that will close it. The summary's §5 assigned
  about half of them to a phase; the rest are assigned here and marked †.
- A finding that Phase 0 fixed only in part stays in the phase that will finish it, with status *partial* and what
  is left.
- **Status values:** *done* (in the working tree, uncommitted) · *partial: what is left* · *to do* ·
  *blocked: on what* · *needs yes* (deletes or overwrites files outside the change; waiting for the owner).
- When an item is finished, set its status, add the date, and add an entry to the log in §2. Don't renumber or
  delete rows.

## 2. Progress log

### 2026-10-26 — Phase 0 implemented in the working tree; uncommitted
- **Done:** 23 of the 27 Phase 0 findings, partial work on 26 later-phase findings (statuses in §3–§7). Edge:
  verified-identity upload keys, key scoping, fail-closed regions, constant-time origin check with a settings-driven
  exemption, `email_verified`, timeouts on S3 and the Google cert fetch, typed face-scan response, generic error
  details. Agent: no import-time AWS clients in `main.py`, timeouts on every client, key scoping, hashed user ids in
  logs, `evaluate_classifier.py` path, `.dockerignore`, pins. Client: no HTML rendering of text, no origin secret,
  session cleared on 401/403, upload deadline, `src/config.js`.
- **Verified:** `backend/venv_backend/bin/python -m pytest -q tests` → 44 passed;
  `backend/agent/venv_agent/bin/python -m pytest -q app tests` → 71 passed, 2 skipped; edge `/health` and agent
  `/ping` answer 200 from a local start; `npx vite build` (into the scratchpad, not `dist/`) succeeds and the app
  chunk contains neither `X-Origin-Verify` nor `dangerouslySetInnerHTML`; `uv pip install --dry-run` confirms both
  pinned requirement sets resolve.
- **Found:** `NEW-1` to `NEW-4` (§8). `mediapipe==0.10.14` with `numpy==2.0.2` and opencv 5.0.0.93 runs a FaceMesh
  pass on x86_64 / Python 3.12 (partial evidence for D8).
- **Environments:** created `backend/venv_backend` (uv, Python 3.12; `requirements.txt` + `pytest` 9.1.1 +
  `httpx` 0.28.1) and filled the empty `backend/agent/venv_agent` from `requirements-dev.txt`. Both are gitignored.
- **Docs:** this file; root `README.md` local-env block (required `BUCKET_US`, no origin header); new
  `backend/.env.example` and `maitribot/client/.env.example`.

## 3. Phase 0 — safety and hygiene

| ID | Sev | Step | Status | Where |
|---|---|---|---|---|
| `API-10` | Med | Explicit botocore `Config` (timeouts, retries) on the regional S3 clients | done | `backend/app/regions.py:64`, `backend/app/config.py:52` |
| `API-11` | Med | Bounded Google cert fetch; outage → 503, not 401 | partial: a cached, lifespan-owned transport waits for `API-28` | `backend/app/auth.py:38` |
| `API-43` | High | `hmac.compare_digest`; exempt origins from settings, empty by default | done; the demo origin is still set in the task definition until CloudFront is back | `backend/app/main.py:38`, `backend/app/config.py:123`, `backend/ecs/task-definition.json:30` |
| `API-45` | Med | Presign key from the verified user, under `users/{user_id}/uploads/`; body `email` ignored | done | `backend/app/routes/upload.py:48`, `backend/app/user_keys.py:19` |
| `API-47` | Med | Unconfigured region → `RegionNotConfigured` → 503; no fallback, no bucket defaults | done | `backend/app/regions.py:73`, `backend/app/main.py:55`, `backend/app/agent_client.py:78` |
| `API-48` | Med | `FaceScanResponse` whitelist; BP/SpO2 always `experimental: true` | done; assumes D3 = (b) | `backend/app/routes/facescan.py:63` |
| `API-49` | Med | Require `email_verified is True`; missing e-mail → 401 | done | `backend/app/auth.py:48` |
| `API-41` | Low | Pin `boto3` | partial: pinned to 1.43.119; lock file left for Phase 3 tooling | `backend/requirements.txt:3` |
| `API-8` † | Low | Demo origin as a setting, not a constant in `main.py` | done | `backend/app/config.py:123` |
| `API-12` † | Low | Health-check probe with `timeout=` (Dockerfile and the task definition, which overrides it) | done | `backend/Dockerfile:23`, `backend/ecs/task-definition.json:65` |
| `API-15` † | Med | One `user_id_from_email` instead of six copies | done | `backend/app/auth.py:26` |
| `API-18` † | Low | Runtime ARN resolved once in `get_data_context`; `invoke_agent` requires it | done | `backend/app/agent_client.py:78` |
| `INF-17` † | Low | Backend image copies only `app/`; `.dockerignore` excludes venvs, tests, docs, `.env.*` | done | `backend/Dockerfile:14`, `backend/.dockerignore` |
| `AGT-8` | High | `main.py` uses food_scan's clients (timeouts, retries) instead of bare import-time clients | done | `backend/agent/app/nutrasmart_agent/main.py:266` |
| `AGT-9` | Med | Strands `BedrockModel` gets `boto_client_config` and `chat_max_tokens` | done | `backend/agent/app/nutrasmart_agent/main.py:279` |
| `AGT-10` | Med | Face-scan model-bucket client gets timeouts from settings | done | `backend/agent/app/nutrasmart_agent/face_scan_biomarkers/services.py:75` |
| `AGT-36` | High | `evaluate_classifier.py` puts `backend/agent` on `sys.path` (`parents[4]`) | done; moving the scripts to `tools/` goes with the Phase 1 layout | `backend/agent/app/nutrasmart_agent/food_scan/scripts/evaluate_classifier.py:37` |
| `AGT-37` | Med | Agent `.dockerignore` (env, venvs, tests, scripts, copies) | done for `backend/agent/`; the four CLI copies build from their own context (R1) | `backend/agent/.dockerignore` |
| `AGT-38` | Med | Pin `opencv-python-headless` and `boto3` | partial: both pinned; lower-bound pins, duplicate `pytest` pin and per-target lock left for Phase 1 | `backend/agent/requirements-base.txt:4`, `:18` |
| `AGT-44` | High | Agent refuses any key outside `users/{user_id}/` (and `..` segments) | done | `backend/agent/app/nutrasmart_agent/main.py:58`, `:341`, `:369` |
| `WEB-5` | High | S3 PUT under a deadline with a readable timeout message | done | `maitribot/client/src/api.js:82`, `maitribot/client/src/config.js:19` |
| `WEB-7` † | Low | Request timeouts in `src/config.js` instead of inline literals | done | `maitribot/client/src/config.js:12` |
| `WEB-19` | Med | 401/403 clears the token and returns to the login gate | done | `maitribot/client/src/api.js:14`, `maitribot/client/src/App.jsx:352` |
| `WEB-26` | High | `**bold**` rendered as React nodes; no `dangerouslySetInnerHTML` | done | `maitribot/client/src/App.jsx:141`, `:298` |
| `WEB-27` | High | `X-Origin-Verify` no longer sent by the client | done; absent from a production build | `maitribot/client/src/api.js:18` |
| `INF-21` | Med | Delete the vestigial root `package.json` (`{}`) and `package-lock.json` | needs yes | `package.json`, `package-lock.json` |
| `INF-22` | Med | Root `.gitignore` covers Python, Node, CDK caches, logs and `.env.*` (keeps `.env.example`) | done | `.gitignore` |

## 4. Phase 1 — collapse duplication

Blocked overall on D7 (verify `agentcore deploy` target selection and whether `codeLocation` may point outside the
project) and on a cutover plan: moving to named targets creates new runtimes with new ARNs.

| ID | Sev | Step | Status |
|---|---|---|---|
| `INF-1` | High | One agent package; delete `backend/agent/regions/` and the copy inside `NutrasmartAgent/` | blocked: D7 |
| `INF-2` | High | One AgentCore project with targets `us`, `in`, `ca`, `eu` | blocked: D7, cutover |
| `INF-3` | Med | `REGION_PROFILES` table (bucket, model id per region) in the agent settings | to do |
| `INF-4` | Med | Agent IAM policy: four buckets in one policy, or rendered per target | blocked: D2 |
| `INF-5` | Med | Keep one generated CLI scaffold (`cdk/`, `.llm-context/`) | to do (with `INF-2`) |
| `INF-6` † | Low | One home for the agent Dockerfile and requirements files | to do |
| `INF-7` † | Low | `runtimeVersion` (`PYTHON_3_14`) agrees with the 3.12 image | to do |
| `INF-8` † | Low | `--platform` moves from `FROM` to the build command | to do |
| `INF-9` | High | `deploy.sh` registers SHA-tagged task-definition revisions; real rollback | to do |
| `INF-10` | High | `setup.sh` creates, and `teardown.sh` deletes, all seven SSM parameters | to do |
| `INF-11` | Med | Task-role policy built from the region list; drop `BedrockInvokeLegacy` | to do |
| `INF-12` | Med | One `ecs/config.env` sourced by all four scripts | to do |
| `INF-13` | Med | `setup.sh` idempotent (look up or create), or move ECS to CDK | to do |
| `INF-14` | Med | One credential convention (`AWS_PROFILE`) | to do |
| `INF-15` † | Low | `setup-https.sh`: domain as a parameter, poll ACM instead of `sleep` | to do |
| `INF-16` † | Low | `teardown.sh` waits on the ALB and removes cert, records, all SSM params | to do |
| `INF-18` † | Med | `task-definition.json`: region and origins as parameters, no localhost in prod | to do |
| `INF-20` † | Low | Google client ID as a plain `String` parameter; `cf-origin-secret` as SecureString | to do |
| `INF-27` † | Low | One `deployed-state.json`; scrub old-account IDs from docs | to do |
| `INF-34` † | Med | Scope the agent policy's Bedrock and marketplace wildcards | to do |
| `API-42` † | Low | Backend Dockerfile hygiene | partial: `COPY app/` and `.dockerignore` done; `PYTHONUNBUFFERED`, port `ARG` left |
| `AGT-39` † | Med | Verify `mediapipe==0.10.14` + `numpy==2.0.2` on arm64 / Python 3.12 | partial: works on x86_64 (2026-10-26); arm64 open (D8) |
| `AGT-40` † | Low | Agent Dockerfile hygiene (`USER`, `PYTHONUNBUFFERED`, `ffmpeg` need, cache-dir env) | to do |
| `NEW-1` | Med | Two OpenCV builds in the agent image (§8) | to do |

## 5. Phase 2 — settings, dependency injection and typed contracts

| ID | Sev | Step | Status |
|---|---|---|---|
| `API-1` | High | Frozen pydantic-settings `Settings`, required fields, loaded in `create_app` | partial: region bucket defaults removed |
| `API-2` † | Med | `MAX_IMAGES_PER_REQUEST`, `MAX_DAILY_UPLOADS` into settings | to do |
| `API-3` † | Med | Rate-limit strings into settings | to do |
| `API-4` † | Med | One S3 key builder, shared with the agent | partial: `backend/app/user_keys.py` owns the upload layout |
| `API-5` † | Low | Content-type → extension map in settings | to do |
| `API-6` † | Low | `agent_client` literals (connect timeout, qualifier) into settings or constants | to do |
| `API-7` † | Low | `Period` enum and named constants in `meals.py` | to do |
| `API-9` † | Low | Delete dead settings and their task-definition entries | to do |
| `API-16` | Med | Typed `AgentClient` methods and an `AgentAction` enum | to do |
| `API-22` | High | `DataContext` and `AuthenticatedUser` dataclasses; typed payloads | to do |
| `API-23` † | Med | `response_model=` on every route | partial: `/facescan/analyze` done |
| `API-24` † | Med | Typed, validated query params in `meals.py` | to do |
| `API-25` † | Low | snake_case schema with aliases | to do |
| `API-26` † | Low | `list[...]`, `Field(default_factory=...)`, `Literal` roles in `chat.py` | to do |
| `API-27` † | Low | `TypeAdapter` per action in `_parse_result` | to do |
| `API-28` | High | Lifespan-owned AWS clients and Google transport instead of `lru_cache` | to do |
| `API-29` | Med | No import-time `load_dotenv` or parsing | to do |
| `API-30` | Med | `create_app(settings)` factory | to do |
| `API-31` | Low | Limiter built in `create_app` | to do |
| `API-32` | Low | Token audience from injected settings | to do |
| `API-33` | Med | Structured JSON logging with request, user and region context | to do |
| `API-34` | Med | Catch `ClientError` by code instead of `except Exception` | partial: `auth.py` done |
| `API-35` | Med | Domain error hierarchy with one exception handler | partial: `RegionNotConfigured` → 503 |
| `API-36` | Low | Generic client messages; one 502/504 mapping | partial: analyze, weekly summary and face scan done |
| `API-37` | Low | Log an error once, where it becomes HTTP | to do |
| `API-44` † | High | Rate limit keyed on the verified user, shared storage | to do |
| `API-50` † | Low | Enumerated CORS headers; production origins only from env | to do |
| `API-53` † | Low | `X-User-Country` override in dev only | to do |
| `INF-19` † | Med | Edge code defaults that point at the old account | partial: bucket defaults removed; Google client ID literal, demo origins, Bedrock constants left |
| `AGT-1` | High | One agent settings module, loaded once and injected | partial: `main.py` no longer reads the environment |
| `AGT-2` | Med | `storage.py` (`UserDataLayout`, `ScanRecordStore`) | to do |
| `AGT-3` † | Med | `max_tokens` and `days` literals into settings | partial: chat and summary token limits done; `days=60` left |
| `AGT-6` † | Low | JPEG quality and resize size into settings | to do |
| `AGT-7` † | Low | `Status` enum and one messages module per package | to do |
| `AGT-12` | High | `main.py` split into `chat/`, `summary/` and a composition root | to do |
| `AGT-14` | Med | One AWS client builder | partial: `main.py` reuses food_scan's; face_scan keeps its own |
| `AGT-20` | High | Typed invocation contract (`Action` enum, request dataclasses) shared with the edge | to do |
| `AGT-21` † | Med | `NutritionAnalysis` and `RecognitionBlock` dataclasses | to do |
| `AGT-23` † | Low | `S3Client` / `BedrockRuntime` protocols | to do |
| `AGT-24` † | Low | Use or drop `ImageRef.content_type` | to do |
| `AGT-25` | High | No import-time clients; injectable tools | partial: import-time clients removed (`main` is importable in tests); tools still reach services through module caches |
| `AGT-27` † | Low | Load settings at startup, build clients on first request | to do |
| `AGT-29` | Med | JSON logging with an AgentCore session correlation id | to do |
| `AGT-30` | Med | Agent error hierarchy; safe messages instead of `str(e)` | partial: `InvalidRequest` for payload and key errors; `invoke` still returns `str(e)`, which the edge no longer forwards |
| `AGT-31` † | Low | `ClientError` / `NoSuchKey` instead of broad excepts | to do |
| `WEB-1` | Med | `src/config.js` for every client setting; `.env.example` | partial: request deadlines and `.env.example` added |
| `WEB-17` | Med | JSDoc typedefs and `// @ts-check` | to do |
| `WEB-18` † | Low | Client payloads match the backend contract | partial: `email` dropped from presign; `content_type` to `/facescan/analyze` left |

## 6. Phase 3 — god modules, test gap and docs

| ID | Sev | Step | Status |
|---|---|---|---|
| `API-13` | High | Split `meals.py` into repository, aggregator and schemas | to do |
| `API-14` | High | Services for quota, summary and upload | to do |
| `API-17` † | Med | Weekly-summary routes move to `routes/summary.py` | to do |
| `API-19` † | Low | Delete dead code | partial: `agent_arn_for_region`, `bucket_for_region`, unreachable fallback removed; `head_object`, local `import re`, unused import left |
| `API-21` † | Low | One sync/async handler convention | to do |
| `API-38` | High | `backend/pyproject.toml` (ruff, mypy, pytest) and the edge test suite | partial: `backend/tests/` has 44 tests; tooling config left |
| `API-39` † | Med | Module and handler docstrings | partial: added to the modules touched in Phase 0; `chat`, `meals`, `testimonials`, `limiter` left |
| `API-40` † | Low | Consistent typing and formatting; ruff and mypy in CI | to do |
| `API-46` † | Med | Upload size cap (presigned POST with `content-length-range`, or `head_object`) | to do |
| `API-51` † | Low | Daily quota counts past one listing page; logs failures | to do |
| `API-52` † | Low | `_parse_logged_at` keeps real offsets | to do |
| `API-54` † | Low | Meals listing paginated, date-prefixed keys | to do |
| `AGT-4` | Med | Validated, injectable `BiomarkerSettings` | partial: `env` parameter and S3 timeouts; validation and DSP knobs left |
| `AGT-5` | High | DSP and product constants from `dsv` into settings | to do |
| `AGT-11` † | Med | `max_video_seconds` passed to `extract_video` | to do |
| `AGT-13` † | Med | Delete the stale prompts in `food_scan/prompts.py` | to do |
| `AGT-15` | Med | One `Lazy[T]`; face models through `model_store` | to do |
| `AGT-16` † | Med | Shared size guard and `converse_text` | to do |
| `AGT-17` | Med | Prune and split `dsv`, or freeze it as vendored | to do |
| `AGT-18` † | Low | Every ensemble member result tagged with its model | to do |
| `AGT-19` † | Med | Per-member ensemble loading with retry after a cooldown | to do |
| `AGT-22` | High | Face-scan dataclasses and a `Status` enum | to do |
| `AGT-26` † | Med | torch global state set once at the build boundary | to do |
| `AGT-28` † | Low | `ModelCache` thread safety (with `AGT-15`) | to do |
| `AGT-32` | High | `face_scan_biomarkers/tests/` on synthetic signals | to do |
| `AGT-33` † | Med | food_scan test gaps and `main.py` tests | partial: `backend/agent/tests/test_main.py`, `test_aws_clients.py` added |
| `AGT-34` † | Med | Docstrings and type hints in `dsv` | to do |
| `AGT-35` † | Med | README and docstring drift | partial: `main.py` docstring updated |
| `AGT-41` † | Low | Import `dsv` lazily inside `analyze_face_scan` | to do |
| `AGT-42` † | Med | Delete dead code | partial: `bedrock_config` is now read by chat |
| `AGT-45` † | Med | `joblib.load` of S3 objects: document the write lock, or move to ONNX/skops | to do |
| `AGT-46` † | Med | Paginate `list_objects_v2` in `get_recent_scans` | to do |
| `AGT-47` † | Med | Guard low-fps videos against the filter band | to do |
| `AGT-48` † | Low | `no_face_detected` status | to do |
| `AGT-49` † | Low | Close `FaceMesh` and release the capture on every path | to do |
| `AGT-50` † | Low | `extract_json` rejects non-dict results | to do |
| `AGT-51` † | Low | Typed storage results instead of text sentinels | to do |
| `INF-28` | High | Rewrite `DEPLOYMENT.md` | to do |
| `INF-29` | Med | Fold or regenerate `SECURITY.md` | to do |
| `INF-30` | Med | Update `DATA_RESIDENCY.md` | to do |
| `INF-31` | Med | Rewrite `backend/agent/README.md` for one project, four targets | to do |
| `INF-32` † | Low | Root `README.md`: current resources, no machine paths | partial: local-env block updated for required buckets; old profile, bucket names and `/home` paths left |
| `INF-33` † | Info | Reconcile `MIGRATION_OUTSTANDING_TASKS.md` with this refactor | to do |

## 7. Phase 4 — client decomposition

| ID | Sev | Step | Status |
|---|---|---|---|
| `WEB-2` † | Med | No silent production API fallback | to do |
| `WEB-3` † | Low | Storage keys, routes and DOM ids as constants | to do |
| `WEB-4` † | Low | Palette tokens instead of raw hex | to do |
| `WEB-6` † | Med | Deadline on the Shen.AI WASM load | to do |
| `WEB-8` | High | Decompose `App.jsx` into components, hooks and `lib/` | to do |
| `WEB-9` | Med | Delete or gate `AnalysisCard`, raw bubble and `FaceScanModal` | blocked: D4, D5 |
| `WEB-10` | Med | `auth/session.js` shared by both pages | to do |
| `WEB-11` † | Low | `useNutritionSummary` hook; fix `NaN` bars and labels | to do |
| `WEB-12` † | Low | Replace the `setTimeout` DOM hack in `FaceScanModal` | to do (moot if D4 deletes it) |
| `WEB-13` | Med | Shen.AI facade so the page never sees SDK enums | to do |
| `WEB-14` | Med | `PENDING_KEY` out of `ScanPage.jsx`; runtime loader via DI | to do |
| `WEB-15` † | Low | Static-copy plugin instead of `prepare:shenai` | to do |
| `WEB-16` † | Low | `ShenaiInitError` codes; user copy instead of developer text | to do |
| `WEB-20` † | Low | Console debris, empty `catch {}`, `alert()` | partial: response bodies logged in dev builds only |
| `WEB-21` † | Low | Revoke object URLs | to do |
| `WEB-22` | Med | COOP/COEP headers for `/scan.html` in infrastructure; smoke check | to do |
| `WEB-23` † | Low | `scan.css` split and a `?return=` parameter | to do |
| `WEB-24` | High | eslint, prettier, vitest; first tests | to do |
| `WEB-25` † | Low | Dependency ranges, `engines`, stale READMEs | to do |
| `WEB-28` † | Med | Opaque per-user id for Shen.AI instead of the e-mail; accurate privacy copy | to do |
| `WEB-29` † | Med | ID token in `sessionStorage` | to do |
| `WEB-30` † | Low | Camera permission errors by type | to do |
| `WEB-31` † | Low | Shen.AI key documented as public, origin-restricted | partial: `.env.example` says so; vendor-side restriction not checked |
| `WEB-32` † | Low | Delete dead CSS | blocked: D5 |
| `API-20` † | Low | Testimonials as static client JSON; drop the route | to do |

Decisions only, or no action: `INF-23` (keep the PDF in git, D6), `INF-24` (covered by `INF-22`), `INF-25` and
`INF-26` (Info, nothing to do), `INF-35` (product slug and renames, D1), `AGT-43` (single-backend registry is
acceptable; don't generalize further).

## 8. New findings

| ID | Sev | Finding | Phase |
|---|---|---|---|
| `NEW-1` | Med | `mediapipe==0.10.14` depends on `opencv-contrib-python`, so the agent image installs it **and** the pinned `opencv-python-headless` (both 5.0.0.93 here): two distributions of the same `cv2` module. It also pulls in `jax`, `jaxlib`, `matplotlib` and `sounddevice`. Read with `uv pip show mediapipe` in `backend/agent/venv_agent`, 2026-10-26. Decide which `cv2` build the image keeps and measure the image size. | 1 |
| `NEW-2` | Med | Uploads made before this change sit at `{email}/{uuid}.{ext}` at the bucket root, outside `users/{user_id}/`, keyed by the plain e-mail. They are food photos and face videos. The erasure job (`.claude/CLAUDE.md` §4) must cover that layout, or a one-off move brings them under `users/{user_id}/uploads/`. How many exist was not checked (needs a read-only listing of the four buckets). | 2 |
| `NEW-3` | Low | The tenant layout in `.claude/CLAUDE.md` §4 lists `scans/`, `vitals_scans/`, `weekly_summary.txt` and `health_profile.json`, but not `users/{user_id}/meals/` (`backend/app/routes/meals.py:85`) or the new `users/{user_id}/uploads/`. | 3 |
| `NEW-4` | Info | At `26eecb6` food_scan has 60 tests plus 2 opt-in skips, not the 50 the review counted, and `backend/agent/venv_agent` (uv, Python 3.12) replaces the broken `.venv` the review could not run. | — |

## 9. Rollout notes: what has to happen before Phase 0 is live

- **R1. The deployed agents don't have the agent fixes yet.** Only the canonical package
  (`backend/agent/app/nutrasmart_agent/`) and `backend/agent/{.dockerignore,requirements-base.txt}` changed. The four
  AgentCore projects build from their own copies under `backend/agent/NutrasmartAgent/` and
  `backend/agent/regions/NutrasmartAgent-{ca,eu,in}/`, which now differ from the canonical package (`main.py`,
  `food_scan/settings.py`, `food_scan/scripts/evaluate_classifier.py`, `face_scan_biomarkers/settings.py`,
  `face_scan_biomarkers/services.py`, `requirements-base.txt`, and no `.dockerignore`). Either copy the canonical
  files over the four copies (overwrites tracked files: needs yes) or wait for Phase 1 to collapse them.
- **R2. Deploy the edge before the agent and before the client.** The new agent refuses the `{email}/...` keys the
  old edge produces. The new client no longer sends `email`, which the old edge's presign model requires (422). The
  new edge accepts both old and new clients, because it ignores the extra `email` field.
- **R3. The edge needs a new task-definition revision.** `deploy.sh` only pushes `:latest` and forces a new
  deployment; it never registers a task definition (`INF-9`). Before deploying this edge build:
  (a) confirm the live revision sets `BUCKET_US/IN/CA/EU`, since there are no code defaults any more and a missing
  bucket now answers 503; (b) if the S3 demo build is still in use, register a revision that adds
  `ORIGIN_VERIFY_EXEMPT_ORIGINS` (as in `backend/ecs/task-definition.json:30`), otherwise the demo origin gets 403.
  Remove that variable once CloudFront is restored.
- **R4. Local edge runs need `BUCKET_*`.** `backend/.env` has no `BUCKET_*` lines and used to fall back to the old
  `sci-neutrasmart-project*` names; it now answers 503 for every user route. Add the buckets
  (`backend/.env.example` lists every variable).
- **R5. Direct-to-ALB local testing.** `MIGRATION_OUTSTANDING_TASKS.md` (Done list) describes sending
  `X-Origin-Verify` from the client to reach the ALB while CloudFront is blocked. The client no longer sends it. If
  that path is needed again, add the header server-side (a dev proxy), never as a `VITE_*` value.
- **R6. Stale rule text.** `.claude/CLAUDE.md` still describes `API-43`, `API-45`, `API-47`, `AGT-44`, `WEB-26` and
  `WEB-27` as open gaps (lines 23, 27, 33, 78, 85) and omits the `uploads/` and `meals/` prefixes (`NEW-3`). Update
  it once these changes are committed.

## 10. Decisions needed (from the summary's §6)

- **D1. Product slug and renames** (`INF-35`). **Answer:** _open_
- **D2. IAM residency:** one agent policy for four buckets, or rendered per target (`INF-4`). **Answer:** _open_
- **D3. Face-scan contract:** heart rate only, or BP and SpO2 too. **Assumed (b)** for `API-48`: expose all three,
  with BP/SpO2 forced to `experimental: true` plus a disclaimer, because
  `backend/agent/app/nutrasmart_agent/face_scan_biomarkers/__init__.py` records "the product decision was to surface
  all three" and the client renders all three. Choosing (a) means dropping `bp` and `spo2` from `FaceScanResponse`.
  **Answer:** _open — please confirm_
- **D4. In-house `FaceScanModal` and `/facescan/analyze`:** delete, or keep behind a provider flag (`WEB-9`).
  **Answer:** _open_
- **D5. Chat image results:** emit `AnalysisCard` or delete it and its CSS (`WEB-9`, `WEB-32`). **Answer:** _open_
- **D6. `documents/data-flow-diagram.pdf`:** keep in git or build in CI (`INF-23`). **Answer:** _open_
- **D7. AgentCore CLI:** does `deploy` select a target, and may `codeLocation` point outside the project
  (`INF-1`, `INF-2`). **Answer:** _open_ (check with the installed CLI before Phase 1)
- **D8. `mediapipe==0.10.14` + `numpy==2.0.2` on arm64 / Python 3.12** (`AGT-39`). **Answer:** _open_; works on
  x86_64 / Python 3.12 (FaceMesh pass, 2026-10-26).

## What wasn't verified

- Nothing ran against AWS or Google: no deploy, no bucket listing, no real token. The live task-definition
  contents (R3) and the number of legacy `{email}/` uploads (`NEW-2`) are unknown.
- The client was built, not run in a browser; there are no client tests (`WEB-24`).
- The BP and SpO2 bundles' target names are assumed to be `sbp`/`dbp` and `spo2` (what the client reads); the
  trained bundles in the model bucket were not opened.
- The agent image was not built; arm64 wheels are unverified (D8).
