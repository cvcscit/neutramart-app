# Refactoring review — summary and roadmap

**Date:** 2026-10-26
**Scope:** whole repository, read-only. No code was changed.
**Tree reviewed:** working tree on `feature/w360-full-multiple-models` (HEAD `e125b10`) with the merge of
`feature/w360-full` (`86f4131`) staged but **not yet committed** at review time.
**Method:** four parallel area reviews (repo layout/infra, FastAPI edge, AgentCore agent, web client), each graded
against the owner's coding rules (settings layer, timeouts, separation of concerns, typed contracts, no import-time
init / DI, structured logging and owned error types, docstrings, tests, YAGNI). High-severity claims were spot-checked
against source. The agent test suite could **not** be run: `backend/agent/.venv` points at a Python 3.12 interpreter
that no longer exists on this machine.

Detail files (one per area, findings keep their original numbering and are referenced below as `INF-n`, `API-n`,
`AGT-n`, `WEB-n`):

| File | Area | Findings |
|---|---|---|
| [01-repo-layout-and-infra.md](01-repo-layout-and-infra.md) | duplication, AgentCore layout, ECS scripts, hygiene, docs, IAM, naming | 35 (5 High) |
| [02-backend-api.md](02-backend-api.md) | `backend/app` FastAPI edge | 54 (8 High) |
| [03-agent-service.md](03-agent-service.md) | `backend/agent/app/nutrasmart_agent` | 51 (10 High) |
| [04-web-client.md](04-web-client.md) | `maitribot/client` | 32 (5 High) |

Totals: **172 findings — 28 High, 73 Medium, 68 Low, 3 Info.**

---

## 1. The repo at a glance

| Component | Path | Size | Tests | Notes |
|---|---|---|---|---|
| FastAPI edge | `backend/app` | 1,138 LOC, 12 handlers | **0** | ECS Fargate (ap-south-1), hand-written AWS CLI scripts in `backend/ecs` |
| Agent (canonical) | `backend/agent/app/nutrasmart_agent` | 2,258 prod LOC + 597 test + 359 scripts | 50 (food_scan only); **0** for face_scan | Strands on Bedrock AgentCore; `food_scan` is the well-engineered reference, `main.py` and `face_scan_biomarkers` lag it |
| Agent copies | `backend/agent/NutrasmartAgent`, `backend/agent/regions/*` | 4 × byte-identical copies of the package + 4 CLI scaffolds | — | **≈34,450 redundant LOC = 66 % of the repo; ≈205 of 322 tracked files** |
| Web client | `maitribot/client` | 1,384 JS/JSX + 334 CSS | **0** | Vite + React 18, two HTML entrypoints, Shen.AI SDK |
| Docs | `documents/` | 4 markdown docs + tex/pdf diagram | — | All four markdown docs describe the previous AWS account or removed code |

Repository-wide: 322 tracked files, 52,212 LOC excluding the PDF. Only `backend/ecs/*.sh` and the four scaffolds'
`.gitignore` files are generated or scripted; everything else is hand-maintained.

## 2. Top findings (fix first regardless of refactoring)

These are correctness or security issues the refactor should be sequenced around, not after.

1. **User-scoped storage is not enforced anywhere in the chain.** The client sends `email` in the presign body
   (`WEB-18`), the edge builds the S3 key from that unvalidated string instead of the verified token (`API-45`,
   `backend/app/routes/upload.py:37`), and the agent fetches any `key` / `images[].key` it is handed without checking
   the `users/{user_id}/` prefix (`AGT-44`, `agent main.py:310,331-334`). Fix all three layers together.
2. **Model and backend text is rendered as HTML** via `dangerouslySetInnerHTML` (`WEB-26`, `App.jsx:139,294`). Chat
   replies, vision-model output and error bodies are injected unescaped.
