# 02 — Backend API (`backend/app`, FastAPI edge)

Read-only review, 2026-10-26. Findings are referenced from the summary as `API-n`. Line numbers refer to the working
tree on `feature/w360-full-multiple-models` with the `feature/w360-full` merge staged.

## Architecture summary

`backend/app` is a thin FastAPI "edge" (1,138 LOC, 12 handlers) that fronts a Strands agent on Bedrock AgentCore.
`main.py` builds the app at import, stacks `OriginVerifyMiddleware` (CloudFront shared-secret gate, with a forgeable
`Origin`-header demo exemption) under `CORSMiddleware`, registers a slowapi `RateLimitExceeded` handler, and mounts six
routers under `/api`. Every protected handler takes `Depends(get_current_user)` (`auth.py`: Google ID-token verify,
returns a loose dict) and `Depends(get_data_context)` (`regions.py`: `CloudFront-Viewer-Country` / `X-User-Country` →
data region → `{region, bucket, s3, agent_arn}` dict with an `lru_cache`d boto3 S3 client). Routes either hit the
regional bucket directly (upload presign, meals CRUD/aggregation, weekly-summary read) or call
`agent_client.invoke_agent(payload_dict, agent_arn=...)`, which picks local HTTP (`AGENT_LOCAL_URL`) or
`bedrock-agentcore.invoke_agent_runtime` (another `lru_cache`d client keyed by the ARN's region), concatenates the
streamed body and `json.loads` it. The agent contract (agent `main.py:4-9,350-362`) is
`{"action": chat|summary|analyze|face_scan, "user_id", ...}` → `{"reply"}` / `{"status":"ok"}` / analysis JSON /
`{"heart_rate","bp","spo2"}`, with failures returned as `{"error": str}` which `_parse_result` turns into `AgentError`.
Config is a flat module (`config.py`) of `os.environ.get` reads with production identifiers as defaults, executed
(plus `load_dotenv()`) at import.

## Findings

### Config / hardcoding

1. **High** · Flat import-time settings with production identifiers as defaults · `config.py:4,6-12,14-24,47-48,54,71,75-79` ·
   `load_dotenv()` runs on import; a real Google client ID, four bucket names, prod/demo origins and regions are
   fallbacks, so a missing env var silently points at production. → Frozen pydantic-settings `Settings` with required
   fields (no prod defaults), loaded once in an app factory and injected via `Depends(get_settings)`.
2. **Med** · Settings read outside the settings layer · `routes/analyze.py:16-17` · `MAX_IMAGES_PER_REQUEST = 5` and
   `MAX_DAILY_UPLOADS = int(os.environ.get(...))` live in a route module. → Move into `Settings`.
3. **Med** · Ten rate-limit strings hardcoded in decorators · `analyze.py:30,76,92`, `chat.py:27`, `facescan.py:22`,
   `meals.py:70,224,270,368`, `upload.py:21` · Limits are policy and should be tunable per environment. → `RateLimits`
   group in `Settings`.
4. **Med** · S3 key layout duplicated between edge and agent · `analyze.py:45,99`, `meals.py:91,161,380`,
   `upload.py:37`; mirrored in agent `main.py:210,218,232` · Six f-string templates of `users/{uid}/...` with no single
   owner; the daily-quota prefix (`analyze.py:45`) depends on the agent's timestamp format (agent `main.py:217`).
   → One key-builder module (`UserKeys.scans_prefix(...)`, `.meal_key(...)`, `.weekly_summary_key(...)`) with a test,
   ideally in a shared contracts package.
5. **Low** · Upload validation literals split across files · `upload.py:33` (eight extension literals) vs
   `config.py:26-38` (content types). → One `UploadKind` enum / `content_type -> allowed_extensions` mapping in settings.
6. **Low** · Protocol/tuning literals in `agent_client` · `:46` `connect_timeout=10`, `:60` `nutrasmart-` prefix,
   `:65,111` `"anonymous"`, `:68` `/invocations`, `:70` header name, `:117` `qualifier="DEFAULT"`, `:138` `[:500]`;
   `facescan.py:44` `facescan-` · Connect timeout and qualifier belong in settings; the rest should be named constants.
7. **Low** · Domain literals inside meals handlers · `meals.py:90` `[:30]`, `229` `Query(100)`, `276` `Query(365)`,
   `243,290` `"UTC"`, `298` `MICRO_KEYS`, `273` `"daily"`, `348-353` period map. → `Period` Enum with a `date_field`
   property, `MICRONUTRIENT_KEYS` domain constant, page limits in settings.
8. **Low** · Demo origin duplicated · `main.py:25` vs `config.py:19`. → `settings.origin_verify_exempt_origins:
   frozenset[str]` (empty by default).
9. **Low** · Dead settings · `config.py:6,7,47,48,53` (`AWS_REGION`, `S3_BUCKET_NAME`, `BEDROCK_MODEL_ID`,
   `BEDROCK_REGION`, `AGENT_RUNTIME_ARN`) and `41-42` (`MAX_IMAGE_SIZE_BYTES`, `MAX_VIDEO_SIZE_BYTES`) referenced
   nowhere in `app/`; `ecs/task-definition.json:21-22,41-42` still injects three of them. → Delete and prune the task
   definition, or wire the size limits (see #46).

### Timeouts

10. **Med** · Regional S3 clients have no explicit botocore `Config` · `regions.py:56`; call sites
    `analyze.py:47,102,103`, `meals.py:105,163,174,383,388` · Eight request-path S3 calls rely on botocore's implicit
    60 s / 60 s defaults and default retries. → `Config(connect_timeout=..., read_timeout=..., retries=...)` from settings.
11. **Med** · Google token verification does an uncached cert fetch per request with library-default timeout ·
    `auth.py:13-17` · A fresh `google.auth.transport.requests.Request()` per call; google-auth refetches certs unless a
    caching session is supplied; the transport default timeout is long. → One transport in the lifespan
    (cachecontrol-wrapped session, explicit timeout from settings), injected.
12. **Low** · Container healthcheck `urlopen` without `timeout=` · `backend/Dockerfile:23`. → Add explicit timeout.

### Structure / separation of concerns

13. **High** · `meals.py` is a god module · `:123-220` (parsing/conversion), `:159-188` (S3 repository),
    `:240-262,297-360` (filtering/aggregation) · Repository, domain conversion, date math, aggregation and routing in one
    392-line file. → `repositories/meal_repository.py`, pure `services/nutrition_aggregator.py` on dataclasses,
    `schemas/meals.py`, thin router.
14. **High** · Business logic in handlers · `analyze.py:44-56` (quota via S3 listing), `:101-111` (summary
    fetch/decoding), `upload.py:28-37` (validation + key generation), `meals.py:240-262,297-360` · Handlers should
    validate → call a service → map to a response. → `services/` (quota, summary, upload) with explicit I/O at the boundary.
15. **Med** · `user_id` derivation copied 6× · `analyze.py:42,82,98`, `chat.py:39`, `facescan.py:29`, `meals.py:63-64` ·
    Same `.replace("@","_at_").replace(".","_")` everywhere. → Frozen `AuthenticatedUser(email, name)` from
    `get_current_user` with a `user_id` property.
16. **Med** · Agent wire format leaks into three routes · `analyze.py:60-67,84`, `chat.py:43-51`, `facescan.py:37-45` ·
    Each hand-builds `{"action": ..., "user_id": ...}`. → `AgentAction` Enum and typed methods on `agent_client`
    (`analyze(user, images)`, `chat(...)`, `summary(...)`, `face_scan(...)`).
17. **Med** · `analyze.py` mixes food analysis with weekly-summary endpoints · `analyze.py:75-111`. → `routes/summary.py`.
18. **Low** · ARN resolution duplicated · `regions.py:61,75` and `agent_client.py:104-108`. → Resolve once into
    `DataContext.agent_arn`; `invoke_agent` takes a required ARN.
19. **Low** · Dead code · `regions.py:59-64` `agent_arn_for_region` never called; `regions.py:24` logger unused;
    `regions.py:44-45` "safety net" unreachable; `analyze.py:102` `head_object` before `get_object` redundant;
    `meals.py:129` function-local `import re`; `testimonials.py:1` unused `HTTPException`. → Delete.
20. **Low** · Static marketing fixture served by the API · `testimonials.py:7-62` · Hardcoded fake people with
    randomuser.me avatars, unauthenticated and unrate-limited. → Frontend static JSON; drop the route.
21. **Low** · Mixed sync/async handlers · `testimonials.py:6` is `async def`; all others sync `def` (correct for
    blocking boto3). → One convention, documented.

### Typing / data models

22. **High** · Loose-dict internal contracts · `regions.py:68-76` (`get_data_context -> dict`, consumed as `ctx["s3"]`
    in every route), `auth.py:18` (`{"email","name"}`), `agent_client.py:80-81` (`payload: dict -> dict`) · No static
    checking of keys. → `@dataclass(frozen=True) DataContext(region, bucket, s3, agent_arn)`, `AuthenticatedUser`,
    per-action TypedDict/dataclass payloads plus typed responses (`ChatReply`, `SummaryAck`, `FaceScanResult`).
23. **Med** · Untyped response bodies · `analyze.py:72,85,105,109`, `chat.py:56`, `facescan.py:50`,
    `meals.py:115,264,362,393`, `upload.py:51` · Ad-hoc dicts or agent JSON passed straight through; OpenAPI is empty.
    → `response_model=` Pydantic models mirroring the agent contract.
24. **Med** · Untyped/unvalidated query params · `meals.py:227-229,273-277` · `period: str` free text;
    `startDate`/`endDate` parsed with `date.fromisoformat` (ValueError → 500 instead of 422); `limit` unbounded;
    `timezone: str` shadows the `datetime.timezone` import (`meals.py:4`). → `period: Period`,
    `start_date: date | None`, `limit: int = Query(..., ge=1, le=settings.max_page)`, rename to `tz_name`.
25. **Low** · camelCase leaks into the API schema · `meals.py:38,53-58,227-228`. → snake_case with `alias=` and
    `populate_by_name=True`.
26. **Low** · Legacy typing and mutable default · `chat.py:4,23` `Optional[List[ChatMessage]] = []`. →
    `list[ChatMessage] = Field(default_factory=list)`, `role: Literal["user","assistant"]`.
27. **Low** · `_parse_result -> dict` is a type lie · `agent_client.py:130-143` · `json.loads` may return a
    list/scalar; only the error branch checks `isinstance`. → Pydantic `TypeAdapter` per action.

### DI / global state

28. **High** · Hidden singletons via `lru_cache` · `regions.py:53-56`, `agent_client.py:39-47` · Module-level caches of
    boto3 clients cannot be swapped in tests without `cache_clear()`. → `AwsClients` provider in a `lifespan`, stored on
    `app.state`, exposed via `Depends`.
29. **Med** · Import-time side effects in config · `config.py:4` (`load_dotenv()`), `:58,63` (`float(os.environ...)`
    crashes at import on bad input). → Load settings inside `create_app()`; pydantic-settings owns `.env` and validation.
30. **Med** · No app factory · `main.py:15-71` · `app`, middleware and routers assembled at import. → `create_app(settings) -> FastAPI`.
31. **Low** · `limiter` module singleton · `limiter.py:4`, `main.py:16`. → Build inside `create_app`; storage from settings (#44).
32. **Low** · `security = HTTPBearer()` and `GOOGLE_CLIENT_ID` bound at import · `auth.py:6-8` · Acceptable idiom,
    but the audience should come from injected settings.

### Logging / errors

33. **Med** · No logging configuration; f-string logging · no `basicConfig`/`dictConfig` anywhere;
    `meals.py:112,165,177,390` use f-strings · No `user_id`/`region`/`request_id` context. → Structured (JSON) logging
    configured in the lifespan; lazy `%s`/`extra={...}`.
34. **Med** · Broad `except Exception` swallowing · `analyze.py:55-56` (`pass`), `:106-111`,
    `meals.py:111,164,176,219,384,389`, `auth.py:19`, `agent_client.py:54` · Google outages become 401; S3 403/timeouts
    become "no summary yet" or 404. → Catch `botocore ClientError`, branch on `Error.Code`; let unexpected errors reach
    a global handler.
35. **Med** · Bare `HTTPException` everywhere; one domain error type · `analyze.py:38,40,49,70,88`, `chat.py:54`,
    `facescan.py:48`, `meals.py:83,86,113,385,391`, `upload.py:30,35`; only `AgentError` (`agent_client.py:35`) ·
    → `QuotaExceeded`, `UploadNotAllowed`, `MealNotFound`, `StorageError`, `RegionNotConfigured`, `AgentUnavailable`
    in their owning packages, mapped in one `@app.exception_handler`.
36. **Low** · Inconsistent error exposure and status codes · `analyze.py:70,88`, `facescan.py:48` interpolate raw
    `AgentError` text (which is `str(e)` of agent-side exceptions) into `detail`; `chat.py:54` hides it; summary
    failure is 500 while identical agent failures are 502. → Generic message, log detail with a correlation id, one
    mapping (502/504).
37. **Low** · Double logging · `agent_client.py:75,120` log then raise; routes log again (`analyze.py:69`, `chat.py:53`,
    `facescan.py:47`). → Log once where the error becomes HTTP.

### Docs / tests / consistency

38. **High** · No tests for `backend/app` (confirmed) · the only tests in the repo are the agent's
    `food_scan/tests/`; no `pyproject.toml`, ruff, mypy or pytest config; `requirements.txt` has no dev deps. →
    `backend/pyproject.toml` (ruff, mypy, pytest) and `backend/tests/` using `TestClient` + `app.dependency_overrides`
    for `DataContext`/`AgentClient`; first targets: region resolution, auth → user_id, presign validation, meals
    aggregation (pure), `_parse_result`.
39. **Med** · Missing docstrings · 11 of 13 modules lack a module docstring (only `regions.py`, `agent_client.py`);
    22 functions lack docstrings incl. every handler in `analyze.py`, `chat.py`, `facescan.py`, `upload.py`,
    `main.py:31,46,62`, `auth.py:11`. → Add; enable ruff `D` rules.
40. **Low** · Inconsistent typing/formatting · `from __future__ import annotations` in two files only;
    `typing.List/Optional` vs builtins; missing return annotations (`main.py:62`, `agent_client.py:40`, all handlers);
    `logger = ...` between imports (`analyze.py:5`, `facescan.py:4`, E402). → ruff + mypy in CI.
41. **Low** · Dependency pinning · `requirements.txt:3` `boto3>=1.40.0` open lower bound while the rest are `==`; no
    lockfile; pydantic unpinned. → Pin or adopt a lock (`uv` / `pip-tools`).
42. **Low** · Dockerfile/.dockerignore · `Dockerfile:14` `COPY . .`; `.dockerignore:9` lists `.venv/` but README refers
    to `backend/venv_backend`; no `PYTHONUNBUFFERED`/`PYTHONDONTWRITEBYTECODE`; port 8000 repeated three times. →
    `COPY app/ ./app/`, add `venv*/`, `*.md`, `tests/` to `.dockerignore`, `ARG` for the port.

### Security / correctness smells

43. **High** · CloudFront gate bypassable by forging `Origin` · `main.py:25,34-35` · Any client sending
    `Origin: http://maitribot-demo-ui…` skips the shared-secret check; `main.py:37` compares the secret with `!=`.
    → Time-box the exemption, drive it from settings (empty in prod), `hmac.compare_digest`.
44. **High** · Rate limiting keyed on proxy IP with per-task memory · `limiter.py:4`, `Dockerfile:25` (uvicorn without
    `--proxy-headers`/`--forwarded-allow-ips`) · Behind CloudFront/ALB `request.client.host` is the proxy, so all users
    share one bucket; in-memory storage is not shared across 1–4 Fargate tasks. → Key on the authenticated user (or
    trusted `X-Forwarded-For`) with shared storage from settings.
45. **Med** · Presign trusts client-supplied `email` for the key prefix · `upload.py:17,37` · The authenticated `_user`
    is ignored; `email` is unvalidated (may contain `/`, `..`, spaces). → Derive the key from `AuthenticatedUser.user_id`;
    drop `email` from the request (client `api.js:52-57` must follow).
46. **Med** · No upload size cap · `config.py:41-42` defined but unused; presigned `put_object` cannot enforce size. →
    `generate_presigned_post` with `content-length-range`, or `head_object` the size in `/analyze` before invoking the agent.
47. **Med** · Silent cross-region fallback breaks data residency · `regions.py:50,61,75`, `agent_client.py:104-108` ·
    A region with no ARN/bucket is routed to the default region without error or log, contradicting
    `documents/DATA_RESIDENCY.md`. → Fail closed with `RegionNotConfigured` → 503; log the region.
48. **Med** · Face-scan route leaks BP/SpO2 despite its comment · `facescan.py:31-32` says only heart rate is exposed,
    but `:50` returns the agent payload wholesale (incl. `bp`, `spo2`, agent `face_scan_biomarkers/analysis.py:48-81`).
    → `FaceScanResponse` `response_model` that whitelists `heart_rate` (or decide to expose all three; see summary §6).
49. **Med** · `email_verified` not checked; `payload["email"]` KeyError collapses to 401 · `auth.py:13-18`. → Require
    `payload.get("email_verified") is True`; `clock_skew_in_seconds` from settings.
50. **Low** · CORS `allow_headers=["*"]`, six default origins incl. plain-HTTP S3 website · `main.py:53-58`,
    `config.py:14-24`. → Enumerate headers; prod origins only via env.
51. **Low** · Daily quota check cannot exceed one page · `analyze.py:47` `KeyCount` capped at 1000 per
    `list_objects_v2` page, so `MAX_DAILY_UPLOADS` > 1000 never trips; failures hit `pass` at `:56` with no log.
    → Paginator or counter object; log on failure.
52. **Low** · `_parse_logged_at` discards real offsets · `meals.py:217` `.replace(tzinfo=timezone.utc)` on ISO strings
    that already carry an offset. → Only set tz when `dt.tzinfo is None`.
53. **Low** · `X-User-Country` override honoured in production · `regions.py:40-42` · Any client can choose its data
    region/bucket. → Gate behind `settings.allow_country_override` (dev only) or ignore when `CF_ORIGIN_SECRET` is set.
54. **Low** · Full-prefix scan per request · `meals.py:159-188` · Every `GET /meals` and `/nutrition/summary` lists and
    serially GETs all meals and scans (no pagination, no `MaxKeys`). → Repository with pagination and date-prefixed
    keys (`meals/YYYY/MM/`) so date filters become prefix queries.

## Quick wins vs structural changes

**Quick wins (hours)**
- Delete dead settings (#9), `agent_arn_for_region`, unused logger/imports; fix E402 logger placement (#19, #40).
- `AuthenticatedUser` dataclass with `user_id`; replace six copies (#15, #22). `DataContext` frozen dataclass (#22).
- Explicit botocore `Config` on the S3 client; cached transport + explicit timeout for Google certs (#10, #11).
- Move `MAX_IMAGES_PER_REQUEST`, `MAX_DAILY_UPLOADS`, rate-limit strings, extension map, demo origin into config (#2, #3, #5, #8).
- `hmac.compare_digest`; `email_verified` check; drop `email` from presign body (#43, #49, #45).
- `response_model`s incl. a `FaceScanResponse` whitelist (#23, #48).
- `Period` Enum and typed/validated query params; f-string → lazy logging (#24, #33).
- Pin boto3; add `pyproject.toml` with ruff/mypy/pytest (#41, #38).

**Structural (days)**
- pydantic-settings `Settings` + `create_app(settings)` + lifespan-owned AWS clients via `Depends`; remove `lru_cache` singletons (#1, #28–31).
- Typed `AgentClient` (Protocol + implementation) with per-action methods, `AgentAction` Enum, typed payload/response models; fail-closed region resolution (#16, #22, #27, #47).
- Split `meals.py` into repository / aggregator service / schemas; extract quota, summary and upload services (#13, #14, #17, #54).
- Domain error hierarchy with one exception handler; structured JSON logging with request/user/region context (#33–37).
- Rate limiter keyed on user with shared storage and proxy-header configuration (#44).
- Test suite via `dependency_overrides` (#38).

## Metrics

- **LOC per file:** `main.py` 71 · `config.py` 101 · `auth.py` 20 · `limiter.py` 4 · `regions.py` 76 ·
  `agent_client.py` 143 · `routes/analyze.py` 111 · `routes/chat.py` 56 · `routes/facescan.py` 50 ·
  `routes/meals.py` 392 · `routes/testimonials.py` 63 · `routes/upload.py` 51 · two empty `__init__.py` · **total 1,138**.
- **Route handlers:** 12 (11 under `/api` + `/health`), 1 middleware, 1 exception handler. 11 sync, 1 async.
- **Hardcoded literals outside `config.py`:** ≈46 (10 rate-limit strings, 4 action strings, 6 S3 key templates,
  8 file extensions, 2 page-limit defaults, 2 `"UTC"`, `MICRO_KEYS`, period map, `connect_timeout=10`, `qualifier`,
  header name, `/invocations`, 2 `"anonymous"`, 2 session prefixes, demo origin, `MAX_IMAGES_PER_REQUEST`,
  `MAX_DAILY_UPLOADS` env read, `[:30]`, `[:500]`, error-code tuple); plus 16 production identifiers baked as
  defaults inside `config.py`; 7 dead settings.
- **I/O calls without explicit timeout:** 10 — 8 S3 call sites through `regions.py:56` (`analyze.py:47,102,103`;
  `meals.py:105,163,174,383,388`), 1 Google cert fetch (`auth.py:13`), 1 Dockerfile healthcheck (`Dockerfile:23`).
  Explicit timeouts exist on `agent_client.py:46` (AgentCore) and `:71` (local `requests.post`).
- **Tests:** 0 (confirmed).
