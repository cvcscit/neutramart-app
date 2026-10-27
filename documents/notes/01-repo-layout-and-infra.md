# 01 — Repo layout, duplication, deployment, hygiene, docs, IAM, naming

Read-only review, 2026-10-26. Findings are referenced from the summary as `INF-n`. Line numbers refer to the
working tree on `feature/w360-full-multiple-models` with the `feature/w360-full` merge staged.

## Layout summary

Three real components and one large block of copies:

- `backend/app/` — FastAPI edge (ECS Fargate, ap-south-1), with hand-written AWS CLI scripts in `backend/ecs/`
  (setup / https / deploy / teardown + `task-definition.json`).
- `backend/agent/app/nutrasmart_agent/` — the canonical Strands agent package (31 files, 3,214 LOC incl. tests and
  scripts) plus `backend/agent/{Dockerfile,requirements*.txt,README.md}`.
- `maitribot/client/` — Vite/React UI.
- `backend/agent/NutrasmartAgent/` + `backend/agent/regions/NutrasmartAgent-{ca,eu,in}/` — four complete AgentCore CLI
  projects (58 files each). Each embeds a byte-identical copy of the agent package, Dockerfile and requirements. All
  four were added in one commit (`191c7f7`, 2026-10-01, message "code"): one `agentcore create`, three `cp -r`, then
  region strings edited.

**Verdict on the five-copy problem: the AgentCore CLI does not force it.** Evidence in-repo:

