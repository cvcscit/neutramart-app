# NutraSmart security, privacy and AI-governance rules (CLAUDE.md)

NutraSmart stores food photos, face-scan videos, vitals and health profiles for individual users under the regulatory
frameworks the owner has committed to: **ISO/IEC 27001:2022**, **SOC 2 Type II**, **ISO/IEC 42001:2023**, **GDPR**,
**PIPEDA** and **HIPAA**. Every code, configuration and infrastructure change must follow the rules below. Each rule
names where it is enforced in this repository today and, where the 2026-10-26 review found a gap, the finding ID in
`documents/notes/00-refactoring-review-summary.md` and its parts (`API-n` edge, `AGT-n` agent, `WEB-n` client,
`INF-n` infrastructure). Grounded in commit `0f88514` on `dev`, 2026-10-26.

The system: a React client (`maitribot/client`) → CloudFront → FastAPI edge (`backend/app`, ECS Fargate in
`ap-south-1`) → one Bedrock AgentCore runtime per data region (`backend/agent/app/nutrasmart_agent`) → that region's
S3 bucket and Bedrock. There is no database and no ORM: all user data is JSON and media objects in S3.

---

## 1. Core engineering guardrails (ISO 27001 / SOC 2)

- **Secrets.** Never hardcode a secret, token, key, account ID, bucket, ARN or model ID. Locally they come from the
  gitignored `backend/.env`, `backend/agent/.env` and `maitribot/client/.env.local`; in ECS from SSM parameters under
  `/nutrasmart/` injected through the task definition's `secrets` block; in AgentCore from `agentcore.json` env vars
  (never a secret there). Both services run on IAM roles (`nutrasmart-ecs-task-role`, the runtime role), never access
  keys. The only real secret is `CF_ORIGIN_SECRET`; it must never reach the client bundle (`WEB-27` ships it as
  `VITE_ORIGIN_VERIFY_SECRET`). Production identifiers must not be code defaults (`API-1`, `AGT-1`).
- **Object keys instead of queries.** Every S3 key is built from the identity verified by `get_current_user`
  (`backend/app/auth.py`), never from a request body or a payload field, and always under that user's prefix (§4).
  Never pass a client-supplied key to `get_object` without checking the prefix. Known gaps: the presign route builds
  the key from the body's `email` (`API-45`, `backend/app/routes/upload.py`) and the agent fetches any `key` or
  `images[].key` it is handed (`AGT-44`, `_handle_analyze`, `_handle_face_scan`).
- **Cross-site scripting.** React escapes by default; never render backend or model text through
  `dangerouslySetInnerHTML`. `WEB-26` does exactly that for chat replies in `App.jsx`; remove it or sanitize first.
- **Secure defaults.** CORS origins come only from `ALLOWED_ORIGINS` in `backend/app/config.py` and must not include
  localhost or demo origins in production (`INF-18`). `OriginVerifyMiddleware` in `backend/app/main.py` rejects
  requests that don't carry `X-Origin-Verify`; its `DEMO_ORIGIN_EXEMPT` carve-out is temporary (`API-43`) and must go
  when CloudFront is restored. Presigned uploads keep the content-type and extension allowlists and
  `PRESIGN_EXPIRY_SECONDS`. Buckets block public access (`documents/DATA_RESIDENCY.md` §4).

## 2. Identity, session and access control

- **Least privilege.** New grants name exact actions on exact ARNs: the four `w360-nutrasmart-*` buckets, the four
  regional runtime ARNs, the model bucket read-only. The runtime policy's `bedrock:InvokeModel` and marketplace
  wildcards are known debt (`INF-34`); don't add to them.
- **Every endpoint authenticates.** Every route under `/api` takes `Depends(get_current_user)` (Google ID token,
  verified on every request) and `Depends(get_data_context)` (`backend/app/regions.py`), and a `@limiter.limit(...)`
  rate. The only public paths are `/health` and `GET /api/testimonials`; adding another needs the owner's explicit
  request and a comment saying why. The agent trusts only the `user_id` the edge sends, never one from a client.
- **Sessions.** There is no server session: the Google ID token is verified per request and expires on Google's
  schedule. The client stores it in `localStorage` (`auth_token`), checks `exp` on load and removes it on logout; it
  must also clear it on any 401/403 (`WEB-19`). Never extend token lifetime or cache a verification result.
- **Rate limiting** is keyed on the remote address (`backend/app/limiter.py`); behind CloudFront and the ALB that is
  the proxy, so limits are shared by all users and per task (`API-44`). Key on the verified user instead when fixing it.

## 3. Change management and code quality