3. **CloudFront gate is bypassable** by sending `Origin: http://maitribot-demo-ui…` (`API-43`, `main.py:25,34-35`),
   and the shared secret is compared with `!=`. The same secret is also shipped in the public JS bundle (`WEB-27`,
   `api.js:11-15`), which the backend comment itself says defeats its purpose.
4. **Rate limiting is keyed on the proxy IP with per-task memory** (`API-44`): behind CloudFront/ALB every user shares
   one bucket and 1–4 Fargate tasks each have their own counter.
5. **`deploy.sh` rollback is a no-op**: the task definition pins `:latest`, deploy pushes `:latest`, so "rollback"
   redeploys the new image (`INF-9`). `setup.sh` creates one of the seven SSM parameters the task definition
   references, so a fresh environment cannot start (`INF-10`).
6. **Silent cross-region fallback** routes a region with no ARN/bucket configured to the default region (`API-47`),
   contradicting `DATA_RESIDENCY.md`. Production identifiers are the fallback defaults for most settings on both the
   edge (`API-1`) and the agent (`AGT-1`), so a missing env var points at production resources instead of failing.
7. **Face-scan contract disagrees with itself**: the route comment says only heart rate is exposed but the agent
   payload (with experimental BP/SpO2) is returned wholesale (`API-48`), the agent docstring says the same (`AGT-35`),
   and the client renders BP/SpO2 (`WEB-18`). Decide, then type the response.
8. **Session is never cleared on 401/403** in the client (`WEB-19`), and the Google ID token lives in `localStorage`
   read by both pages (`WEB-29`).
9. **Agent error flattening leaks internals**: every exception becomes `{"error": str(e)}` which the edge re-raises
   verbatim into HTTP `detail` (`AGT-30`, `API-36`), so botocore/torch/mediapipe messages reach clients.
10. **`evaluate_classifier.py` is broken by its relocation** (`AGT-36`, `parents[1]` resolves to the wrong dir), and
    `agentcore.json` declares Python 3.14 while the Dockerfile builds 3.12 (`INF-7`).

## 3. Cross-cutting themes (mapped to the coding rules)

### 3.1 No settings layer on two of three components
- **Edge:** `config.py` is a flat module of `os.environ.get` with production IDs as defaults, `load_dotenv()` at import,
  dead settings (`API-1`, `API-9`), while rate-limit strings, quotas, key templates, extension lists and tuning literals
  live in routes and the agent client (`API-2..8`). ≈46 literals outside `config.py`, 16 production identifiers inside.
- **Agent:** `main.py` re-reads four env vars that `food_scan/settings.py` already owns (`AGT-1`); S3 key layout and
  timestamp format repeated as literals (`AGT-2`); `face_scan_biomarkers` has an unvalidated, non-injectable settings
  reader and ≈65 DSP/product constants hardcoded in `dsv` (`AGT-4`, `AGT-5`). ≈90 literals outside settings.
- **Client:** no config module; production API URL is the silent fallback; timeouts, intervals, storage keys, routes
  and palette are scattered (`WEB-1..4`). ≈27 distinct values across ≈45 sites.
- **Infra:** `setup.sh` defaults to the old account's bucket names and region; task definition carries literal
  `us-east-1` and localhost origins (`INF-12`, `INF-18`, `INF-19`).

**Recommendation.** One frozen settings object per deployable (pydantic-settings for Python, `src/config.js` reading
`import.meta.env.VITE_*` for the client, `ecs/config.env` for scripts), required fields with no production defaults,
loaded once at the composition root and injected. See `API-1`, `AGT-1`, `WEB-1`, `INF-12`.

### 3.2 Timeouts
| Where | Missing | Ref |
|---|---|---|
| Edge S3 clients (8 call sites), Google cert fetch, Dockerfile healthcheck | botocore `Config`, transport timeout, `urlopen(timeout=)` | `API-10..12` |
| Agent `main.py` boto3 clients (9 call sites), Strands `BedrockModel`, face-scan S3 client, video extraction compute budget | botocore `Config`, `boto_client_config`, `max_sec` never passed | `AGT-8..11` |
| Client S3 PUT, WASM runtime `import()` | AbortController / deadline | `WEB-5`, `WEB-6` |

