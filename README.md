# NutraSmart app

Food-photo nutrition analysis, chat and face-scan vitals.

| folder | what | local port |
|---|---|---|
| `maitribot/client/` | React + Vite chat frontend | 5174 |
| `backend/app/` | FastAPI edge: Google auth, presigned S3 uploads, routes `/api/*` to the agent | 8000 |
| `backend/agent/` | Agent runtime (Bedrock AgentCore HTTP contract): food recognition, chat, summaries, face scan | 8080 |

```
browser :5174 ──(Google ID token)──> FastAPI :8000 ──(AGENT_LOCAL_URL)──> agent :8080
     │                                    │                                   │
     └──── PUT photo (presigned URL) ─────┴──── S3 bucket ────────────────────┘  + Bedrock
```

Details: `backend/agent/README.md` (agent, food recognition, deploy) and `maitribot/README.md` (frontend).

## Run the whole stack locally

Everything runs on your machine except S3 and Bedrock. Those use the `moxa-dev` AWS profile and
the `sci-neutrasmart-project-us` bucket (us-east-1). Without a CloudFront country header, the
backend routes every user to `DEFAULT_DATA_REGION=us-east-1`.

### Prerequisites (once)

- **AWS:** working credentials for `moxa-dev`. Check with:
  ```bash
  aws sts get-caller-identity --profile moxa-dev
  ```
- **Food models:** the `food-detection-model` bucket mounted at
  `/home/mario/data/welness360/s3/food-detection-model`. The agent reads the Chinese, Indian and
  Thai checkpoints from there:
  ```bash
  mount-s3 food-detection-model ~/data/welness360/s3/food-detection-model/ --profile moxa-dev
  ```
- **Agent dependencies:** `venv_agent` has CUDA torch but not the face-scan dependencies
  (`opencv`, `mediapipe`, …) that the agent server imports at startup. Install the full GPU set
  into it:
  ```bash
  cd backend/agent
  VIRTUAL_ENV=$PWD/venv_agent uv pip install -r requirements-gpu.txt --index-strategy unsafe-best-match
  ```
  Without an NVIDIA GPU, install `requirements.txt` (CPU) instead and set
  `FOOD_CLASSIFIER_DEVICE=cpu`.
- **Backend dependencies:** `backend/venv_backend` already has them. Otherwise:
  ```bash
  VIRTUAL_ENV=$PWD/backend/venv_backend uv pip install -r backend/requirements.txt
  ```
- **Frontend dependencies:**
  ```bash
  cd maitribot/client
  npm install
  ```
- **Google sign-in:** `http://localhost:5174` must be an *Authorized JavaScript origin* on the
  OAuth client in the Google Cloud console.

### Configuration (gitignored files)

**`backend/agent/.env`** (agent):
```bash
AWS_PROFILE=moxa-dev
S3_BUCKET_NAME=sci-neutrasmart-project-us     # must match the backend's bucket for DEFAULT_DATA_REGION
S3_REGION=us-east-1
BEDROCK_REGION=us-east-1
FOOD_RECOGNITION_ORDER=classifier_first
LLM_CONFIDENCE_THRESHOLD=0.60
FOOD_CLASSIFIER_ENABLED=true
FOOD_CLASSIFIER_MODELS=chinese=/home/mario/data/welness360/s3/food-detection-model/chinese/nutrasmart_efficientnetv2s_best.pt,indian=/home/mario/data/welness360/s3/food-detection-model/indian/nutrasmart_efficientnetv2s_best.pt,thai=/home/mario/data/welness360/s3/food-detection-model/thai/thai_nutrasmart_efficientnetv2s_best.pt
FOOD_CLASSIFIER_THRESHOLD=0.60
FOOD_CLASSIFIER_DEVICE=cuda
```

**`backend/.env`** (FastAPI; the keys that matter locally):
```bash
AWS_PROFILE=moxa-dev
DEFAULT_DATA_REGION=us-east-1                 # -> bucket sci-neutrasmart-project-us (BUCKET_US default)
GOOGLE_CLIENT_ID=<OAuth web client id>        # same as VITE_GOOGLE_CLIENT_ID
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
CF_ORIGIN_SECRET=                             # keep EMPTY locally, or every request is rejected
AGENT_LOCAL_URL=http://localhost:8080         # send agent calls to the local agent, not AgentCore
```

**`maitribot/client/.env.local`** (frontend; create it). Without `VITE_API_URL` the UI talks to the
**production** API:
```bash
VITE_API_URL=http://localhost:8000/api
VITE_GOOGLE_CLIENT_ID=<same OAuth web client id as GOOGLE_CLIENT_ID>
```
Leave `VITE_ORIGIN_VERIFY_SECRET` unset locally.

### Start (three terminals, in this order)

```bash
# 1. Agent -> http://localhost:8080
cd backend/agent
set -a; . ./.env; set +a
venv_agent/bin/python -m app.nutrasmart_agent.main

# 2. Backend -> http://localhost:8000 (python-dotenv loads backend/.env)
cd backend
venv_backend/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. Frontend -> http://localhost:5174
cd maitribot/client
npm run dev
```

In VS Code, the launch configs **Agent (AgentCore :8080)** and **Backend API (FastAPI :8000)**
in `.vscode/launch.json` start steps 1 and 2 with the same `.env` files. Choose
`backend/agent/venv_agent` and `backend/venv_backend` as their interpreters.

After the boto3 credentials line, the agent prints nothing until the first request. That is
normal: it is up when `/ping` answers.

Health checks:
```bash
curl -s localhost:8080/ping
curl -s localhost:8000/health
```

### Test the food scan

1. Open http://localhost:5174 and sign in with Google.
2. Attach a food photo. The browser uploads it straight to `sci-neutrasmart-project-us`. Then
   `/api/analyze` → local agent → classifier ensemble → Bedrock nutrition call → nutrition card.
3. The agent log has one line per scan:
   ```
   food_analysis {"source": "classifier", "top": [{"model": "indian", "food_id": "aloo_gobi", "confidence": 0.87}], ...}
   ```
   - `source`: `classifier` if the winning cuisine model cleared `FOOD_CLASSIFIER_THRESHOLD`,
     `llm` if it fell back to the vision LLM.
   - `model`: which cuisine model won.

   The same data is saved with the scan under `recognition`.

The first scan after the agent starts loads the three checkpoints (a few seconds on GPU, about 15 s
on CPU). The frontend's request timeout is 30 s, so if that first scan times out, send it again.

To check the models without the frontend or AWS:
```bash
cd backend/agent
set -a; . ./.env; set +a
venv_agent/bin/python app/nutrasmart_agent/food_scan/scripts/classify_images.py photo.jpg
```

### Notes

- Local scans are real data in `sci-neutrasmart-project-us` under `users/<your Google user id>/`.
- To test another region locally, send the header `X-User-Country: IN|CA|DE…` to the backend.
  You also have to point the agent's `S3_BUCKET_NAME`/`S3_REGION` at that region's bucket.
- To use the **deployed** agent from the local backend, comment out `AGENT_LOCAL_URL` in
  `backend/.env`. Calls then go to the AgentCore ARNs in `AGENT_ARN_*`, which needs credentials
  for the deploy account.