- **Errors.** Clients get a generic message and a status code; the stack trace goes to the server log only. Today the
  agent returns `{"error": str(e)}` from `invoke` and the edge re-raises it as the HTTP `detail` (`AGT-30`, `API-36`),
  so botocore, torch and MediaPipe messages reach the browser. New code must not repeat this; fix it when touching
  those paths.
- **Dependencies.** Pinned in `backend/requirements.txt`, `backend/agent/requirements*.txt` and
  `maitribot/client/package-lock.json`; ECR scans every pushed image (`setup.sh`, `scanOnPush`). Add a dependency only
  through the package manager after checking it is maintained and free of known high or critical vulnerabilities.
- **Tests.** Edge code gets tests in `backend/tests/` (none exist yet) with FastAPI's `TestClient` and
  `dependency_overrides`; agent code gets tests next to its package, as `food_scan/tests/` does, or in
  `backend/agent/tests/`. Every new route, service or utility ships with a happy-path test and an error-path test.

## 4. Privacy and healthcare governance (GDPR / PIPEDA / HIPAA)

- **Tenant isolation is a key prefix and a region.** A user's records live at `users/{user_id}/scans/`,
  `users/{user_id}/vitals_scans/`, `users/{user_id}/weekly_summary.txt` and `users/{user_id}/health_profile.json`
  in the bucket of the region `resolve_region` picked for them; uploads must move under the same prefix (`API-45`).
  Every read, write, list and delete names that prefix; the chat tools are bound to one `user_id` for the same reason.
- **Anonymization before analysis or export.** Nothing in the repo exports user data today; if an export, dataset or
  analytics job is added, it must strip the user id (derived from the e-mail), object keys under `users/`, images,
  videos and free text before anything leaves the regional bucket. The agent's `food_analysis` log line is the
  pattern: scores and labels, no identity.
- **Audit trail.** Target: CloudTrail data events on the four buckets, retained outside the application's control;
  nothing in the repo configures this yet. Until then every read or write under `users/` logs one structured line
  with the action, region, timestamp and a truncated user id, never the payload. The edge log group keeps 30 days
  (`setup.sh`). Don't log e-mails or full user ids in clear (`main.py` does in `_handle_summary` and `_handle_analyze`).
- **Right to be forgotten.** Erasure means deleting the whole `users/{user_id}/` prefix and the user's uploaded
  objects in their regional bucket, their client-side `localStorage` and `sessionStorage` entries, and any log line
  carrying their id, in one automated job. No such job exists; `DELETE /api/meals/{meal_id}` removes one record.
- **Data residency.** `COUNTRY_REGION` → `REGION_BUCKETS` and `REGION_AGENT_ARNS` in `backend/app/config.py` bind a
  user to one region for storage and processing (`documents/DATA_RESIDENCY.md`). Unknown countries fall to
  `DEFAULT_DATA_REGION` by design; a *mapped* region with a missing ARN or bucket must fail, not fall back
  (`agent_arn_for_region` falls back today, `API-47`). Canada runs Amazon Nova Lite because no Anthropic model is
  Canada-resident; keep that per-region model choice in the runtime's settings.
- **Consent.** The client has no consent step today. Any profile, onboarding or data-collection feature must record
  explicit, granular consent before collecting or activating it.

## 5. AI management (ISO/IEC 42001)

- **No training on user data.** The classifier checkpoints are read-only from the model bucket
  (`biomarker-processing/models/*`); the runtime role has `GetObject` there and nothing else. User uploads, chat
  history and scan records must never feed a training or fine-tuning set unless the user opted in and the data went
  through the anonymization step above. There is no such pipeline in the repo.
- **Transparency and lineage.** Every scan record already carries a `recognition` block (`_recognition_block` in
  `food_scan/analysis.py`: order, source, model, scores, thresholds) and a timestamp. It must also carry the Bedrock
  model ID (`settings.bedrock_model_id`), the inference parameters and a hash or version of the prompt, so a result
  can be reproduced. The same applies to chat and summary outputs (`_save_summary` stores only text today).
- **Automated decisions (GDPR Art. 22).** The app returns nutrition estimates and vitals; `bp` and `spo2` are
  experimental and must stay flagged as such (`face_scan_biomarkers/__init__.py`). No feature may score, restrict or
  assess a user automatically without a human-review path and an explanation the user can read.
- **Output validation.** Model output passes a programmatic boundary before it reaches the client: for food
  analysis that is `extract_json`, `_parse_or_graceful`, `_llm_says_no_food` and `_backfill` in
  `food_scan/analysis.py`, which force the schema and a graceful no-food result. Chat replies (`str(result)` in
  `_handle_chat`) and summaries have no such boundary yet and are rendered as HTML by the client (`WEB-26`): validate
  structure and escape text before any new model output is shown.
