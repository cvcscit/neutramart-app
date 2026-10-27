---
name: aws-infrastructure
description: Inspect, change and deploy NutraSmart's AWS estate safely — the FastAPI edge on ECS Fargate (backend/ecs/setup.sh, deploy.sh, setup-https.sh, teardown.sh, task-definition.json; ALB, CloudFront, SSM parameters, ACM, Route 53), the four regional Bedrock AgentCore runtimes (the AgentCore CLI projects under backend/agent/, one CDK stack per region), the regional S3 data buckets and the Bedrock model choices. Covers the two AWS accounts and what lives in which region, read-only investigation with the AWS CLI, what each script does and the state it needs, preview before any deploy, and protecting user data, the live domain and the runtime ARNs. Use this whenever a task touches AWS or the deploy scripts — "add an env var / secret / SSM parameter", "give the task role access to X", "deploy the backend", "redeploy the agent in eu", "what's deployed in ap-south-1", "check the logs", "is CloudFront unblocked", "which runtime serves Canada", "clean up the old account" — even when the user names only a service (ECS, Fargate, ALB, CloudFront, S3, SSM, AgentCore, Bedrock, ECR, ACM, Route 53).
---

# AWS infrastructure

## The estate

**Two accounts.** Everything deployed since the September 2026 migration lives in account `792207721590`. The previous
account, `209479309679`, is shared with another of the owner's projects, is reachable on this machine through the
`moxa-dev` profile, and still owns three things NutraSmart depends on: the Route 53 zone for `nutrasmart.in`, the
CloudFront distribution `E17LBHEJ1KKM70` that holds the live `api.nutrasmart.in` alias, and the old buckets
(`sci-neutrasmart-project*`, `food-detection-model`) that the root `README.md` still uses for local development. The
owner's decision (`documents/MIGRATION_OUTSTANDING_TASKS.md` §5) is that the old account stays untouched: read it when
a question needs it, never change it. `documents/DEPLOYMENT.md`, `SECURITY.md` and `DATA_RESIDENCY.md` still describe
the old account (`documents/notes/01-repo-layout-and-infra.md`, *Docs drift*); the migration doc is the current record.

**Four regions, one edge.** Users are routed by `CloudFront-Viewer-Country` to a data region
(`backend/app/config.py`, `COUNTRY_REGION`); all of a user's data stays in that region's bucket and is processed by that
region's runtime (`documents/DATA_RESIDENCY.md`). The edge itself runs only in `ap-south-1`.

| Region | Holds |
|---|---|
| `ap-south-1` | ECS cluster `nutrasmart-cluster`, service `nutrasmart-backend-service`, task family `nutrasmart-backend`, ALB `nutrasmart-alb-*`, ECR `nutrasmart-backend`, log group `/ecs/nutrasmart-backend`, SSM parameters `/nutrasmart/*`, IAM roles `nutrasmart-ecs-{execution,task}-role`, the ALB's ACM certificate, the India runtime, bucket `w360-nutrasmart-in` |
| `us-east-1` | CloudFront (`E2FYYI13W2EXEP`) and its ACM certificate, the US runtime, bucket `w360-nutrasmart-us`, the model bucket `biomarker-processing` (classifier checkpoints) |
| `ca-central-1` | the Canada runtime (Amazon Nova Lite `ca.` profile: no Anthropic model is Canada-resident), bucket `w360-nutrasmart-ca` |
| `eu-west-1` | the EU runtime, bucket `w360-nutrasmart-eu` |