`food_scan` already does this right (`services.py:68-85`); copy its pattern via one shared client builder (`AGT-14`).

### 3.3 Separation of concerns and god modules
- `backend/app/routes/meals.py` (392 LOC) mixes repository, conversion, date math, aggregation and routing (`API-13`);
  quota, summary and upload logic sit in handlers (`API-14`); `user_id` derivation copied six times (`API-15`); the
  agent wire format is hand-built in three routes (`API-16`).
- `agent main.py` (366 LOC) owns chat and summary end to end: prompts, tools, S3 writers and a Bedrock call (`AGT-12`);
  three boto3 client builders, two lazy-load caches, duplicated size guard and response unwrap (`AGT-14..16`); `dsv` is
  a vendored research module with dataset-only code paths (`AGT-17`).
- `App.jsx` (484 LOC, 8 components, module-level mutable counter) holds formatting, auth, persistence, upload pipeline
  and navigation (`WEB-8`); identity is derived four different ways (`WEB-10`); the Shen.AI SDK leaks past the adapter
  into the page component (`WEB-13`).

### 3.4 Typed contracts
The edge↔agent contract is loose dicts on both sides (`API-22`, `AGT-20`): `get_data_context` returns a dict,
`get_current_user` returns a dict, `invoke_agent(payload: dict) -> dict`, agent handlers index `payload["user_id"]`.
`face_scan` is dict-only end to end (`AGT-22`). The client has implicit response shapes (`WEB-17`). Already-observed
drift: `content_type` sent but never forwarded, `email` sent though the token has it, face-scan fields disagree.

**Recommendation.** A small shared `nutrasmart_contracts` package (Action enum, request/response dataclasses or Pydantic
models, S3 key layout) consumed by both edge and agent, with `response_model=` on every route and JSDoc typedefs in the
client. Keep it tiny; it is justified by the drift that already exists, not by anticipated needs.

### 3.5 Import-time initialization and hidden singletons
- Edge: `load_dotenv()` and env parsing at import, `lru_cache` boto3 clients, module-level `app` with no factory
  (`API-28..31`). Tests cannot construct an app with fake dependencies.
- Agent: `boto3.client(...)` ×2 at import in `main.py`, tools closing over module globals (`AGT-25`); process-global
  torch state mutated per ensemble member (`AGT-26`); non-thread-safe `ModelCache` (`AGT-28`).
- Client: module-level SDK singleton reading env at import; `App.jsx` pulls the scan module graph in for one constant
  (`WEB-14`).

### 3.6 Logging and error types
No logging configuration on the edge; f-string logging; broad `except Exception` turning S3 403s into "no summary yet"
and Google outages into 401 (`API-33..35`). Agent mixes JSON-in-message and printf styles, has one owned error type
(`ClassifierError`), and flattens everything (`AGT-29..31`). Client logs full response bodies in production and has
empty `catch {}` blocks (`WEB-20`).

### 3.7 Tests, tooling and docs
- Tests: edge 0, face_scan 0, client 0. `food_scan` has 50 good unit tests with in-memory fakes — use it as the template.
- Tooling: no `pyproject.toml`, ruff or mypy for the edge; no eslint/prettier/vitest for the client despite
  `eslint-disable` comments in source (`API-38`, `WEB-24`).
- Docs: `DEPLOYMENT.md`, `SECURITY.md`, `DATA_RESIDENCY.md`, `backend/agent/README.md` and both READMEs reference the
  old account, removed folders, wrong paths or machine-specific paths (`INF-28..32`, `AGT-35`, `WEB-25`).
- 11 of 13 edge modules lack a module docstring; ≈30 undocumented, unannotated public functions in `dsv` (`API-39`,
  `AGT-34`).

