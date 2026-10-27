# Refactoring roadmap: what is done, what is in progress and what is left

**Last updated:** 2026-10-27
**Base:** branch `dev`. Phase 0 was committed in `46d590e` (on top of `26eecb6`), and line numbers in the *Where*
column are at `46d590e`. The agent-copy sync and the root Node file deletion are in `bda9d6b`, the rule-text update
in `5eff3ff`, the log fix in `8928e1d`, the edge deploy scripts in `c87fb21`; the newest entry in §2 (production
stays in the old account) is uncommitted.
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
| 0 — safety and hygiene | 27 | 24 | 3 | 0 |
| 1 — collapse duplication | 23 (+`NEW-1`) | 6 | 6 | 11 (+1) (`INF-1`, `INF-2` on D7; `INF-4` on D2) |
| 2 — settings, DI, typed contracts | 48 | 1 | 14 | 33 |
| 3 — god modules, test gap, docs | 43 | 0 | 8 | 35 |
| 4 — client decomposition | 25 | 0 | 2 | 23 (`WEB-9`, `WEB-32` on D4/D5) |
| Decisions only / no action | 6 | — | — | 2 wait on decisions (`INF-35` on D1, `INF-23` on D6); 4 need no action |

- **Phase 0 is committed (`46d590e`) but not deployed.** The four AgentCore projects now carry the agent fixes too
  (synced in `bda9d6b`, §9 R1). Deploy the edge first, then the agents and the client (§9, R2–R4).
- **Production stays in the old account `209479309679` (D9, 2026-10-27).** Every live name (`nutrasmart.in`,
  `app.`, `api.`) is served from there; the September copy in `792207721590` serves nothing. `backend/ecs/config.env`
  now targets the old account and its `sci-neutrasmart-project*` buckets (§2, R7, R8).
- **The edge deploy scripts are rewritten (Phase 1, `c87fb21`):** one `backend/ecs/config.env`, a task definition
  with no literals, `deploy.sh` that registers a revision per commit and rolls back to the previous one, and a
  read-only `deploy.sh --plan`. Nothing has changed in AWS (§9 R3, R7).
- **Tests:** edge 0 → 63 tests (`backend/tests/`); agent 60 → 73 passing, 2 opt-in skipped. Both services start and
  answer their health checks locally; the client builds.
- **Still open for the owner:** add `BUCKET_*` to the local `backend/.env` (R4); a yes for
  `AWS_PROFILE=moxa-dev backend/ecs/deploy.sh --plan` (R7); how to redeploy the old account's agents (R8).

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

### 2026-10-27 — Production stays in the old account `209479309679` (D9); uncommitted
- **Found (read-only, 2026-10-27, profile `moxa-dev`, IAM user `mariom`):** the `nutrasmart.in` Route 53 zone the
  domain's name servers use is in `209479309679`, and so are the CloudFront distributions for `nutrasmart.in`,
  `app.nutrasmart.in` and `api.nutrasmart.in`. The API goes from there to ALB `nutrasmart-alb-800561718`, ECS
  `nutrasmart-backend:8` (image `1ebc811`, registered 2026-08-15), the four `nutrasmart_agent` runtimes (last updated
  2026-08-02) and buckets `sci-neutrasmart-project{,-us,-ca,-eu}`. The account is shared with another project.
- **Decided (owner):** production stays there and `mariom` deploys it (D9). The September copy in `792207721590` is
  not used.
- **Changed:** `backend/ecs/config.env` targets `209479309679` and the old buckets; `ALLOWED_ORIGINS` adds
  `https://app.nutrasmart.in`, which the live revision allows; `ORIGIN_VERIFY_EXEMPT_ORIGINS` is empty, because
  CloudFront adds `X-Origin-Verify` in this account (read: header name only). `export_runtime_arns` in
  `backend/ecs/lib.sh` now stops when a project's runtime is in another account: the AgentCore projects in the repo
  deploy to `792207721590`. `setup-https.sh` warns that it would repoint the live names at the ALB. The four scripts'
  usage lines name `EXPECTED_ACCOUNT_ID` instead of an account.
- **New edge with the old agents (read from git, `1ebc811` vs `HEAD`):** the user id is derived the same way; meals,
  scans, the summary and the profile were already under `users/{user_id}/`; the old agents read whatever upload key
  they are handed, so the new `users/{user_id}/uploads/` keys work. The old agents handle only `chat`, `summary` and
  `analyze`, so the new `/api/facescan/analyze` answers 502 until they are redeployed (R8). R2's order holds.
