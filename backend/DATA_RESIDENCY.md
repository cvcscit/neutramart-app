# NutraSmart — Data Residency

**Status:** Live in production (AWS account `209479309679`)
**Last updated:** 2026-07-26

NutraSmart stores and processes each user's data in an AWS region chosen by the user's
geographic location. A user's country is detected automatically at the edge; all of that
user's data is then kept in — and analyzed by — that region's infrastructure.

---

## 1. Region mapping

| User location | Data region | S3 bucket (data at rest) | In-region AI model |
|---|---|---|---|
| 🇺🇸 United States | `us-east-1` | `sci-neutrasmart-project-us` | Claude Haiku 4.5 (`global.` profile) |
| 🇮🇳 India | `ap-south-1` | `sci-neutrasmart-project` *(original bucket, reused)* | Claude Haiku 4.5 (`global.` profile) |
| 🇨🇦 Canada | `ca-central-1` | `sci-neutrasmart-project-ca` | **Amazon Nova Lite (`ca.` profile)** |
| 🇪🇺 Europe / EEA / UK / CH | `eu-west-1` | `sci-neutrasmart-project-eu` | Claude Haiku 4.5 (`global.` profile) |
| Anywhere else / unknown | `us-east-1` *(default)* | `sci-neutrasmart-project-us` | Claude Haiku 4.5 (`global.` profile) |

**Country → region** is defined in [`app/config.py`](app/config.py) (`COUNTRY_REGION`,
`REGION_BUCKETS`, `DEFAULT_DATA_REGION`). Europe covers all EU-27 plus Iceland,
Liechtenstein, Norway, the United Kingdom, and Switzerland.

### Model choice rationale
- **US / EU / India** use Claude Haiku 4.5 via the `global.` inference profile (uniform model).
- **Canada** is special: **no Anthropic model has a Canada-resident inference profile.** The
  only Canada-resident multimodal model is **Amazon Nova Lite (`ca.amazon.nova-lite-v1:0`)**,
  so Canadian users are served by Nova Lite to keep *processing* inside Canada. The agent uses
  the Bedrock **Converse** API, which is model-agnostic, so this is purely per-runtime config.

---

## 2. How a user's region is detected

1. Requests reach the API through CloudFront (`api.nutrasmart.in`, distribution `E17LBHEJ1KKM70`).
2. CloudFront injects the **`CloudFront-Viewer-Country`** header (ISO-3166 alpha-2), forwarded
   to the origin by the managed origin-request policy
   **`Managed-AllViewerAndCloudFrontHeaders-2022-06`** (`33f36d7e-…`).
3. The FastAPI edge resolves the region in [`app/regions.py`](app/regions.py):
   `CloudFront-Viewer-Country` → `X-User-Country` (manual/testing override) → `DEFAULT_DATA_REGION`.
4. The resolved region yields the bucket, a region-bound S3 client, and the regional AgentCore
   runtime ARN — bundled by the `get_data_context` FastAPI dependency and used by every route.

> If the country header is missing (e.g., CloudFront misconfigured, or direct ALB access),
> the user falls back to `DEFAULT_DATA_REGION` (`us-east-1`). Nothing breaks; data just lands
> in the default region.

---

## 3. Architecture

```
Frontend (unchanged)  ──HTTPS──▶  CloudFront (api.nutrasmart.in)
                                     │  injects CloudFront-Viewer-Country
                                     ▼
                          FastAPI edge (ECS Fargate, ap-south-1)
                          • resolves region from country
                          • presigns uploads to the REGIONAL bucket
                          • routes analyze/chat/summary to the REGIONAL agent
                                     │
        ┌───────────────┬───────────┴───────────┬────────────────┐
        ▼               ▼                        ▼                ▼
   us-east-1        ap-south-1              ca-central-1       eu-west-1
   AgentCore        AgentCore               AgentCore          AgentCore
   + US bucket      + IN bucket             + CA bucket        + EU bucket
   Haiku (global.)  Haiku (global.)         Nova Lite (ca.)    Haiku (global.)
```

- **Image uploads** go **browser → regional bucket directly** via a presigned URL — image
  bytes never pass through the edge.
- **Analysis / chat / summary** run entirely inside the user's regional AgentCore runtime
  (fetches the regional bucket in-region, calls in-region Bedrock).

