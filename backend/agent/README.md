# NutraSmart AgentCore Agent

A Strands agent deployed on **Amazon Bedrock AgentCore Runtime** (us-east-1) that owns all of
NutraSmart's LLM logic. The FastAPI backend proxies to it via `invoke_agent_runtime`.

## Actions (invocation payload)

| action | payload | returns |
|---|---|---|
| `chat` | `{"action":"chat","user_id","message","history":[{role,content}]}` | `{"reply": str}` |
| `summary` | `{"action":"summary","user_id"}` | `{"status":"ok"}` (writes `weekly_summary.txt`) |
| `analyze` | `{"action":"analyze","user_id","images":[{"key","content_type"}]}` | analysis JSON |
| `face_scan` | `{"action":"face_scan","user_id","key":"users/.../scans/<id>.mp4"}` | `{"heart_rate", "bp", "spo2"}` |

Identity is trusted from `user_id` in the payload only — the FastAPI edge validates the Google
ID token and derives it. Never pass a client-supplied user id.

`face_scan` is a separate feature (biomarker heart-rate/BP/SpO2 from a face video) owned
independently of food recognition below -- its code lives in `app/dsv/` and the relevant
section of `main.py`; only `heart_rate` is currently validated (see
`BP_measurement/README.md`), `bp`/`spo2` are experimental and always flagged as such.

## Tools

`get_recent_scans`, `get_health_profile`, `get_eating_summary` (chat reads these on demand) and
internal `_save_scan` / `_save_summary` writers. S3 bucket `sci-neutrasmart-project` (ap-south-1);
Bedrock in us-east-1.

## Food recognition (`analyze`)

Two recognizers, and `FOOD_RECOGNITION_ORDER` picks which runs first; the other is the fallback.

- **Classifier**: classify each image; score = lowest top-1 confidence across images; good enough when
  ≥ `FOOD_CLASSIFIER_THRESHOLD`. The dish names then go to a text-only LLM call for nutrition.
- **Vision LLM**: images go to the LLM, which self-reports `confidence` (0–1); good enough when
  ≥ `LLM_CONFIDENCE_THRESHOLD`. No JSON, "No food detected" or a missing confidence scores 0.

```
classifier_first (default):
S3 images ─► classifier ─► good enough? ─yes─► text-only LLM (nutrition for the named dishes)
                 │ no                                  ▲
                 ▼                                     │ classifier scored higher
             vision LLM ─► good enough? ─no──► compare scores (tie → classifier)
                               │ yes / LLM scored higher ─► vision result

llm_first:
S3 images ─► vision LLM ─► good enough? ─yes─► vision result (classifier never runs)
                 │ no
                 ▼
             classifier ─► good enough, or scored higher than the LLM? ─yes─► text-only LLM
                               │ no (tie → LLM) ─► vision result
```

With the classifier disabled, or if it fails to load or classify, the vision LLM result is used
in either order.

- Code lives in `app/nutrasmart_agent/food_scan/` (a self-contained subpackage, independent
  of the rest of the agent): `analysis.py` (routing), `recognition/` (classifier protocol,
  EfficientNetV2-S backend, S3 model cache, backend registry), `prompts.py`, `settings.py`,
  `services.py`. `main.py` only calls `food_scan.analysis.analyze_food_images(...)`.
- Every result carries a top-level `confidence` (the winning recognizer's score) and
  `recognition: {source: "classifier"|"llm", order, threshold, llm_threshold, llm_confidence,
  fallback_used, predictions}`, which is saved with the scan so fallback rate and accuracy can be
  audited. `fallback_used` is true when the first recognizer fell short and the fallback's answer won.
- The model loads lazily on the first `analyze` request per container (chat/summary never load
  torch). If it cannot be loaded, the error is logged and the agent uses the vision LLM only.

**Cuisine models**
- The classifier is an ensemble: every checkpoint in `FOOD_CLASSIFIER_MODELS` (today Chinese, Indian
  and Thai) classifies each image, and the prediction with the highest top-1 confidence wins (ties go
  to the model listed first). `recognition.models` records the winning model per image. The models are
  not jointly calibrated (fewer classes tend to give higher softmax peaks), so watch per-model win
  rates when tuning `FOOD_CLASSIFIER_THRESHOLD`.
- Checkpoints live in `s3://biomarker-processing/models/food/<cuisine>/` (us-east-1, readable through the
  existing `BiomarkerModelsAccess` grant) and are downloaded with an S3 client pinned to
  `FOOD_CLASSIFIER_MODEL_REGION`.

**Swapping the model**
- Same architecture, new weights: upload the checkpoint to S3 and add or replace its `name=uri` entry
  in `FOOD_CLASSIFIER_MODELS` (the cache is keyed by ETag, so replacing the object also works).
- New architecture: add a class implementing `recognition.base.FoodClassifier`, register a loader in
  `recognition/factory.py::CLASSIFIER_BACKENDS`, and set `FOOD_CLASSIFIER_BACKEND`.

Checkpoints are loaded with `torch.load(weights_only=True)` and must contain `model_state_dict`,
`class_names` and `class_to_index` (optionally `architecture`, `image_size`, `imagenet_mean`, `imagenet_std`).
The runtime role needs `s3:GetObject` on every model object.

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
| `FOOD_RECOGNITION_ORDER` | `classifier_first` (or `llm_first`) |
| `LLM_CONFIDENCE_THRESHOLD` | `0.60` |
| `FOOD_CLASSIFIER_ENABLED` | `false` |
| `FOOD_CLASSIFIER_BACKEND` | `efficientnet_v2_s` |
| `FOOD_CLASSIFIER_MODELS` | — (required when enabled; comma-separated `name=uri`, each `s3://…` or a local path) |
| `FOOD_CLASSIFIER_MODEL_REGION` | `us-east-1` (region of the model bucket) |
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

Prereqs: Node 20+, Docker, AWS creds for account 792207721590. CLI is npm `@aws/agentcore`.

```bash
npm install -g @aws/agentcore aws-cdk
cd backend/agent

# One-time CDK bootstrap for us-east-1 (if not already done)
cdk bootstrap aws://792207721590/us-east-1

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