### 3.8 Duplication and hygiene
- Five copies of the agent package; the AgentCore CLI does **not** require it — `aws-targets.json` is an array and
  the generated CDK already creates one stack per target (`INF-1`, `INF-2`). The staged merge touches `main.py` in five
  places and the IAM policy in four, which is the cost made visible.
- Root `package.json` is `{}` and the root lockfile names a package with zero dependencies (`INF-21`); root
  `.gitignore` is three lines (`INF-22`); 87 generated files are committed where 21 need to exist (`INF-5`).
- Dead code: `AnalysisCard`, raw bubble, `FaceScanModal` and ≈75 CSS lines unreachable (`WEB-9`, `WEB-32`); stale
  duplicate prompts in `food_scan/prompts.py` (`AGT-13`); dead settings and unused functions on the edge (`API-9`,
  `API-19`).

### 3.9 Naming
Six spellings for the product (`neutramart`, `nutrasmart`, `netrramart`, `w360-nutrasmart`, `sci-neutrasmart`,
`NutrasmartAgent`) and three for the UI (`maitribot`, `nutrasmart_ui`, `maitribot-demo-ui`); `senai_scan` wraps the
Shen.AI SDK (`INF-35`). Recommendation: `nutrasmart` as the canonical slug, since every live AWS resource and the
domain already use it.

## 4. Proposed target layout

```
nutrasmart-app/
├── README.md, .gitignore (full py/node/cdk set), .vscode/
├── contracts/                      # tiny shared package: Action enum, request/response models, S3 key layout
├── backend/
│   ├── app/                        # FastAPI edge: create_app(settings), routes/ services/ repositories/ schemas/
│   ├── tests/
│   ├── pyproject.toml              # ruff, mypy, pytest
│   ├── Dockerfile, .dockerignore, requirements.txt (locked)
│   └── infra/ecs/                  # config.env + lib.sh shared by setup/https/deploy/teardown; task-definition.tmpl.json
├── agent/                          # ONE AgentCore project (was backend/agent/NutrasmartAgent)
│   ├── agentcore/
│   │   ├── agentcore.json          # one runtime; region-neutral env
│   │   ├── aws-targets.json        # [{us,us-east-1},{in,ap-south-1},{ca,ca-central-1},{eu,eu-west-1}]
│   │   ├── .cli/deployed-state.json  # one file, keyed by target
│   │   └── cdk/, .llm-context/     # one copy of the generated scaffold
│   ├── app/NutrasmartAgent/
│   │   ├── Dockerfile, .dockerignore, requirements*.txt (incl. -dev, -gpu), policies/
│   │   └── app/nutrasmart_agent/
│   │       ├── main.py             # app + composition root + dispatch (~80 lines)
│   │       ├── settings.py         # composes ChatSettings/SummarySettings/FoodScanSettings/BiomarkerSettings + REGION_PROFILES
│   │       ├── infra/aws.py        # build_s3 / build_bedrock with timeouts; Lazy[T]
│   │       ├── storage.py          # UserDataLayout, ScanRecordStore
│   │       ├── chat/, summary/     # extracted from main.py
│   │       ├── food_scan/          # as today
│   │       └── face_scan_biomarkers/   # settings with DSP knobs, dataclass results, tests/, dsv split by concern
│   └── tools/                      # evaluate_classifier.py, classify_images.py (not shipped in the image)
├── frontend/                       # was maitribot/client
│   └── src/ config.js, auth/session.js, api/, components/, hooks/, lib/, shenai_scan/ (facade), types.js
└── documents/
```

Migration risks are listed in `01-repo-layout-and-infra.md` §"Proposed target layout": renaming AgentCore resources
recreates them (new ARNs → SSM params and edge must follow; plan a cutover, not a rename); `agentcore deploy` target
selection and whether `codeLocation` may point outside the project dir must be verified against the installed CLI
before deleting `backend/agent/app`; a single IAM policy across four buckets weakens IAM-level residency unless rendered
per target; finish or abort the in-progress merge before deleting copies.