- **Verified:** edge 63 passed (new: the runtime-ARN account check, both ways); `bash -n` on all five scripts; an
  offline render shows the old account's image, roles, buckets and SSM ARNs. Nothing changed in AWS.
- **Docs that now disagree (not edited):** `.claude/CLAUDE.md` (§2 names the `w360-nutrasmart-*` buckets; §1 says
  the task definition sets `ORIGIN_VERIFY_EXEMPT_ORIGINS`), `.claude/skills/aws-infrastructure/SKILL.md` and its
  `which-runtime-serves-canada` eval (expect `792207721590`), `documents/MIGRATION_OUTSTANDING_TASKS.md` §5 and
  `backend/agent/README.md`.

### 2026-10-27 — Edge deploy scripts: one config, a revision per commit, rollback (`INF-9`–`INF-20`); committed in `c87fb21`
Written for account `792207721590` and the `w360-nutrasmart-*` buckets; the same day the target became the old
account (entry above).
- **One config (`INF-12`, `INF-18`):** `backend/ecs/config.env` holds every value the four scripts and the templates
  need (account, project, regions, the four `w360-nutrasmart-*` buckets, origins, domains). `backend/ecs/lib.sh`
  loads it for all four scripts. `task-definition.json` keeps only `<NAME>` placeholders, and
  `backend/ecs/deploy_helpers.py render` fills them (JSON-escaped; it stops with the names of any unfilled ones).
  `ALLOWED_ORIGINS` is `https://nutrasmart.in` only, so no localhost origins in production.
- **One credential convention (`INF-14`):** every script needs `AWS_PROFILE` and stops unless it resolves to
  `EXPECTED_ACCOUNT_ID` (`792207721590`). `deploy.sh` no longer needs `resources.env`; `setup-https.sh` and
  `teardown.sh` do, and stop unless it names the same account, project and region.
- **Deploy (`INF-9`):** `deploy.sh` tags the image with the commit (or `<sha>-dirty-<UTC>` with `ALLOW_DIRTY=1`;
  otherwise uncommitted build inputs stop it), no longer pushes `:latest`, and registers a revision for that image.
  It moves the service to the new revision and, if the service doesn't stabilize, back to the one it ran before.
  `deploy.sh --plan` is read-only: it diffs the running revision against the rendered one (image, roles, env, secret
  ARNs, health check) and stops. Environment values whose name looks like a secret are masked in the diff.
- **SSM (`INF-10`, `INF-20` partial):** `setup.sh` creates any of the six parameters that is missing and never
  overwrites one: `google-client-id` as `String` from `config.env`, `cf-origin-secret` as a generated `SecureString`
  (piped in, never in argv or output), `agent-arn-*` from each AgentCore project's `deployed-state.json`.
  `teardown.sh` deletes all six plus the legacy `agent-runtime-arn`.
- **Task role (`INF-11`):** `backend/ecs/task-role-policy.json` grants object access only under `users/*` in the four
  buckets, `ListBucket` only for that prefix, and `InvokeAgentRuntime` on the four runtime ARNs and their endpoints
  (`/*`). `BedrockInvokeLegacy` (`bedrock:InvokeModel` on `*`) and `GetBucketLocation` are gone. The edge's S3 calls
  were checked: every key it reads, writes, lists or deletes is under `users/{user_id}/`.
- **Partial (`INF-13`, `INF-15`, `INF-16`):** `setup.sh` refuses to run if the project's VPC exists, but it still
  can't resume a half-finished run. `setup-https.sh` takes its domains from `config.env`, but still waits for ACM with
  `sleep 5`. `teardown.sh` waits for the ALB to be deleted instead of `sleep 30`, but still leaves the certificate and
  the Route 53 records.
- **Dead settings (`API-9`):** `S3_BUCKET_NAME`, `AGENT_RUNTIME_ARN`, `BEDROCK_MODEL_ID` and `BEDROCK_REGION` were
  removed from `backend/app/config.py`, which nothing read, and their entries from the task definition.
