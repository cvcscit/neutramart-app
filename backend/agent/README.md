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

`get_recent_scans`, `get_health_profile`, `get_eating_summary` (chat reads these on demand) and
internal `_save_scan` / `_save_summary` writers. S3 bucket `sci-neutrasmart-project` (ap-south-1);
Bedrock in us-east-1.

## Food recognition (`analyze`)

```
S3 images ─► local classifier (each image) ─► every top-1 ≥ threshold? ─yes─► text-only LLM: nutrition for the named dishes
                 │ disabled / load or inference error    │ no
                 └───────────────────────────────────────┴───────────► vision LLM on the images (original behavior)
```

- Code: `analysis.py` (routing), `recognition/` (classifier protocol, EfficientNetV2-S backend,
  S3 model cache, backend registry), `prompts.py`, `settings.py`, `services.py`.
- Every result carries `recognition: {source: "classifier"|"llm", threshold, predictions}`, which is
  saved with the scan so fallback rate and classifier accuracy can be audited.
- The model loads lazily on the first `analyze` request per container (chat/summary never load
  torch). If it cannot be loaded, the error is logged and the agent uses the vision LLM only.

**Swapping the model**
- Same architecture, new weights: upload the checkpoint to S3 and point
  `FOOD_CLASSIFIER_MODEL_URI` at it (the cache is keyed by ETag, so replacing the object also works).
- New architecture: add a class implementing `recognition.base.FoodClassifier`, register a loader in
  `recognition/factory.py::CLASSIFIER_BACKENDS`, and set `FOOD_CLASSIFIER_BACKEND`.

Checkpoints are loaded with `torch.load(weights_only=True)` and must contain `model_state_dict`,
`class_names` and `class_to_index` (optionally `architecture`, `image_size`, `imagenet_mean`, `imagenet_std`).
The runtime role needs `s3:GetObject` on the model object.

## Environment variables

| var | default |
|---|---|
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `BEDROCK_REGION` / `AWS_REGION` | `us-east-1` |
| `S3_BUCKET_NAME` | `sci-neutrasmart-project` |
| `S3_REGION` | `ap-south-1` |
| `MAX_IMAGE_SIZE_BYTES` / `BEDROCK_MAX_IMAGE_BYTES` / `MAX_IMAGES_PER_REQUEST` | `10485760` / `3932160` / `5` |
| `ANALYZE_MAX_TOKENS` / `SUMMARY_MAX_TOKENS` | `4096` / `2048` |
| `BEDROCK_CONNECT_TIMEOUT_S` / `BEDROCK_READ_TIMEOUT_S` | `10` / `120` |
| `S3_CONNECT_TIMEOUT_S` / `S3_READ_TIMEOUT_S` / `AWS_MAX_RETRIES` | `5` / `60` / `3` |
| `FOOD_CLASSIFIER_ENABLED` | `false` |
| `FOOD_CLASSIFIER_BACKEND` | `efficientnet_v2_s` |
| `FOOD_CLASSIFIER_MODEL_URI` | — (required when enabled; `s3://…` or a local path) |
| `FOOD_CLASSIFIER_THRESHOLD` | `0.60` |
| `FOOD_CLASSIFIER_TOP_K` / `FOOD_CLASSIFIER_NUM_THREADS` | `5` / `2` |
| `FOOD_CLASSIFIER_CACHE_DIR` | `/tmp/food_models` |
| `FOOD_CLASSIFIER_DEVICE` | `cpu` (`cuda` for local GPU runs only; AgentCore has no GPU) |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
# optional smoke test against a real checkpoint
FOOD_CLASSIFIER_TEST_CHECKPOINT=/path/to/model.pt python -m pytest -k checkpoint
```

## Local GPU (evaluation only)

Production stays CPU-only (`requirements.txt`). For local evaluation on an NVIDIA GPU:

```bash
uv venv -p 3.12 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -r requirements-gpu.txt --index-strategy unsafe-best-match
.venv/bin/python scripts/evaluate_classifier.py "/path/to/<label folders>" --device cuda \
    --model /path/to/model.pt --manifest /path/to/manifest.csv --output results.csv
```

On CUDA the classifier disables TF32, so GPU scores match CPU (production) scores and a
threshold chosen on the GPU carries over unchanged.

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