## 5. Suggested sequencing

**Phase 0 — safety and hygiene (hours, no architecture change).**
Scope keys to the authenticated user in client, edge and agent (§2.1). Replace `dangerouslySetInnerHTML` with a
node-splitting renderer; drop `X-Origin-Verify` from the client; `hmac.compare_digest`; `email_verified` check.
Add botocore `Config` timeouts everywhere and an abort on the S3 PUT. Clear session on 401. Whitelist the face-scan
response. Fail closed on unconfigured regions. Delete root Node files, extend root `.gitignore`, fix
`evaluate_classifier.py`, add `.dockerignore` to the agent, pin `opencv-python-headless` and `boto3`.
*(API-10,11,43,45,47,48,49; AGT-8,9,10,36,37,44; WEB-5,19,26,27; INF-21,22.)*

**Phase 1 — collapse duplication (one or two days plus a cutover window).**
Verify CLI constraints, then one AgentCore project with four named targets and a `REGION_PROFILES` table in agent
settings; delete `backend/agent/regions/` and the package copy; one `deployed-state.json`. Fix `deploy.sh` to register
SHA-tagged task-definition revisions and make `setup.sh` create all SSM parameters (or move ECS to CDK, which the agent
side already uses). *(INF-1..5, 9..14.)*

**Phase 2 — settings, DI and typed contracts (days).**
pydantic-settings + `create_app(settings)` + lifespan-owned AWS clients on the edge; composition root and single
settings module on the agent; `contracts/` package with `Action` enum, request/response models and S3 key layout; domain
error hierarchy with one exception handler per side; structured JSON logging with a correlation id.
*(API-1,16,22,28..37; AGT-1,2,12,14,20,25,29,30; WEB-1,17.)*

**Phase 3 — split the god modules and close the test gap (days).**
`meals.py` → repository / aggregator / schemas; services for quota, summary, upload. `agent main.py` → `chat/`,
`summary/`, `storage.py`. `face_scan_biomarkers` brought to `food_scan`'s standard: validated settings holding the DSP
knobs, dataclass results, shared `Lazy[T]`, synthetic-signal tests; prune `dsv`. Edge test suite via
`dependency_overrides`. *(API-13,14,38; AGT-4,5,15,17,22,32; INF-28..31 docs rewrite alongside.)*

**Phase 4 — client decomposition (days).**
`config.js`, `auth/session.js`, `hooks/useSession` + `useThread`, `components/`, `lib/`; Shen.AI facade so the page
never sees SDK enums; JSDoc typedefs with `// @ts-check`; eslint/prettier/vitest; delete or gate dead paths; codify
COOP/COEP headers for `/scan.html` in infrastructure. *(WEB-8..10,13,14,22,24.)*

## 6. Decisions needed from the owner

1. Canonical product slug (`nutrasmart` recommended) and whether to rename `maitribot/` → `frontend/`, `senai_scan` → `shenai_scan`, and the repo itself.
2. IAM residency: one agent policy listing all four buckets, or render the policy per target to keep IAM-level isolation.
3. Face-scan contract: expose heart rate only (as the route comment says) or BP/SpO2 too (as the client renders).
4. In-house `FaceScanModal` + `/facescan/analyze` path: delete, or keep behind a provider flag alongside Shen.AI.
5. Chat image results: emit the richer `AnalysisCard` (`type: "analysis"`) or keep text and delete the card + CSS.
6. Keep `documents/data-flow-diagram.pdf` in git as a deliverable, or build it in CI.
7. Confirm with the installed `agentcore` CLI whether `deploy` takes a target selector and whether `codeLocation` may point outside the project directory, before the Phase 1 cutover.
8. Verify the `mediapipe==0.10.14` / `numpy==2.0.2` pairing in a clean arm64 / Python 3.12 environment (`AGT-39`); the pin is load-bearing for the legacy `mediapipe.solutions` API.