- `agentcore/aws-targets.json` is typed as an *array* of targets (`.llm-context/aws-targets.ts:14-21`, "Target names
  must be unique within the array"); the generated `cdk/bin/cdk.ts:164-167` loops `for (const target of targets)` and
  creates one stack per target named `AgentCore-<project>-<target>`; `.cli/deployed-state.json` is keyed
  `targets.<targetName>`. One project with targets `us`, `in`, `ca`, `eu` is the designed path. Public CLI docs show
  the multi-entry array (staging/production example). A `--target` selector on `deploy` is not documented and must be
  checked with `agentcore deploy --help`.
- The real constraint: `envVars` and `additionalPolicies` live on the *runtime*, not the target (`agentcore.ts:53,61`);
  there is no per-target env override. Region-specific values (`BEDROCK_REGION`, `S3_BUCKET_NAME`, `S3_REGION`,
  `BEDROCK_MODEL_ID`) must either be derived at runtime from `AWS_REGION` via a region table in the agent's settings
  layer, or `agentcore.json` must be rendered from a template per deploy.
- `codeLocation` is a relative directory path (`agentcore.ts:48`); whether `../../app` outside the project dir passes
  `agentcore validate` and CodeBuild packaging is **unverified**. Safe move: one project with `app/` inside it and the
  canonical `backend/agent/app` relocated there.
- `.cli/deployed-state.json` is generated deploy output (runtime IDs/ARNs, role ARNs, account ID, deployHash).
  Committing it is the CLI's own convention — the generated `agentcore/.gitignore:8-14` ignores `.cli/*` then
  un-ignores it ("Exception: Commit the State"), and `bin/cdk.ts:50-55` reads it on synth. Keeping **one** is
  legitimate; four is a side effect of the copies.

## Duplication table

| Path | What differs from canonical | Nature |
|---|---|---|
| `backend/agent/NutrasmartAgent/app/NutrasmartAgent/app/nutrasmart_agent/` (+ `Dockerfile`, `requirements*.txt`) | nothing | byte-identical copy of `backend/agent/app/nutrasmart_agent/`, `backend/agent/Dockerfile`, `requirements.txt`, `requirements-base.txt` |
| `regions/NutrasmartAgent-{ca,eu,in}/app/NutrasmartAgent/app/nutrasmart_agent/` + Dockerfile + requirements | nothing | byte-identical (×3) |
| `regions/*/agentcore/agentcore.json` | `AWS_REGION`, `BEDROCK_REGION`, `S3_REGION` (→ `ca-central-1` / `eu-west-1` / `ap-south-1`); `S3_BUCKET_NAME` (→ `w360-nutrasmart-{ca,eu,in}`); **ca only**: `BEDROCK_MODEL_ID` → `ca.amazon.nova-lite-v1:0` | 4–5 env-var strings; no CPU/memory/image fields exist in this schema |
| `regions/*/agentcore/aws-targets.json` | `region` only; `account` identical; target `name` is `default` in all four | 1 string |
| `regions/*/agentcore/.cli/deployed-state.json` | `runtimeId`, `runtimeArn`, `roleArn`, `deployHash` | generated per-deploy state; same `stackName` `AgentCore-NutrasmartAgent-default` in all four (four stacks with the same name in four regions) |
| `regions/*/app/NutrasmartAgent/policies/s3-bedrock-policy.json` | bucket ARN in `S3Access`/`S3Location` | 2 resource strings |
| `*/agentcore/cdk/**` (12 files incl. 5,078-line `package-lock.json`), `.llm-context/*` (3), `.gitignore`, `AGENTS.md`, `README.md`, `app/NutrasmartAgent/{.gitignore,README.md}` | nothing | CLI-generated scaffolding, identical ×4; `cdk-stack.ts`/`bin/cdk.ts` referenced by nothing outside the scaffold |

## Findings

### Duplication / layout

1. **High** · Agent source tracked five times · `backend/agent/app/nutrasmart_agent/` vs the four
   `.../app/NutrasmartAgent/app/nutrasmart_agent/` trees · Every change must be applied five times; the staged merge
   does exactly that (`main.py` changed in 5 places, IAM policy in 4). Git history already diverges (canonical
   `main.py` has 5 commits, the `ca` copy 4). → Collapse to one AgentCore project; delete `backend/agent/regions/` and
   the package copy inside `NutrasmartAgent/`.
2. **High** · Four CLI projects where one with four targets is the designed model · `*/agentcore/aws-targets.json`
   (`name: "default"` ×4), `cdk/bin/cdk.ts:164-167` · Single-target copies defeat the per-target stack naming the
   generated CDK implements; four stacks share the name `AgentCore-NutrasmartAgent-default`. → Keep
   `backend/agent/NutrasmartAgent/` only; `aws-targets.json` = `[{us,us-east-1},{in,ap-south-1},{ca,ca-central-1},{eu,eu-west-1}]`;
   verify target selection with `agentcore deploy --help`.
3. **Med** · Region-specific config baked into env vars prevents a single `agentcore.json` ·
   `agentcore/agentcore.json:22-45`, agent `main.py:49-54`, `food_scan/settings.py` · Schema has no per-target env
   override. → `REGION_PROFILES` table (dataclass/enum keyed by `AWS_REGION`: bucket, model id) in the agent settings
   layer; keep `BEDROCK_MODEL_ID`/`S3_BUCKET_NAME` env as explicit overrides. Alternative: render `agentcore.json`
   from a template per deploy.
4. **Med** · Per-region IAM policy duplicated by bucket name · `policies/s3-bedrock-policy.json:12,21` (×4) · Only the
   bucket ARN varies. → In a single-project layout either list all four bucket ARNs (edge role already does this per
   `MIGRATION_OUTSTANDING_TASKS.md:13`) and accept that each regional runtime *could* reach other regions' buckets, or
   render per target if IAM-level residency is required. Make this an explicit decision.
5. **Med** · CLI scaffolding committed four times (15k+ LOC of lockfile) · `*/agentcore/cdk/package-lock.json`
   (5,078 lines ×4), `.llm-context/` (752 ×4), `cdk/{bin,lib,test}` ×4 · All generated, identical, unreferenced by
   project docs/scripts. → Goes away with #2; keep one `cdk/` (required by `agentcore deploy`).
6. **Low** · Canonical scaffold duplicates `backend/agent/{Dockerfile,requirements.txt,requirements-base.txt}` ·
   identical to the copy inside `NutrasmartAgent/app/NutrasmartAgent/`; `-dev`/`-gpu` requirements exist only at
   `backend/agent/`. → Make the project's `app/` dir the only home for these.
7. **Low** · `runtimeVersion: PYTHON_3_14` vs `FROM python:3.12-slim` · `agentcore.json:16`, `backend/agent/Dockerfile:2` ·
   For Container builds the Dockerfile wins, so the field misleads. → Set to 3.12 or drop if the CLI allows.
8. **Low** · `--platform=linux/arm64` hardcoded in `FROM` · `backend/agent/Dockerfile:2` · Breaks plain local
   `docker build` on amd64 without emulation. → Move the platform to the build command / buildx.

### Deployment scripts

9. **High** · `deploy.sh` rollback is a no-op and image tags are mutable · `backend/ecs/deploy.sh:30-31,55-56,75-79,105-110`,
   `task-definition.json:12` · Task definition pins `:latest`; deploy pushes `:latest` and `--force-new-deployment`, so
   `CURRENT_TASK_DEF` points at the same `:latest` and "rollback" redeploys the new image. Contradicts
   `DEPLOYMENT.md:110,119` and `SECURITY.md:32`. → Register a new task-def revision with the SHA-tagged image URI,
   `update-service --task-definition <new rev>`, roll back to the previous revision; stop pushing `:latest`.
10. **High** · `setup.sh` registers a task definition whose secrets it never creates · `task-definition.json:31-60`
    references `/nutrasmart/{cf-origin-secret,agent-runtime-arn,agent-arn-us,-in,-ca,-eu,google-client-id}`;
    `setup.sh:323-330` creates only `google-client-id`; `teardown.sh:146` deletes only that one · Fresh run → tasks
    fail at start (ResourceInitializationError). → Create all parameters in setup (prompt or config file), delete all
    in teardown.
11. **Med** · Task-role policy in `setup.sh` is stale vs live infra · `setup.sh:256,264` (old bucket
    `sci-neutrasmart-project`), `:272` (AgentCore invoke only `us-east-1`), `:275-281` (`bedrock:InvokeModel` on `*`
    though `backend/app/config.py:44-46` says the edge no longer calls Bedrock) · `MIGRATION_OUTSTANDING_TASKS.md:13`
    says the live policy was widened by hand. → Build the policy from a region list (4 bucket ARNs, 4 regional
    `bedrock-agentcore:*:runtime/*` ARNs), drop `BedrockInvokeLegacy`.
12. **Med** · Hardcoded region/bucket defaults in `setup.sh` · `:21` (`AWS_REGION="ap-south-1"`), `:351-354` (sed
    defaults to old `sci-neutrasmart-project*` names), `:350` (`<ALB_DNS>` placeholder no longer in
    `task-definition.json`) · Live buckets are `w360-nutrasmart-*`. → One `ecs/config.env` (region, project, bucket
    map, allowed origins) sourced by all four scripts; delete the dead sed line.
13. **Med** · `setup.sh` is not idempotent and not CI-safe · `:34-187` create VPC/subnets/IGW/NAT/EIP/SG/ALB/TG
    unconditionally; `:324` interactive `read -p`; `:197,219,244` fixed `/tmp/*.json`; `:412` `resources.env` written
    only at the end · A rerun creates a second VPC + NAT (billable) then fails on ALB name collision, leaving orphans.
    Prerequisite `jq` (`:14`) is never used. → Look-up-or-create by Name tag, or replace with CDK/Terraform (the agent
    side already uses CDK).
14. **Med** · Three credential conventions · `setup.sh` ambient creds; `deploy.sh:20` `${AWS_PROFILE:-nutrasmart}`;
    `setup-https.sh:28` hardcoded `PROFILE="nutrasmart"` with `--profile` on every call. → Standardize on `AWS_PROFILE`.
15. **Low** · `setup-https.sh` races and hardcodes domain · `:26-27` (`nutrasmart.in`, `api.nutrasmart.in`), `:90`
    `sleep 5`, `:98-99` python3 for JSON while setup claims jq. → Parametrize domain; poll `describe-certificate`.
16. **Low** · `teardown.sh` incomplete · `:76` `sleep 30` for ALB deletion; no removal of cert, Route 53 records, or
    the six extra SSM params. → `aws elbv2 wait load-balancers-deleted`; read HTTPS resources from `resources.env`.
17. **Low** · Backend image may include local venvs · `backend/Dockerfile:14` `COPY . .`; `backend/.dockerignore:9`
    only `.venv/` while README references `backend/venv_backend` and root `.gitignore:3` is `*venv*/`. → Add `venv*/`,
    `*.md`, `tests/` to `.dockerignore`; `COPY app/ ./app/`.

### Task definition & config

18. **Med** · Literal values in `task-definition.json` that are deploy parameters · `:23-24`
    `AGENTCORE_REGION`/`DEFAULT_DATA_REGION` = `us-east-1`; `:29` `ALLOWED_ORIGINS` includes `http://localhost:5173,5174`
    in production; `:12` `:latest`. → Template like the `<...>` placeholders (or generate the file); drop localhost
    origins from prod.
19. **Med** · Backend code defaults point at the old account's resources · `backend/app/config.py:7`
    (`sci-neutrasmart-project`), `:47-48` (`BEDROCK_REGION` constant), `:76-79` (old bucket names), `:18-21`
    (`maitribot-demo-ui` S3 website origins), `:9-12` (Google client id literal) · Silent fallback to wrong buckets if
    an env var is missing. → Fail fast (no defaults) for `BUCKET_*`/`AGENT_ARN_*`; remove dead Bedrock constants.
20. **Low** · Google OAuth client ID treated as a secret · `setup.sh:325-329` SecureString; same value in clear at
    `config.py:11` and `DEPLOYMENT.md:160` · It is a public identifier; the real secret is `CF_ORIGIN_SECRET`. → Plain
    `String` parameter; SecureString for `cf-origin-secret`, created in setup (#10).

### gitignore / hygiene

21. **Med** · Vestigial root Node files · `package.json` = `{}`, `package-lock.json` names `nutrasmart-aws` with zero
    packages · Explains how `node_modules` got committed earlier. → Delete both.
22. **Med** · Root `.gitignore` too thin · `.gitignore:1-7` lacks `__pycache__/`, `*.pyc`, `.pytest_cache/`,
    `cdk.out/`, `.cache/`, `*.log`, `.env.*`; coverage depends on nested gitignores · → Add the standard
    Python/Node/CDK set at root; `maitribot/client/.gitignore:24,30` duplicates `.env.*`.
23. **Low** · Build artifact committed · `documents/data-flow-diagram.pdf` (152 KB) alongside its `.tex`. → Accept PDFs
    as deliverables deliberately (then ignore `*.aux/*.log/*.synctex.gz`) or build in CI.
24. **Low** · Merge in progress conflicted on artifacts · `.git/MERGE_MSG` lists `maitribot/client/dist/index.html` and
    `node_modules/.package-lock.json` · `dist/` and `node_modules/` were tracked on one branch; now untracked and
    ignored. → Nothing beyond #22.
25. **Info** · `.vscode/launch.json` has no absolute paths (uses `${workspaceFolder}`); tracked while
    `app/NutrasmartAgent/.gitignore:40` ignores `.vscode/` — fine.

### Secrets

26. **Info** · No credentials found. Tracked files scanned for `AKIA…`, `aws_secret`, `api_key`, `token`, `password`,
    `Bearer`, private keys: all hits are code/variable names (`backend/app/auth.py:2-20`,
    `maitribot/client/src/api.js:14`, `src/senai_scan/sdk.js:23` reads an env var, `deploy.sh:41-42` `--password-stdin`).
27. **Low** · Sensitive identifiers (not secrets) committed · current account ID in `aws-targets.json` ×4 and
    `deployed-state.json` ×4 (runtime + role ARNs); old account ID, VPC/subnet/SG IDs and ALB DNS in
    `DEPLOYMENT.md:9-16,85-90`; CloudFront distribution IDs in `DATA_RESIDENCY.md:37`, `MIGRATION…md:16,24,31`; Google
    client id in `config.py:11`, `DEPLOYMENT.md:160` · Acceptable for a private repo; reduce to one
    `deployed-state.json` and scrub docs of old-account IDs.

### Docs drift

28. **High** · `DEPLOYMENT.md` describes the previous account and a frontend that no longer exists · `:9-16` old
    account/ALB/bucket/ECR; `:169,197,263,300` `cd netrramart_backend/ecs` (typo; real path `backend/ecs`); `:238`
    `nutrasmart_ui/src/config/api.js` (removed per `MIGRATION…md:17`); `:122-131` "HTTPS not yet" while
    `setup-https.sh` exists and `MIGRATION…md:15` says 443 is live; `:107` "UID 1000" vs `useradd -r`; `:110`
    immutable tags vs #9. → Rewrite around the current scripts, or generate the "Current Deployment" table from
    `resources.env`.
29. **Med** · `SECURITY.md` stale · `:7` "only port 80", `:37` "only thing missing is HTTPS", `:32` git-SHA immutable
    tags, `:35` "24 AWS components". → Fold into `DEPLOYMENT.md` or regenerate after #28.
30. **Med** · `DATA_RESIDENCY.md` stale · `:3` old account; `:16-20` old bucket names; `:84-87` old runtime ARNs;
    `:22,41` links `app/config.py` (should be `backend/app/config.py`); `:146-153` "Add a new region" describes manual
    ECR+runtime creation rather than the CLI. → Update bucket table and ARNs from `deployed-state.json`; point "add a
    region" at adding a target.
31. **Med** · `backend/agent/README.md` inconsistent with itself and code · `:3` "(us-east-1)" single region; `:22-23`
    bucket `sci-neutrasmart-project` vs `:168` `w360-nutrasmart-us`; `:93-96` env defaults match `main.py:49-54` but
    not deployment; `:220-240` deploy section describes a single `agentcore create` + single SSM `agent-runtime-arn`,
    not four regional runtimes; `:257` "this machine has 3.9". → Rewrite for the single-project/multi-target flow.
32. **Low** · Root `README.md` uses old resources and machine-specific paths · `:21-22,63,125,149` `moxa-dev` profile
    and `sci-neutrasmart-project-us`; `:32,35,69` `/home/mario/data/welness360/...`. → Use current bucket names and an
    `.env.example` with placeholders.
33. **Info** · `MIGRATION_OUTSTANDING_TASKS.md` items overlapping this refactor: Done `:8` (account IDs removed from
    scripts — but bucket/region literals remain, #12), Done `:13` (IAM widened by hand — #11 codifies it), Done `:17`
    (folders removed — `DEPLOYMENT.md` still cites them, #28), Outstanding `:38` #4 docs update (#28-30), `:41` #5
    revert `.env`/hosts hacks, `:45` #6 "holding all changes uncommitted" (explains the large staged merge). The doc
    references "this conversation" (`:24`) — a chat artifact, not a doc.

### IAM

34. **Med** · Agent policy wildcards · `policies/s3-bedrock-policy.json:24-30` `bedrock:InvokeModel` on `*`; `:31-39`
    `aws-marketplace:ViewSubscriptions/Subscribe` on `*` (lets the runtime subscribe the account to marketplace models)
    · → Scope Bedrock to `arn:aws:bedrock:<region>::foundation-model/*` + `arn:aws:bedrock:*:<acct>:inference-profile/*`
    (needed for `global.`/`ca.` profiles — `DATA_RESIDENCY.md:94`), add `InvokeModelWithResponseStream` if streaming is
    used; move marketplace subscription to a one-time admin action. `s3:DeleteObject` (`:10`) — confirm the agent
    deletes objects; otherwise remove. Model-bucket read (`:40-55`) is appropriately scoped.

### Naming

35. **Low** · Six spellings for one product and three for the UI · repo dir `neutramart-app`; ECS/SSM/roles
    `nutrasmart-*`; buckets `w360-nutrasmart-*` and old `sci-neutrasmart-project*`; AgentCore project
    `NutrasmartAgent`, package `nutrasmart_agent`; domain `nutrasmart.in`; root lockfile `nutrasmart-aws`; docs
    `netrramart_backend` (`DEPLOYMENT.md:169`), `neutramart_backend` (commit `0a4fc72`), `nutrasmart_ui`; UI folder
    `maitribot/` with package `maitribot-client` and S3 origin `maitribot-demo-ui`; `senai_scan/` for the Shen.AI SDK;
    local path `welness360`. → Pick `nutrasmart` as the canonical slug (matches every live AWS resource and the
    domain); rename folders (`maitribot` → `frontend`, `senai_scan` → `shenai_scan`) in one commit after the merge
    lands; note "W360 = account/bucket prefix" in the README.

## Proposed target layout

```
nutrasmart-app/
├── README.md, .gitignore (full py/node/cdk set), .vscode/
├── backend/
│   ├── app/                     # FastAPI edge
│   ├── Dockerfile, .dockerignore, requirements.txt
│   └── infra/ecs/               # renamed from ecs/
│       ├── config.env           # REGION, PROJECT, bucket map, origins, domain (single source)
│       ├── lib.sh               # shared: load config, lookup-or-create helpers
│       ├── setup.sh, setup-https.sh, deploy.sh, teardown.sh
│       └── task-definition.tmpl.json
├── agent/                       # ONE AgentCore project (was backend/agent/NutrasmartAgent)
│   ├── AGENTS.md, README.md
│   ├── agentcore/
│   │   ├── agentcore.json       # one runtime; env = region-neutral defaults only
│   │   ├── aws-targets.json     # [{us,us-east-1},{in,ap-south-1},{ca,ca-central-1},{eu,eu-west-1}]
│   │   ├── .cli/deployed-state.json   # one file, targets.{us,in,ca,eu}
│   │   ├── .llm-context/, cdk/  # one copy of the generated scaffold
│   └── app/NutrasmartAgent/
│       ├── Dockerfile, requirements*.txt (incl. -dev, -gpu)
│       ├── policies/s3-bedrock-policy.json   # 4 bucket ARNs or rendered per target
│       └── app/nutrasmart_agent/            # the only copy; settings has REGION_PROFILES
├── frontend/                    # was maitribot/client
└── documents/
```

**Migration risks.**
1. Resource identity — `AGENTS.md` warns renaming a resource destroys/recreates it; moving from four `default` targets
   to named targets creates four new stacks/runtimes with new ARNs, so the SSM `agent-arn-*` params and the edge must be
   updated and the old stacks destroyed (`agentcore remove` / `cdk destroy` per old project). Plan a cutover, not an
   in-place rename.
2. Confirm target selection (`agentcore deploy --help`) and whether `codeLocation` may point outside the project dir
   before deleting `backend/agent/app`.
3. A single IAM policy across four buckets weakens IAM-level residency unless rendered per target.
4. The merge in progress stages the same `main.py` edit in five places — finish or abort it before deleting copies.
5. `.vscode/launch.json` and both READMEs reference `backend/agent` as cwd; update together.

## Metrics

- Tracked files: 322; tracked LOC (excl. PDF): 52,212. `backend/agent` alone: 45,189 LOC / 292 files.
- Duplicated LOC: agent package 3,214 × 4 redundant copies = **12,856**; CLI scaffold (non-package) 7,199 × 3 =
  **21,597** (of which `cdk/package-lock.json` 15,234, `.llm-context` 2,256); plus Dockerfile/requirements duplicates
  (~50 × 4). **Total ≈ 34,450 redundant LOC (66 % of the repo)**; redundant files ≈ 205 of 322 (64 %).
- Hardcoded literals in `backend/ecs/*` + `task-definition.json`: account IDs 0 (auto-detected; but the current account
  appears in 8 config/state files and `backend/agent/README.md:165,218,225`; the old one in 3 docs); regions 4
  (`setup.sh:21,272`, `task-definition.json:23,24`); bucket names 6 (`setup.sh:256,264,351-354`, all old names);
  profile names 2; domains 2; wildcard IAM resources 1 in scripts + 2 in the agent policy; mutable `:latest` 1.
- Generated files committed: 21 per scaffold × 4 = 84 (4 `deployed-state.json`, 4 × 12 `cdk/`, 4 × 3 `.llm-context`,
  4 `.gitignore`, 8 template README/AGENTS, 8 template app `.gitignore`/README) + 1 PDF + 2 vestigial root Node files
  = **87**; 21 need to exist.
- Scripts: all four have `set -euo pipefail`; 0 of 4 idempotent on rerun (`deploy.sh` is safe to rerun; `setup.sh` is
  not).

Sources consulted (public, generic): AgentCore CLI deploy skill (multi-target `aws-targets.json`); AgentCore CLI
reference (AWS docs); AgentCore CLI README (project layout).