- **Verified:** edge 62 passed (12 new in `backend/tests/test_deploy_helpers.py`: both templates render from
  `config.env` alone, also through `lib.sh`; no localhost or old bucket; the policy names only the four buckets and
  runtimes; diff and masking). `bash -n` passes on all five scripts. The guards were run offline: with no
  `AWS_PROFILE`, `deploy.sh --plan` and `setup.sh` stop before any AWS call. `shellcheck` is not installed. **Nothing
  ran against AWS.**
- **D7 evidence (still open):** see §10.

### 2026-10-26 — No identity, keys or reply text in edge or agent logs (`NEW-5`); committed in `8928e1d`
- **Done:** the edge names a user in logs only by `user_log_id` (`backend/app/auth.py`), the same 12-character
  SHA-256 prefix as the agent's `_log_id`, so lines correlate. `backend/app/routes/meals.py` no longer logs the user
  id or object keys (a meal key also holds the user-typed meal name); `backend/app/agent_client.py` logs a malformed
  reply's size, not its text. The audit for the fix found two agent leaks of the same kind, also fixed: the
  oversize-image error named the object key (it reached both logs through `str(e)`), and the no-JSON warning logged
  160 characters of the model's description of the photo
  (`backend/agent/app/nutrasmart_agent/food_scan/analysis.py`). Copied to the four AgentCore projects; all five
  trees identical.
- **Verified:** edge 50 passed (6 new in `backend/tests/test_log_privacy.py`); agent 73 passed, 2 skipped (2 new in
  `food_scan/tests/test_log_privacy.py`). Each new test leaks the identifier through the path it covers and asserts
  it is absent from the log or the error text.
- **Docs:** the audit-trail rule in `.claude/CLAUDE.md` §4 now states the rule and names the two hash helpers.

### 2026-10-26 — `.claude/CLAUDE.md` matches Phase 0 (R6, `NEW-3`, `NEW-5`); committed in `5eff3ff`
- **Done:** rewrote the rule text that still described `API-43`, `API-45`, `API-47`, `AGT-44`, `WEB-19`, `WEB-26`
  and `WEB-27` as open: each now names where the rule is enforced. Kept the gaps that are still open (`AGT-30`,
  `API-44`, `API-53`, the chat/summary output boundary). Added `uploads/` and `meals/` to the tenant layout and the
  legacy `{email}/` uploads to the erasure rule. Moved the grounding commit to `46d590e`, with a note that production
  keeps the old gaps until deployed. Every symbol the new text cites was checked to exist in the code.
- **Found:** `NEW-5` (§8): the edge still logs full user ids and object keys in `meals.py`.

