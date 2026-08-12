# NutraSmart AgentCore Agent

A Strands agent deployed on **Amazon Bedrock AgentCore Runtime** (us-east-1) that owns all of
NutraSmart's LLM logic. The FastAPI backend proxies to it via `invoke_agent_runtime`.

## Actions (invocation payload)

| action | payload | returns |
|---|---|---|
| `chat` | `{"action":"chat","user_id","message","history":[{role,content}]}` | `{"reply": str}` |
| `summary` | `{"action":"summary","user_id"}` | `{"status":"ok"}` (writes `weekly_summary.txt`) |
| `analyze` | `{"action":"analyze","user_id","images":[{"key","content_type"}]}` | analysis JSON |

Identity is trusted from `user_id` in the payload only — the FastAPI edge validates the Google
ID token and derives it. Never pass a client-supplied user id.

## Tools

`get_recent_scans`, `get_health_profile`, `get_eating_summary` (chat reads these on demand);
`analyze_food_images` (S3 fetch → Pillow normalize → vision model) and internal `_save_scan` /
`_save_summary` writers. S3 bucket `sci-neutrasmart-project` (ap-south-1); Bedrock in us-east-1.

## Environment variables

| var | default |
|---|---|
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `BEDROCK_REGION` / `AWS_REGION` | `us-east-1` |
| `S3_BUCKET_NAME` | `sci-neutrasmart-project` |
| `S3_REGION` | `ap-south-1` |

## Deploy

Prereqs: Node 20+, Docker, AWS creds for account 209479309679. CLI is npm `@aws/agentcore`.

```bash
npm install -g @aws/agentcore aws-cdk
cd backend/agent

# One-time CDK bootstrap for us-east-1 (if not already done)
cdk bootstrap aws://209479309679/us-east-1

# Scaffold config around this code (Container build, HTTP, Bedrock, no memory)
agentcore create --name NutrasmartAgent --framework Strands \
  --protocol HTTP --model-provider Bedrock --build Container --memory none

# Deploy (builds ARM64 image → ECR → AgentCore Runtime + IAM role via CDK)
agentcore deploy

# Grab the ARN and store it for the FastAPI edge
agentcore status                       # copy agentRuntimeArn
aws ssm put-parameter --name /nutrasmart/agent-runtime-arn --type String \
  --value "<agentRuntimeArn>" --overwrite --region ap-south-1
```

Extend the generated runtime execution role with S3 access to the bucket:
`s3:GetObject`/`PutObject` on `arn:aws:s3:::sci-neutrasmart-project/*` and `GetBucketLocation`
on the bucket (mirror `agentcore-experiments-role`).

## Verify

```bash
agentcore invoke '{"action":"chat","user_id":"<test uid>","message":"Am I low on any minerals?"}'
agentcore invoke '{"action":"summary","user_id":"<test uid>"}'
agentcore invoke '{"action":"analyze","user_id":"<test uid>","images":[{"key":"<s3 image key>","content_type":"image/jpeg"}]}'
agentcore logs        # tool-call traces
```

Then redeploy the FastAPI backend (`backend/ecs/deploy.sh`) so it picks up
`AGENT_RUNTIME_ARN` and the updated task role (`bedrock-agentcore:InvokeAgentRuntime`).

> Local `agentcore dev` needs Python 3.10+ (this machine has 3.9). The Container build +
> `agentcore deploy` path avoids that; install 3.10+ only if you want local hot-reload.