---

## 4. Deployed resources

**Per region:** an S3 bucket, an ECR repo (`nutrasmart-agent`), and an AgentCore runtime.

| Region | AgentCore runtime ARN |
|---|---|
| us-east-1 | `…:us-east-1:…runtime/nutrasmart_agent-U19HH23bO9` |
| ap-south-1 | `…:ap-south-1:…runtime/nutrasmart_agent-wDJ4h65kNp` |
| ca-central-1 | `…:ca-central-1:…runtime/nutrasmart_agent-do2fzV7MXV` |
| eu-west-1 | `…:eu-west-1:…runtime/nutrasmart_agent-l9gyWY6wir` |

ARNs are stored in SSM (ap-south-1) as `/nutrasmart/agent-arn-{us,in,ca,eu}` and injected into
the ECS task definition as `AGENT_ARN_{US,IN,CA,EU}`. Bucket names are injected as
`BUCKET_{US,IN,CA,EU}`; default region as `DEFAULT_DATA_REGION`.

**IAM**
- `nutrasmart-agent-runtime-role` — Bedrock invoke (`foundation-model/*` + `inference-profile/*`,
  covers Haiku and Nova), S3 read/write on all 4 buckets, ECR pull, CloudWatch Logs.
- `nutrasmart-ecs-task-role` (edge) — S3 on all 4 buckets, `bedrock-agentcore:InvokeAgentRuntime`
  in all 4 regions.

**Buckets** — private (all public access blocked), CORS allows browser `PUT` from
`https://nutrasmart.in` and localhost dev origins.

---

## 5. What is / isn't resident

| Data / operation | Resident in user's region? |
|---|---|
| Uploaded images (S3) | ✅ Yes — browser → regional bucket |
| Scan records, meals, summaries, health profile (S3) | ✅ Yes — regional bucket |
| Food-image analysis, chat, summary generation (AI) | ✅ Yes — regional AgentCore + in-region Bedrock |
| `GET /meals`, `/nutrition/summary`, `/weekly-summary`, chat message text | ⚠️ **Transits the ap-south-1 edge** |

### Known limitation — single-region edge
The FastAPI edge runs only in **ap-south-1**. Read endpoints and chat text briefly transit that
edge even for non-India users. For **100% edge-side residency**, deploy the edge in all four
regions and use CloudFront latency/geo routing to the nearest one (the frontend contract stays
the same). This is a scoped follow-up, not yet done.

> Note on `global.` inference profiles: US/EU/India processing uses the `global.` Claude profile,
> which AWS may route across regions within its geo. Storage is strictly regional; if strict
> in-region *processing* is later required for these regions too, switch them to region-scoped
> profiles (`us.` / `eu.` / `apac.`) — Canada already uses a region-scoped model.

---

## 6. Verifying & extending

**Verify routing (mapping):**
```bash
# country → region → bucket resolution
python3 - <<'PY'
from app.config import COUNTRY_REGION, REGION_BUCKETS, DEFAULT_DATA_REGION
for cc in ["US","IN","CA","DE","GB","JP",None]:
    r = COUNTRY_REGION.get((cc or "").upper(), DEFAULT_DATA_REGION)
    print(cc, "->", r, REGION_BUCKETS[r])
PY
```

**Verify a regional runtime directly:**
```bash
aws bedrock-agentcore invoke-agent-runtime --region <region> \
  --agent-runtime-arn <arn> --runtime-session-id "$(python3 -c 'import uuid;print("s"+uuid.uuid4().hex*2)')" \
  --payload "$(printf '{"action":"chat","user_id":"test","message":"hi"}' | base64)" /dev/stdout
```

**Add a new region:**
1. Create the bucket (block public access, add CORS).
2. Create an ECR repo + push the ARM64 agent image.
3. Create an AgentCore runtime (env: `S3_BUCKET_NAME`, `S3_REGION`, `BEDROCK_REGION`,
   `BEDROCK_MODEL_ID` — verify the model has a region-resident profile).
4. Extend both IAM roles to include the new bucket/region.
5. Add the country codes to `COUNTRY_REGION`, the bucket to `REGION_BUCKETS`, the ARN to
   `REGION_AGENT_ARNS` (SSM + task-def env), and redeploy the edge.