### 2026-10-26 — Agent copies synced, root Node files deleted, D3 answered (`INF-21`, R1, D3); committed in `bda9d6b`
- **Done:** copied the six changed agent files and `.dockerignore` from the canonical package into the four
  AgentCore projects (`backend/agent/NutrasmartAgent/` and `backend/agent/regions/NutrasmartAgent-{ca,eu,in}/`, each
  under `app/NutrasmartAgent/`, the projects' `codeLocation`). Before copying, all four matched the canonical package
  at `26eecb6` byte for byte, so no copy held work of its own; afterwards `diff -r` shows all five trees identical.
  Deleted the root `package.json` (`{}`) and `package-lock.json` (no packages); the deletion is left unstaged.
- **Decided:** D3 = (b): heart rate plus BP and SpO2, with BP/SpO2 flagged experimental. `API-48` stands as built.
- **Not verified:** whether the AgentCore CLI uploads dotfiles with `codeLocation`, and so whether the copies'
  `.dockerignore` reaches the Docker build (Docker applies it whenever it sits at the context root).

### 2026-10-26 — Phase 0 implemented (`API`, `AGT`, `WEB`, `INF` items in §3); committed in `46d590e`
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
| `API-43` | High | `hmac.compare_digest`; exempt origins from settings, empty by default | done; the demo origin is set in `backend/ecs/config.env` until CloudFront is back | `backend/app/main.py:38`, `ORIGIN_VERIFY_EXEMPT_ORIGINS` in `backend/app/config.py` and `backend/ecs/config.env` |
| `API-45` | Med | Presign key from the verified user, under `users/{user_id}/uploads/`; body `email` ignored | done | `backend/app/routes/upload.py:48`, `backend/app/user_keys.py:19` |
| `API-47` | Med | Unconfigured region → `RegionNotConfigured` → 503; no fallback, no bucket defaults | done | `backend/app/regions.py:73`, `backend/app/main.py:55`, `backend/app/agent_client.py:78` |
| `API-48` | Med | `FaceScanResponse` whitelist; BP/SpO2 always `experimental: true` | done; D3 = (b) confirmed 2026-10-26 | `backend/app/routes/facescan.py:63` |
| `API-49` | Med | Require `email_verified is True`; missing e-mail → 401 | done | `backend/app/auth.py:48` |
| `API-41` | Low | Pin `boto3` | partial: pinned to 1.43.119; lock file left for Phase 3 tooling | `backend/requirements.txt:3` |
| `API-8` † | Low | Demo origin as a setting, not a constant in `main.py` | done | `ORIGIN_VERIFY_EXEMPT_ORIGINS` in `backend/app/config.py` |
| `API-12` † | Low | Health-check probe with `timeout=` (Dockerfile and the task definition, which overrides it) | done | `backend/Dockerfile:23`, `backend/ecs/task-definition.json:65` |
| `API-15` † | Med | One `user_id_from_email` instead of six copies | done | `backend/app/auth.py:26` |
| `API-18` † | Low | Runtime ARN resolved once in `get_data_context`; `invoke_agent` requires it | done | `backend/app/agent_client.py:78` |
| `INF-17` † | Low | Backend image copies only `app/`; `.dockerignore` excludes venvs, tests, docs, `.env.*` | done | `backend/Dockerfile:14`, `backend/.dockerignore` |
| `AGT-8` | High | `main.py` uses food_scan's clients (timeouts, retries) instead of bare import-time clients | done | `backend/agent/app/nutrasmart_agent/main.py:266` |
| `AGT-9` | Med | Strands `BedrockModel` gets `boto_client_config` and `chat_max_tokens` | done | `backend/agent/app/nutrasmart_agent/main.py:279` |
| `AGT-10` | Med | Face-scan model-bucket client gets timeouts from settings | done | `backend/agent/app/nutrasmart_agent/face_scan_biomarkers/services.py:75` |
| `AGT-36` | High | `evaluate_classifier.py` puts `backend/agent` on `sys.path` (`parents[4]`) | done; moving the scripts to `tools/` goes with the Phase 1 layout | `backend/agent/app/nutrasmart_agent/food_scan/scripts/evaluate_classifier.py:37` |
| `AGT-37` | Med | Agent `.dockerignore` (env, venvs, tests, scripts, copies) | done in all five build contexts (copies synced 2026-10-26) | `backend/agent/.dockerignore` and each project's `app/NutrasmartAgent/.dockerignore` |
| `AGT-38` | Med | Pin `opencv-python-headless` and `boto3` | partial: both pinned; lower-bound pins, duplicate `pytest` pin and per-target lock left for Phase 1 | `backend/agent/requirements-base.txt:4`, `:18` |
| `AGT-44` | High | Agent refuses any key outside `users/{user_id}/` (and `..` segments) | done | `backend/agent/app/nutrasmart_agent/main.py:58`, `:341`, `:369` |
| `WEB-5` | High | S3 PUT under a deadline with a readable timeout message | done | `maitribot/client/src/api.js:82`, `maitribot/client/src/config.js:19` |
| `WEB-7` † | Low | Request timeouts in `src/config.js` instead of inline literals | done | `maitribot/client/src/config.js:12` |
| `WEB-19` | Med | 401/403 clears the token and returns to the login gate | done | `maitribot/client/src/api.js:14`, `maitribot/client/src/App.jsx:352` |
| `WEB-26` | High | `**bold**` rendered as React nodes; no `dangerouslySetInnerHTML` | done | `maitribot/client/src/App.jsx:141`, `:298` |
| `WEB-27` | High | `X-Origin-Verify` no longer sent by the client | done; absent from a production build | `maitribot/client/src/api.js:18` |
| `INF-21` | Med | Delete the vestigial root `package.json` (`{}`) and `package-lock.json` | done (2026-10-26) | both files deleted |
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
| `INF-9` | High | `deploy.sh` registers SHA-tagged task-definition revisions; real rollback | done (2026-10-27); `--plan` diffs against the live revision |
| `INF-10` | High | `setup.sh` creates, and `teardown.sh` deletes, all seven SSM parameters | done (2026-10-27); six now, `agent-runtime-arn` dropped (`API-9`) and deleted by teardown |
| `INF-11` | Med | Task-role policy built from the region list; drop `BedrockInvokeLegacy` | done (2026-10-27) in `task-role-policy.json`; not applied to the live role (R7) |
| `INF-12` | Med | One `ecs/config.env` sourced by all four scripts | done (2026-10-27), through `backend/ecs/lib.sh` |
| `INF-13` | Med | `setup.sh` idempotent (look up or create), or move ECS to CDK | partial: refuses to run when the VPC exists; no resume |
| `INF-14` | Med | One credential convention (`AWS_PROFILE`) | done (2026-10-27); every script checks the account |
| `INF-15` † | Low | `setup-https.sh`: domain as a parameter, poll ACM instead of `sleep` | partial: domains from `config.env`; `sleep 5` left |
| `INF-16` † | Low | `teardown.sh` waits on the ALB and removes cert, records, all SSM params | partial: waits on the ALB, deletes all SSM params; cert and records left |
| `INF-18` † | Med | `task-definition.json`: region and origins as parameters, no localhost in prod | done (2026-10-27) |
| `INF-20` † | Low | Google client ID as a plain `String` parameter; `cf-origin-secret` as SecureString | partial: new parameters get these types; the live `google-client-id` is never overwritten, so it stays `SecureString` |
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
| `API-9` † | Low | Delete dead settings and their task-definition entries | done (2026-10-27): `S3_BUCKET_NAME`, `AGENT_RUNTIME_ARN`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION` |
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
| `INF-19` † | Med | Edge code defaults that point at the old account | partial: bucket defaults removed, Bedrock constants and `S3_BUCKET_NAME` deleted (2026-10-27, `API-9`); Google client ID literal and demo origins left |
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
| `NEW-2` | Med | Legacy `{email}/` uploads covered by erasure, or moved under `users/{user_id}/uploads/` (§8) | to do |
| `NEW-5` | Med | No user ids, object keys or reply bodies in edge logs (§8) | done (2026-10-26) |

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
| `NEW-3` | Low | ~~The tenant layout in `.claude/CLAUDE.md` §4 lists `scans/`, `vitals_scans/`, `weekly_summary.txt` and `health_profile.json`, but not `users/{user_id}/meals/` (`backend/app/routes/meals.py:85`) or the new `users/{user_id}/uploads/`.~~ Done 2026-10-26: both prefixes added. | — |
| `NEW-5` | Med | ~~The edge still logs identity and payload: `backend/app/routes/meals.py:106`, `:159`, `:171` and `:384` put the full `user_id` or a `users/` object key in the message, and `backend/app/agent_client.py:132` logs up to 500 characters of a non-JSON agent reply, which can hold analysis content. `.claude/CLAUDE.md` §4 forbids both. Found 2026-10-26 while checking the audit-trail rule.~~ Done 2026-10-26, together with two agent leaks of the same kind in `food_scan/analysis.py` (§2). | 2 |
| `NEW-4` | Info | At `26eecb6` food_scan has 60 tests plus 2 opt-in skips, not the 50 the review counted, and `backend/agent/venv_agent` (uv, Python 3.12) replaces the broken `.venv` the review could not run. | — |

## 9. Rollout notes: what has to happen before Phase 0 is live

- **R1. Agent copies: done 2026-10-26.** The four AgentCore projects build from their own copies of the package.
  The changed files and `.dockerignore` were copied into all four (§2), so a deploy of any region now ships the
  Phase 0 agent fixes. Until Phase 1 collapses the copies, every agent change has to be copied to all four again.
- **R2. Deploy the edge before the agent and before the client.** The new agent refuses the `{email}/...` keys the
  old edge produces. The new client no longer sends `email`, which the old edge's presign model requires (422). The
  new edge accepts both old and new clients, because it ignores the extra `email` field.
- **R3. The edge needs a new task-definition revision: addressed 2026-10-27 (not deployed).** The old `deploy.sh`
  only pushed `:latest` and forced a new deployment, so the live task still runs the revision `setup.sh` or a person
  registered (`INF-9`). The new `deploy.sh` registers a revision on every deploy. Its `--plan` diff answers the two
  questions this note used to ask: (a) does the live revision set `BUCKET_US/IN/CA/EU` (there are no code defaults
  any more, and a missing bucket answers 503), and (b) does it set `ORIGIN_VERIFY_EXEMPT_ORIGINS`.
- **R4. Local edge runs need `BUCKET_*`.** `backend/.env` has no `BUCKET_*` lines and used to fall back to the old
  `sci-neutrasmart-project*` names; it now answers 503 for every user route. Add the buckets
  (`backend/.env.example` lists every variable).
- **R5. Direct-to-ALB local testing.** `MIGRATION_OUTSTANDING_TASKS.md` (Done list) describes sending
  `X-Origin-Verify` from the client to reach the ALB while CloudFront is blocked. The client no longer sends it. If
  that path is needed again, add the header server-side (a dev proxy), never as a `VITE_*` value.
- **R6. Stale rule text: done 2026-10-26.** `.claude/CLAUDE.md` now names where each Phase 0 fix is enforced and
  keeps only the gaps that are still open (§2). Update it again when a phase closes more of them, and after the
  Phase 0 deploy remove its "until they are deployed" note.
- **R7. First run of the new ECS scripts (2026-10-27; account changed to `209479309679` the same day, D9).** Each
  step below changes AWS and needs the owner's yes.
  - **Profile.** `moxa-dev` (IAM user `mariom` in `209479309679`). `deploy.sh` needs nothing else. Never run
    `setup.sh` there (its guard sees the live VPC and stops), `teardown.sh` (it deletes the live edge) or
    `setup-https.sh` (it would repoint `nutrasmart.in` and `api.nutrasmart.in` at the ALB, around CloudFront).
  - **Read the plan.** `AWS_PROFILE=moxa-dev backend/ecs/deploy.sh --plan` is read-only. Expected from the live
    revision `nutrasmart-backend:8` (read 2026-10-27): the image moves from `:1ebc811` to the commit's tag;
    `S3_BUCKET_NAME` and the `AGENT_RUNTIME_ARN` secret are removed; `ALLOWED_ORIGINS` loses the two localhost
    origins. Buckets, roles, the log group and the other five secrets stay the same.
  - **S3 demo build: resolved 2026-10-27.** The live revision sets no `ORIGIN_VERIFY_EXEMPT_ORIGINS`, and CloudFront
    adds `X-Origin-Verify` in this account, so `config.env` leaves it empty.
  - **Task-role policy: don't apply yet.** `deploy.sh` doesn't touch IAM. `documents/DATA_RESIDENCY.md` §4 says the
    live role already grants S3 on the four buckets and `InvokeAgentRuntime` in the four regions (not read from AWS).
    The rendered `task-role-policy.json` would need the old runtimes' ARNs, which live in that account's SSM, not in
    the repo's `deployed-state.json` files; `export_runtime_arns` now refuses the repo's ARNs there. Read the live
    policy with `aws iam get-role-policy --role-name nutrasmart-ecs-task-role --policy-name nutrasmart-s3-bedrock`
    before changing it.
  - **SSM.** All six parameters the task definition reads exist in `209479309679` (names and types read 2026-10-27),
    so nothing needs creating. `google-client-id` stays `SecureString` (`INF-20`); `agent-runtime-arn` stays until
    teardown.
- **R8. The old account's agents (2026-10-27).** The four `nutrasmart_agent` runtimes in `209479309679` run a
  container (`nutrasmart-agent:latest` in that account's ECR; read for `us-east-1`), last updated 2026-08-02, with
  role `nutrasmart-agent-runtime-role`. They were built from `backend/agent/Dockerfile` and created by hand; no script
  in the repo deploys them. The repo's AgentCore CLI projects (R1) deploy to `792207721590` and don't apply. Until
  they are rebuilt from `backend/agent/app/nutrasmart_agent/` and updated region by region, they lack the Phase 0
  agent fixes and `face_scan`. Deploy order stays R2: edge first. **How to redeploy them: open.**

## 10. Decisions needed (from the summary's §6)

- **D1. Product slug and renames** (`INF-35`). **Answer:** _open_
- **D2. IAM residency:** one agent policy for four buckets, or rendered per target (`INF-4`). **Answer:** _open_
- **D3. Face-scan contract:** heart rate only, or BP and SpO2 too. **Assumed (b)** for `API-48`: expose all three,
  with BP/SpO2 forced to `experimental: true` plus a disclaimer, because
  `backend/agent/app/nutrasmart_agent/face_scan_biomarkers/__init__.py` records "the product decision was to surface
  all three" and the client renders all three. Choosing (a) means dropping `bp` and `spo2` from `FaceScanResponse`.
  **Answer:** (b), 2026-10-26: show heart rate plus BP and SpO2, BP/SpO2 flagged experimental.
- **D4. In-house `FaceScanModal` and `/facescan/analyze`:** delete, or keep behind a provider flag (`WEB-9`).
  **Answer:** _open_
- **D5. Chat image results:** emit `AnalysisCard` or delete it and its CSS (`WEB-9`, `WEB-32`). **Answer:** _open_
- **D6. `documents/data-flow-diagram.pdf`:** keep in git or build in CI (`INF-23`). **Answer:** _open_
- **D7. AgentCore CLI:** does `deploy` select a target, and may `codeLocation` point outside the project
  (`INF-1`, `INF-2`). **Answer:** _open_ (check with the installed CLI before Phase 1). **Evidence so far
  (2026-10-27, read-only):**
  - A third-party mirror of an AWS agent skill documents `agentcore deploy --target <name> -y` for CLI v0.9.0 and
    later (References). It was not checked against the CLI, which is not installed here.
  - The project schema the CLI generated, `backend/agent/NutrasmartAgent/agentcore/.llm-context/agentcore.ts:48`, has
    `codeLocation` (a directory path) and, for container builds, an optional `buildContextPath` (`:50`). Whether
    either may point outside the project directory is not stated there.
- **D8. `mediapipe==0.10.14` + `numpy==2.0.2` on arm64 / Python 3.12** (`AGT-39`). **Answer:** _open_; works on
  x86_64 / Python 3.12 (FaceMesh pass, 2026-10-26).
- **D9. Which AWS account runs production** (new, 2026-10-27). `documents/MIGRATION_OUTSTANDING_TASKS.md` §5 had
  the old account `209479309679` left untouched and the September copy in `792207721590` taking over, but the cutover
  never happened. **Answer:** 2026-10-27, owner: production stays in `209479309679` and `mariom` deploys it. The
  trade-off: that account is shared with another project. Consequences: R7, R8, and the docs listed in §2.

## What wasn't verified

- Nothing changed in AWS or Google: no deploy, no bucket listing, no real token. On 2026-10-27 the old account was
  read under `moxa-dev` (`describe-*`, `get-*`, `list-*` only, no decryption): Route 53, CloudFront, the ALBs, the
  live task definition, SSM names and types, bucket regions and the agent runtimes. The number of legacy `{email}/`
  uploads (`NEW-2`) is unknown.
- The client was built, not run in a browser; there are no client tests (`WEB-24`).
- The BP and SpO2 bundles' target names are assumed to be `sbp`/`dbp` and `spo2` (what the client reads); the
  trained bundles in the model bucket were not opened.
- The agent image was not built; arm64 wheels are unverified (D8).
- The new ECS scripts (2026-10-27) were checked with `bash -n`, offline runs of their guards and the tests in
  `backend/tests/test_deploy_helpers.py`; `shellcheck` is not installed. None of their AWS calls ran. Three things
  rest on documentation, not on a run:
  - that `register-task-definition` accepts the rendered file;
  - that `InvokeAgentRuntime` is authorized against the runtime and its endpoint (hence the `/*` grants);
  - that the `describe-parameters` name filter matches exactly one parameter.
  Empty environment values are dropped from the rendered task definition, because the ECS documentation found doesn't
  say whether `""` is accepted.

## References

Read 2026-10-27, for the deploy-script track:

- [AgentCore resource-based policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/resource-based-policies.html):
  `InvokeAgentRuntime` is evaluated against both the agent runtime and the endpoint invoked.
- [aws ssm put-parameter](https://docs.aws.amazon.com/cli/latest/reference/ssm/put-parameter.html): `--overwrite`
  defaults to false, and an existing name fails with `ParameterAlreadyExists`.
- [aws ecs wait services-stable](https://docs.aws.amazon.com/cli/v1/reference/ecs/wait/services-stable.html): polls
  every 15 seconds and exits 255 after 40 failed checks.
- [agents deploy (third-party mirror of an AWS agent skill)](https://mcpservers.org/agent-skills/aws/agents-deploy):
  `agentcore deploy --target` (D7).