| What | Defined in | Deployed by |
|---|---|---|
| Edge network, ALB, ECS cluster and service, ECR, IAM roles, log group, SSM `google-client-id` | `backend/ecs/setup.sh` (one-time; writes `backend/ecs/resources.env`, which the other scripts source) | A person, once. Not idempotent: a rerun creates a second VPC and NAT gateway before failing on the ALB name |
| Edge task (image, env, SSM secrets, health check) | `backend/ecs/task-definition.json` (placeholders filled by `setup.sh`), `backend/Dockerfile` | `backend/ecs/deploy.sh`: builds amd64, pushes `:<sha>` and `:latest`, `update-service --force-new-deployment`, waits for stability |
| HTTPS listener, certificate, DNS | `backend/ecs/setup-https.sh` (assumes the zone is in the same account; it is not, see above) | By hand (`MIGRATION_OUTSTANDING_TASKS.md`, *Done*) |
| CloudFront distribution, origin secret, buckets and their CORS | Nothing in the repo | By hand |
| Four agent runtimes | One AgentCore CLI project each: `backend/agent/NutrasmartAgent/` (us) and `backend/agent/regions/NutrasmartAgent-{ca,eu,in}/`. In each: `agentcore/agentcore.json` (runtime, env vars, policy), `agentcore/aws-targets.json`, `app/NutrasmartAgent/policies/s3-bedrock-policy.json`, state in `agentcore/.cli/deployed-state.json`, CDK stack `AgentCore-NutrasmartAgent-default` in that region | `agentcore deploy` from the project dir (CodeBuild builds the ARM64 image from the project's own copy of the agent code) |
| Frontend | `maitribot/client` (Vite build) | By hand; no script in the repo |

The runtime ARNs are wired to the edge through SSM: `/nutrasmart/agent-arn-{us,in,ca,eu}` become `AGENT_ARN_*` in the
task definition and `REGION_AGENT_ARNS` in `backend/app/config.py`. If a runtime is recreated, SSM and the edge must
follow.

## Rules

1. **Read freely; change nothing without a yes.** `describe-*`, `get-*` (except `ssm get-parameter --with-decryption`),
   `list-*`, `logs tail`, Logs Insights queries and `sts get-caller-identity` may run freely. Everything else changes
   AWS and needs an explicit yes, in the current message, for the exact command you showed: the four scripts in
   `backend/ecs/`, `agentcore deploy` / `agentcore remove`, `cdk deploy` / `cdk destroy`, `ecs update-service`,
   `ecs register-task-definition`, `ssm put-parameter`, `cloudfront update-distribution`,
   `route53 change-resource-record-sets`, `iam put-*`/`attach-*`, any S3 write, and `cdk deploy --no-execute` (it
   uploads assets). It also includes `agentcore invoke` and `bedrock-agentcore invoke-agent-runtime`: they run real
   work that calls paid models and writes under a user's prefix. A yes for one region is not a yes for another, and one
   deploy's yes doesn't cover the next.
2. **Know where you are.** Run `aws sts get-caller-identity` first and expect account `792207721590`. On 2026-10-26 this
   machine had no profile for that account (`deploy.sh` defaults to a profile named `nutrasmart`; `setup-https.sh`
   hardcodes it; the migration doc calls it `nutrasmart-792207721590`): if the identity is another account, stop and
   ask the user which profile to use. Never fall back to `default` or `moxa-dev` for a change, and never use the
   `gladi-*` or `*_AdministratorAccess` profiles: they belong to other accounts.
3. **Name the region on every command.** Nothing here is single-region. `--region ap-south-1` for the edge, SSM, ECR
   and the ALB; `us-east-1` for CloudFront and its certificate; the data region for a bucket or a runtime. Default to
   the edge's region only for edge resources. Look a name up rather than guess it.
4. **Protect stateful resources.** The four data buckets hold food photos, face-scan videos, vitals and health profiles
   under `users/<id>/`; the SSM parameters hold the origin secret and the runtime ARNs; renaming a runtime in
   `agentcore.json` destroys and recreates it with a new ARN (`AGENTS.md`, *Resource Identity*); the ECR repositories
   hold the only built images; the log group is the audit trail; the certificates and the alias are the live domain.
   `teardown.sh` deletes the whole edge estate, log group included, and leaves the certificate, the Route 53 records
   and the six extra SSM parameters behind: never run it without the user's explicit yes in the current message, and
   say what it will delete first. Never rerun `setup.sh` against an account that already has the estate.
5. **Keep secrets and user data out.** `CF_ORIGIN_SECRET` lives in SSM as a SecureString and in the gitignored `.env`
   files; never read it with `--with-decryption`, never put it in a command, a log, a doc or the chat. When reading
   buckets, count and describe (`list-objects-v2 --max-keys 1`, `head-object`); never download or print an object
   under `users/`, a scan record, a chat message or a vitals payload. The Google client ID is public; the account IDs,
   distribution IDs and ARNs may appear where a reader needs them.
6. **Least privilege, authenticated by default.** New grants name exact actions on exact ARNs built from the region
   and the four bucket names; S3 grants stay on the data buckets' `users/*` prefix where the code allows it. Edge
   routes stay behind `get_current_user`; CORS origins come from `ALLOWED_ORIGINS`, never `*`. The runtime policy's
   wildcards (`bedrock:InvokeModel` and marketplace subscription on `*`) are known debt (`INF-34`): don't add to them.

## Changing the edge deployment

- **A new tunable** is read in `backend/app/config.py` from an environment variable with a dev-safe default and no
  production identifier, added to the `environment` list in `backend/ecs/task-definition.json`, and documented in the
  root `README.md` configuration block.
- **A new secret** is an SSM parameter under `/nutrasmart/` (SecureString), referenced in the task definition's
  `secrets` list, created by `setup.sh` next to `google-client-id` (today it creates only that one of the seven the task
  definition reads, `INF-10`), and readable by `nutrasmart-ecs-execution-role`.
- **A new permission** for the running container goes on `nutrasmart-ecs-task-role`, in the policy `setup.sh` builds,
  scoped to the four buckets and the four regional runtime ARNs.

Then report that the change is not deployed: the live task reads a task-definition revision that `setup.sh`
registered, and `deploy.sh` only rebuilds the image and forces a new deployment of the same revision (`INF-9`). Shipping
an env or secret change needs `ecs register-task-definition` with the filled-in file and `ecs update-service
--task-definition <new revision>`, each with a yes. Rollback is the previous revision, not `deploy.sh`'s rollback,
which redeploys the same `:latest` image.

## Changing an agent runtime

- The `.json` files are the source of truth; never edit the generated `agentcore/cdk/` code (`AGENTS.md`). Types with
  constraints are in `agentcore/.llm-context/`. Run `agentcore validate` after an edit when the CLI is available.
- Environment variables live on the runtime, not the target, so region-specific values (`AWS_REGION`, `BEDROCK_REGION`,
  `S3_REGION`, `S3_BUCKET_NAME`, `BEDROCK_MODEL_ID`) differ per project. Change the project for the region in question,
  or all four consistently, and say which.
- A change to the agent code reaches a region only when that project's copy of `app/nutrasmart_agent/` carries it. The
  canonical package is `backend/agent/app/nutrasmart_agent/`; the four copies were byte-identical on 2026-10-26.
  Compare with `diff -r` before a deploy and tell the user when a copy lags.
- Never change `runtimes[].name`: it is the CloudFormation logical ID, and renaming destroys the runtime and its ARN.

## Deploying

**Preconditions.** Docker running; the right profile (rule 2). For the edge: `backend/ecs/resources.env`, which
`setup.sh` wrote on the machine that ran it and which was absent here on 2026-10-26; `deploy.sh` refuses to run without
it. For a runtime: the npm `@aws/agentcore` CLI and `aws-cdk`, neither installed here on 2026-10-26 (`npx` works for
CDK), plus a `cdk bootstrap` of the target region. `deploy.sh` and `agentcore deploy` ship the working tree, uncommitted
changes included: say so.

**Edge, in order.** Read-only check (`ecs describe-services`, `elbv2 describe-target-health`, the last minutes of the
log group); `./deploy.sh` with a yes; then `ecs describe-services` for `runningCount == desiredCount`, `curl
https://<alb or domain>/health`, and the first minutes of the log group. On failure the script re-forces the current
revision, which is the new image too (`INF-9`): find the previous revision with `ecs list-task-definitions
--family-prefix nutrasmart-backend` and propose `update-service --task-definition` to it.

**Runtime, in order.** `cd` into the project; `agentcore validate`; preview with `cd agentcore/cdk && npx cdk diff`
(needs `npm install` there once). For a change set to review, `npx cdk deploy --no-execute` (a yes: it uploads assets)
and then

```bash
aws cloudformation describe-change-set --change-set-name <arn> --region <region> --output json \
  | python3 <skill-dir>/scripts/review_change_set.py
```

Exit 1 means a runtime, bucket, repository, log group or distribution would be removed or replaced: stop and show the
user. Read every `ACCESS` row's policy diff. Then `agentcore deploy` with a yes, `agentcore status`, and compare the
ARN in `agentcore/.cli/deployed-state.json` with `ssm get-parameter --name /nutrasmart/agent-arn-<r> --region
ap-south-1`. If they differ, `put-parameter` and a new edge task revision are two more changes, each with a yes.
Finally `agentcore invoke` once with a test user id, with a yes, and read the runtime's log group.

## Investigating

Use read-only CLI calls with `--query` to keep the output small.

- **Edge:** `ecs describe-services --cluster nutrasmart-cluster --services nutrasmart-backend-service`;
  `ecs describe-task-definition --task-definition nutrasmart-backend` (env names and secret ARNs, no values);
  `logs tail /ecs/nutrasmart-backend --since 30m`; `elbv2 describe-load-balancers` and `describe-target-health`;
  `ssm get-parameters-by-path --path /nutrasmart --query 'Parameters[].Name'`. All in `ap-south-1`.
- **CloudFront and domain:** `cloudfront get-distribution --id E2FYYI13W2EXEP --query 'Distribution.{Status:Status,
  Aliases:DistributionConfig.Aliases,Origin:DistributionConfig.Origins.Items[0].DomainName}'`;
  `acm list-certificates --region us-east-1` and `--region ap-south-1`. The alias was still on the old account's
  distribution on 2026-09-26 (`MIGRATION_OUTSTANDING_TASKS.md` §2); check before assuming traffic reaches the new ALB.
- **Runtimes:** `cloudformation describe-stacks --stack-name AgentCore-NutrasmartAgent-default --region <r>` (same
  stack name in all four regions); `cloudformation list-stack-resources` for the runtime, role and repository;
  `bedrock-agentcore-control list-agent-runtimes --region <r>` if the CLI knows the command (aws-cli 2.15.30 on this
  machine did not on 2026-10-26; the repo's `deployed-state.json` files hold the same ARNs). Runtime logs are under
  `logs describe-log-groups --log-group-name-prefix /aws/bedrock-agentcore`.
- **Buckets:** `s3api get-bucket-location`, `get-bucket-cors`, `get-public-access-block`, and
  `list-objects-v2 --prefix users/ --max-keys 1` to confirm data exists without listing it.
- **Which account owns it?** `sts get-caller-identity` under the profile you used, then the same `describe-*` under
  `moxa-dev` for the old account, read-only.

Write findings up with the markdown-docs skill, into `documents/MIGRATION_OUTSTANDING_TASKS.md` or
`documents/DEPLOYMENT.md` when they change a recorded fact, saying what was read, when, and that it was read-only.

## Known state (read 2026-10-26 from the repo; verify before relying on it)

- `MIGRATION_OUTSTANDING_TASKS.md` (dated 2026-09-26): the new account's CloudFront was blocked account-wide, the
  `api.nutrasmart.in` alias and Route 53 zone were still in the old account, and all changes were being held
  uncommitted until cutover.
- Deploy-script defects with IDs in `documents/notes/01-repo-layout-and-infra.md`: `INF-9` (rollback is a no-op,
  `:latest` tag), `INF-10` (setup creates one of seven SSM parameters), `INF-11`/`INF-12` (task-role policy and bucket
  defaults still name the old buckets), `INF-13` (setup not idempotent), `INF-14` (three credential conventions).
  Fix them through the scripts, with a yes per AWS change, not by hand in the console.
