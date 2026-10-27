# 03 — Agent service (`backend/agent/app/nutrasmart_agent`)

Read-only review, 2026-10-26. Findings are referenced from the summary as `AGT-n`. Only the canonical copy was
reviewed; the four copies under `backend/agent/NutrasmartAgent` and `backend/agent/regions/*` are byte-identical (see
`01-repo-layout-and-infra.md`). Line numbers refer to the working tree on `feature/w360-full-multiple-models` with the
`feature/w360-full` merge staged.

**Pytest was not run.** `backend/agent/.venv/bin/python` is a symlink to `/usr/bin/python3.12`, which no longer exists
on this machine (only 3.11 / 3.13 / 3.14, none with boto3/pytest). The venv also lacks scipy/cv2/mediapipe/sklearn and
its numpy is 2.5.3 vs the pinned 2.0.2.

## Architecture summary

`main.py` (366 lines) is the AgentCore entrypoint: `@app.entrypoint invoke(payload)` dispatches on `payload["action"]`
through `_HANDLERS` to four handlers. `chat` and `summary` are implemented entirely inside `main.py` (two prompts,
three Strands `@tool` S3 readers, three S3 writers, a module-level `bedrock.converse` call, and a `BedrockModel` for the
Strands `Agent`). `analyze` delegates to `food_scan.analysis.analyze_food_images`, which fetches images from S3, runs a
lazily-loaded `HighestConfidenceClassifier` ensemble (EfficientNetV2-S per cuisine, checkpoints pulled from S3 via an
ETag-keyed disk cache) and/or the Bedrock vision LLM according to `FOOD_RECOGNITION_ORDER`, parses the LLM JSON,
backfills keys and returns a dict with a `recognition` audit block. `face_scan` delegates to
`face_scan_biomarkers.analysis.analyze_face_scan`, which downloads the video to a temp file, runs the vendored `dsv`
pipeline (MediaPipe FaceMesh + KLT tracking → POS rPPG / rBCG → windowed HR with a joblib-loaded sklearn gate, plus
experimental BP/SpO2 regressors) and returns a dict of `heart_rate`/`bp`/`spo2` status blocks. Each subpackage owns its
own settings, boto3 clients and lazy model cache (`lru_cache` singletons in `main.py`), while `main.py` keeps a *third*
pair of import-time boto3 clients for its own S3 layout and hands its S3 client to `face_scan` for the user bucket.
Results are persisted to `users/{uid}/scans|vitals_scans/{ts}.json`; errors are flattened to `{"error": str(e)}`, which
the FastAPI edge (`backend/app/agent_client.py:141`) re-raises as `AgentError`.

**Overall:** `food_scan` is the well-engineered reference (typed value objects, injectable settings, timeouts,
fakes-based tests); `main.py` and `face_scan_biomarkers` lag it on every axis of the owner's standards.

## Findings

### Config / hardcoding

1. **High** · Settings layer bypassed; four env vars read in two places · `main.py:49-54` vs
   `food_scan/settings.py:150-155` · `BEDROCK_MODEL_ID`, `BEDROCK_REGION`, `S3_BUCKET_NAME`, `S3_REGION` have two
   readers and two sets of defaults; `settings.py:5` says "callers never read os.environ themselves". → One
   `nutrasmart_agent/settings.py` composing `ChatSettings/SummarySettings/FoodScanSettings/BiomarkerSettings`, loaded
   once, injected.
2. **Med** · S3 key layout and timestamp format repeated as literals · `main.py:143,153,186,200,209,217-218,231-232` ·
   `users/{uid}/scans/`, `vitals_scans/`, `weekly_summary.txt`, `health_profile.json`, `%Y%m%dT%H%M%SZ` (×3).
   → `storage.py` with a `UserDataLayout` value object and a `ScanRecordStore` owning read/write.
3. **Med** · `max_tokens=2048` ×2 and `days=60` ×2 hardcoded while `summary_max_tokens` exists unused ·
   `main.py:137,263,289,299`; `food_scan/settings.py:65,161`. → Use settings; add `chat_max_tokens`, `summary_lookback_days`.
4. **Med** · `BiomarkerSettings` is an unvalidated, non-injectable env reader · `face_scan_biomarkers/settings.py:23-32` ·
   no `env` parameter, no range checks, no timeouts, `int()` raises a raw ValueError; style diverges from
   `food_scan.load_settings(env)` (both frozen dataclasses, neither pydantic — consistent there). → Mirror food_scan's
   `_get_int/_get_unit_float` helpers; add S3 timeouts, `max_video_seconds`, and the signal knobs below.
5. **High** · ≈65 DSP/product constants hardcoded in `dsv` · `signals.py:6-7,10,24,34,40,84-92,104,108,125,141,145,150,154`;
   `heart_rate.py:13,24,33,49,63,70,89`; `extract.py:26,30,65,68-69,80-81,142-143`; `features.py:46,67,73,75,119` ·
   HR band, 30 s/10 s window/hop, 15 s minimum, gate threshold 0.5, `min_snr_db=-3`, FaceMesh confidences, KLT
   `k=60/fb_max=0.5/reseed=0.8`, IBI bounds 0.33–1.5 s, 25 % median filter, 30 fps fallback, etc. are tuning knobs with
   product impact. → `HeartRateSettings`/`TrackingSettings` frozen dataclasses in the face `settings.py`, threaded
   through; keep pure epsilons (`1e-9`) as named module constants.
6. **Low** · `_JPEG_QUALITY = 85` and `_RESIZE_SIZE = 256` outside settings · `food_scan/analysis.py:53`,
   `recognition/efficientnet.py:29` · JPEG quality drives Bedrock payload size/cost; resize is eval-time preprocessing
   not stored in the checkpoint (224/mean/std at `:30-32` are legitimate checkpoint defaults). →
   `bedrock_jpeg_quality`, `classifier.resize_size`.
7. **Low** · User-facing strings and status codes as inline literals ·
   `face_scan_biomarkers/analysis.py:49-50,68,71,75-76,80-81`; `dsv/heart_rate.py:95,108`; `food_scan/analysis.py:199`.
   → `Status(str, Enum)` + one `messages.py` per package.

### Timeouts

8. **High** · `main.py` boto3 clients have no botocore `Config` · `main.py:57-58` → call sites
   `:145,157,185,199,208,219,233,296` ride botocore defaults; the summary `converse` (2048 tokens over 60 days of
   records) is the same call `food_scan/services.py:82-85` gives 120 s for. → One settings-driven client builder (#14).
9. **Med** · Strands `BedrockModel` built without `boto_client_config` · `main.py:263` · strands accepts it and
   otherwise applies its own default; chat is the longest LLM path (tool loop). → `BotocoreConfig(connect_timeout,
   read_timeout, retries)` from settings.
10. **Med** · face_scan S3 client has no `Config` · `face_scan_biomarkers/services.py:75` → `download_file` at
    `:41,59`; `user_s3` at `analysis.py:35,41` is main's bare client. → Same builder.
11. **Med** · No compute budget on video extraction · `face_scan_biomarkers/analysis.py:42`; `dsv/extract.py:138,149` ·
    `extract_video(max_sec=…)` exists but is never passed; a large video can process for minutes against the API's
    300 s read timeout (`backend/app/config.py:58`). → `max_video_seconds` setting, passed through; fail fast on duration.

### Structure / separation of concerns / duplication

12. **High** · `main.py` is not a thin entrypoint · owns chat + summary end to end: prompts `:62-132`, tools
    `:136-204`, S3 writers `:207-238`, Bedrock summary call `:287-304`. → Extract `chat/` (prompt, tool factory,
    handler) and `summary/`; `storage.py` for the user-data layout; `main.py` becomes app + composition root + dispatch
    (~80 lines).
13. **Med** · Duplicated and stale prompts · `food_scan/prompts.py:78-128` vs `main.py:62-132` · `WEEKLY_SUMMARY_PROMPT`
    identical; `CHAT_SYSTEM_PROMPT` differs (the `prompts.py` copy is the old, unused one). → Delete from `prompts.py`;
    single source in `chat/prompts.py`.
14. **Med** · Three boto3 client builders · `main.py:57-58` (bare), `food_scan/services.py:68-85` (Config),
    `face_scan_biomarkers/services.py:75` (bare). → `infra/aws.py: build_s3(region, timeouts)`, `build_bedrock(...)`.
15. **Med** · Two "load once, remember failure" caches · `food_scan/services.py:25-53` (`LazyClassifier`, locked) vs
    `face_scan_biomarkers/services.py:22-65` (`ModelCache`, unlocked, string keys, two near-identical download blocks
    `:39-43` and `:57-60`). → One generic `Lazy[T]` (lock + memo + failure memo); face models should reuse
    `recognition/model_store.resolve_model_path` (ETag disk cache, atomic replace) instead of re-downloading to
    `NamedTemporaryFile` on every cold start.
16. **Med** · Duplicated size guard and Bedrock response unwrap · `food_scan/analysis.py:142-145` vs
    `face_scan_biomarkers/analysis.py:35-37`; `main.py:301` vs `food_scan/analysis.py:185`. →
    `storage.ensure_object_size(...)`, `bedrock.converse_text(...)`.
17. **Med** · `dsv` is a vendored research module, not a package · `extract.py:1-6` docstring says "Saves an .npz per
    video" (it doesn't); dataset-only code: folder-of-images frames `:19-26`, `resample_uniform` `:118-135`,
    `fps/timestamps` params `:138`, `HRGate.save/load` `heart_rate.py:78-86`; `import glob, os, re` on one line; empty
    `dsv/__init__.py`. → Prune to the inference path and split by concern (`tracking.py`, `rppg.py`, `rbcg.py`,
    `beats.py`, `features.py`), or freeze as vendored with provenance/version recorded.
18. **Low** · Ensemble is a clean composite, but `model` leaks into the base result · `ensemble.py:19-34` properly
    implements `FoodClassifier`; `ClassificationResult.model` (`base.py:40`) is set only by the ensemble, so
    single-model results carry `None` (`test_analysis.py:53` asserts `[None, None]`). → Factory tags every member
    result, or return an ensemble-specific result. Members run sequentially (3× latency on 2 threads) — acceptable for
    now (YAGNI), but note it.
19. **Med** · Ensemble load is all-or-nothing and failure is permanent · `factory.py:48-51`;
    `food_scan/services.py:48-53` · One missing checkpoint or a transient S3 error at cold start disables the classifier
    for the container's lifetime, silently moving all traffic to the vision LLM. → Load members individually, skip
    failures with a logged warning, retry after a cooldown; emit a metric.

### Typing / data models

20. **High** · Invocation contract is untyped dicts · `main.py:266-339,351` · `payload["user_id"]`, `img["key"]`
    KeyErrors become `{"error": "'key'"}`; the API side is dicts too (`agent_client.py:80`, `routes/analyze.py:62-64`,
    `routes/facescan.py:39-42`). → `Action(str, Enum)`; frozen `ChatRequest/AnalyzeRequest/FaceScanRequest` with
    `from_payload()` raising `InvalidRequest`; typed response dataclasses with `to_dict()`; share the schema with the API.
21. **Med** · Food analysis payload is a mutable loose dict · `food_scan/analysis.py:77` (`Attempt.analysis: dict`),
    `_backfill` mutates `:203-211`, `analysis["confidence"]=` `:235,243`, `_recognition_block` `:290-303`;
    `MICRONUTRIENT_KEYS/_TOP_LEVEL_KEYS` `:45-52` duplicate the prompt schema. → `NutritionAnalysis` +
    `RecognitionBlock` dataclasses; derive prompt schema and key lists from one typed source.
22. **High** · face_scan is dict-only end to end · `extract.py:165-168` (`raw` dict; empty case returns 1-D `roi_rgb`,
    inconsistent with `(T,R,3)`), `heart_rate.py:48-58,95-115`, `services.py:51`, `analysis.py:44-83`. → `RawTraces`,
    `WindowFeatures`, `HeartRateResult`, `RegressionBundle`, `VitalsResult` dataclasses; `Status` Enum;
    `HRGate.from_bundle()`.
23. **Low** · Clients typed as `object`/untyped · `food_scan/services.py:61-63`, `model_store.py:31,45`, face
    `services.py:29`, `analysis.py:30`. → `S3Client`/`BedrockRuntime` `Protocol`s (the conftest fakes already duck-type them).
24. **Low** · `ImageRef.content_type` accepted but never used · `food_scan/analysis.py:69`, `main.py:310`. → Drop from
    the contract or use it.

### DI / global state

25. **High** · Import-time AWS clients and module globals · `main.py:57-58`; tools close over `s3`/`S3_BUCKET_NAME`
    (`:145,157,185,199,208,219,233`) → `main.py` cannot be imported in tests; contradicts `food_scan/services.py:3-4`.
    → Composition root inside the lazily built services; tools via `make_tools(store) -> list[Tool]` or a class.
26. **Med** · Process-global torch state mutated inside a constructor · `efficientnet.py:45-46` (`allow_tf32`), `:129`
    (`set_num_threads`) — once per ensemble member. → Do once at the `build_classifier` boundary, documented as a side effect.
27. **Low** · `lru_cache` singletons as hidden composition root · `main.py:242-253` · acceptable, but settings are read
    lazily on first request. → Load settings at startup (pure, fails fast); build clients on first request.
28. **Low** · `ModelCache` not thread-safe · face `services.py:22-65` (AgentCore runs sync handlers in a threadpool).
    → Covered by the shared `Lazy[T]` in #15.

### Logging / errors

29. **Med** · Mixed logging styles, no correlation id · `food_scan/analysis.py:322`, `efficientnet.py:134`,
    `model_store.py:39` log JSON-in-message; `main.py` and face_scan use printf-style; `logging.basicConfig`
    (`main.py:45`) default formatter. → One JSON formatter configured in `main`; `logger.info("food_analysis",
    extra={...})`; bind the AgentCore session id via a filter.
30. **Med** · No package-owned error types beyond `ClassifierError` · request validation uses `ValueError`
    (`food_scan/analysis.py:114,123,136,138,145,226`; face `analysis.py:37`; `main.py:291,333`); `invoke`
    (`main.py:358-362`) flattens every exception to `{"error": str(e)}`, which the API re-raises verbatim →
    botocore/torch/mediapipe internals leak to clients, and an expected condition ("No food scans") travels as an
    exception. → `AgentError` base with `InvalidRequest`, `FoodScanError`, `BiomarkerUnavailable`; map known errors to
    user-safe message + code, unknown to a generic message with full trace logged.
31. **Low** · Broad `except Exception` · `main.py:189,203` (AccessDenied/throttling read as "no profile"), face
    `services.py:45,62`, `analysis.py:62-64`. → Catch `ClientError`, check `NoSuchKey`; log anything else at error.

### Docs / tests

32. **High** · `face_scan_biomarkers` has zero tests (confirmed) · pure functions (`windows`, `clean_ibis`, `hrv_time`,
    `fuse_ibis`, `match_beats`, `pos`/`spectral_peak` on a synthetic sine, `measure_hr` on synthetic traces with a
    known HR, `analyze_face_scan` with fake S3 + stub gate) are cheap to cover. → `face_scan_biomarkers/tests/` with
    synthetic-signal fixtures; put `extract_video` behind a `FrameSource` protocol so it is testable without mediapipe.
33. **Med** · food_scan test gaps · `LazyClassifier` (failure memo, locking), `build_classifier` (unknown backend,
    partial failure), `extract_json` returning a non-dict, and all of `main.py` (blocked by #25). The existing 50 tests
    are good unit tests: in-memory fakes (`conftest.py:23-78`), no network/torch, both recognition orders and
    tie/threshold edges covered; `test_efficientnet_checkpoint.py` is an opt-in smoke test.
34. **Med** · Docstrings/type hints missing in dsv · ≈30 undocumented public functions (`signals.py:10,15,77,139,148`;
    `heart_rate.py:61,70-86`; `features.py:87`; `extract.py:15,50,65-76`); zero annotations in all four dsv modules;
    face `settings.py:14,23`, `services.py:69,74` undocumented; `main.py:207,216,266,287,307`. → Annotate with
    `NDArray[np.float64]`, document shapes and units.
35. **Med** · README/docstring drift · `README.md:19`, `requirements-base.txt:7`, `Dockerfile:6` say `app/dsv/` (now
    `face_scan_biomarkers/dsv/`); `README.md:20` cites `BP_measurement/README.md` (not in repo); `README.md:126` runs
    `pytest -q app tests` (no `tests/` dir); `README.md:147,210` reference `scripts/evaluate_classifier.py` (moved);
    `README.md:113-121` and root `README.md:31-45,69` hardcode `/home/mario/...` and `venv_agent` (absent; `.venv` is
    the CUDA venv); `main.py:8-9` says `face_scan` returns only `heart_rate`; `README.md:26` omits `_save_vitals_scan`.

### Requirements / Docker

36. **High** · `evaluate_classifier.py` broken by relocation · `food_scan/scripts/evaluate_classifier.py:37` uses
    `parents[1]` (resolves to `.../food_scan`), left over from its original `backend/agent/scripts/` home (commit
    `13888b6`); `from app.nutrasmart_agent...` fails unless `PYTHONPATH` is set. `classify_images.py:23` correctly uses
    `parents[4]`. → Move both to `backend/agent/tools/` outside the deployable package, run via `python -m`, drop the
    `sys.path` hacks.
37. **Med** · Dev tooling and tests ship in the production image · `Dockerfile:20` `COPY app/ ./app/`, no
    `.dockerignore`. → Add `.dockerignore` (tests, scripts, `__pycache__`); relocate scripts (#36).
38. **Med** · Requirements drift · `requirements-base.txt:16` `opencv-python-headless` unpinned among pins; `:2-5`
    lower bounds only (venv has strands 1.57.1, agentcore 1.24.0); `pytest==9.1.1` pinned in both
    `requirements-dev.txt:2` and `requirements-gpu.txt:9`; `numpy==2.0.2` pinned vs venv 2.5.3; no lock file despite
    `uv`. → `requirements-dev.txt` = tooling only, included from either target; `uv pip compile` lock per target; pin opencv.
39. **Med** · mediapipe/numpy pairing unverified · `requirements-base.txt:11,17` (`numpy==2.0.2` + `mediapipe==0.10.14`)
    · No authoritative statement on numpy 2 support for 0.10.14 was found; public projects pair it with numpy 1.26.x,
    and later mediapipe releases drop the legacy `mediapipe.solutions` API used at `extract.py:142`, so the pin is
    load-bearing; `Dockerfile:12-15` already flags the arm64 wheel as unverified. → Resolve in a clean arm64/py3.12
    env, record the result in the Dockerfile comment, pin numpy accordingly.
40. **Low** · Dockerfile hygiene · `Dockerfile:2` constant `--platform` in `FROM`; `:9` apt `ffmpeg` likely redundant
    with opencv-headless's bundled codecs (verify); no `USER`, no `PYTHONUNBUFFERED=1`; `:24`
    `ENV FOOD_CLASSIFIER_CACHE_DIR` duplicates `settings.py:137`.
41. **Low** · Heavy imports at process start for every action · `main.py:41-42` → face `analysis.py:15-17` →
    `extract.py:8-10` (cv2, mediapipe), `heart_rate.py:10` (scipy); `services.py:3-5` claims laziness but only
    joblib/pandas are lazy. → Import `dsv` inside `analyze_face_scan`, as `factory.py:26` does for torch.

### YAGNI / dead code

42. **Med** · Dead code inventory · `food_scan/prompts.py:78-128`; `food_scan/settings.py:65,161`
    (`summary_max_tokens`); `food_scan/services.py:64,91` (`bedrock_config` stored, never read);
    `extract.py:19-26,118-135,138` (image-folder frames, `resample_uniform`, `fps/timestamps`);
    `heart_rate.py:78-86` (`HRGate.save/load`); face `analysis.py:66` (`name == key_out` always). → Delete.
43. **Low** · `CLASSIFIER_BACKENDS` registry with one backend · `factory.py:33-35` · cheap and documented; acceptable,
    but don't generalize further until a second architecture exists.

### Correctness smells

44. **High** · `key` not scoped to `user_id` (IDOR) · `main.py:331-334` (face), `:310` (analyze `images[].key`) · The
    agent fetches any object in the bucket; the API forwards client-supplied keys unchecked (`routes/facescan.py:41`,
    `routes/analyze.py:64`). → Enforce `key.startswith(f"users/{user_id}/")` in the typed request validation (#20),
    and in the API.
45. **Med** · `joblib.load` of S3 objects executes arbitrary pickles · face `services.py:42,60` · contrast with
    `efficientnet.py:52` `weights_only=True`. → Acceptable only with a write-locked bucket; document it, or move to
    ONNX/skops.
46. **Med** · `list_objects_v2` unpaginated · `main.py:145` · >1000 scan objects truncates (lexical order = oldest
    first, so the newest records are dropped). → Paginator with `StartAfter` derived from the cutoff timestamp.
47. **Med** · Low-fps videos crash the HR path · `signals.py:11` `butter` raises when `hi/(fs/2) >= 1` (bands up to
    8 Hz at `:92`; fs ≤ 16 fps), unguarded inside `window_features` (`heart_rate.py:53`) → surfaces as `{"error": ...}`.
    → Validate `fs` against the highest band (or clamp to `0.45·fs`) and return `withheld` with a reason.
48. **Low** · No-face video reports "scan too short" · `extract.py:165` returns empty traces; `heart_rate.py:92-96`.
    → Distinct `no_face_detected` status.
49. **Low** · Resource leaks · `extract.py:142` `FaceMesh` never `.close()`d; `cap.release()` (`:38`) skipped on early
    `break` (`:149`) or exception. → Context managers / `try/finally`.
50. **Low** · `extract_json` may return a non-dict · `food_scan/analysis.py:104,111` → `_llm_score` `.get`
    AttributeError. → `isinstance(obj, dict)` guard → graceful result.
51. **Low** · Control flow on tool output text · `main.py:290,293` `startswith("No food scans")`. → Typed results from
    the storage layer; render text only for the LLM.

## Quick wins vs structural changes

**Quick wins (hours)**
- Add botocore `Config` to `main.py:57-58`, face `services.py:75`, and `boto_client_config` to `BedrockModel` (`main.py:263`), sourced from settings (#8–10).
- Enforce `users/{user_id}/` prefix on `key`/`images[].key` in the handlers (#44).
- Delete dead prompts/fields/dsv branches (#13, #42); fix `evaluate_classifier.py` `parents[1]` or move scripts out (#36); add `.dockerignore` (#37).
- Replace `2048`/`60` literals with settings (#3); pass `max_sec` to `extract_video` (#11); guard `fs` vs filter band (#47); `isinstance(dict)` in `extract_json` (#50).
- Paginate `list_objects_v2` (#46); fix README paths/commands (#35); pin `opencv-python-headless`, dedupe `pytest` pin (#38).

**Structural (days)**
- Split `main.py` into `chat/`, `summary/`, `storage.py`, `infra/aws.py`, with a single top-level settings module and a composition root; make tools injectable (#1, #12, #14, #25).
- Typed request/response contract shared with the API (`Action` enum + dataclasses) and a package-owned error hierarchy with safe error mapping (#20, #30).
- Bring `face_scan_biomarkers` up to `food_scan`'s standard: validated injectable settings holding the DSP knobs, dataclass results, `Status` enum, shared `Lazy[T]`/model store, test suite on synthetic signals (#4, #5, #15, #22, #32).
- Prune/split `dsv` into a proper signal-processing package with docstrings and type hints (#17, #34).
- Per-member ensemble loading with retry (#19); JSON logging with session correlation (#29).

## Metrics

**Lines of code** (Python; production 2,258; tests 597; scripts 359)
- `main.py` 366 · `__init__.py` 0
- food_scan (1,107): `analysis.py` 336, `settings.py` 170, `prompts.py` 129, `services.py` 93, `__init__.py` 3;
  `recognition/`: `efficientnet.py` 164, `model_store.py` 59, `base.py` 52, `factory.py` 52, `ensemble.py` 34, `__init__.py` 15
- face_scan_biomarkers (785): `analysis.py` 83, `services.py` 76, `settings.py` 32, `__init__.py` 12; `dsv/`:
  `extract.py` 172, `signals.py` 155, `features.py` 140, `heart_rate.py` 115, `__init__.py` 0
- scripts: `evaluate_classifier.py` 299, `classify_images.py` 60
- tests: `test_analysis.py` 258, `test_settings.py` 94, `conftest.py` 83, `test_model_store.py` 61, `test_ensemble.py` 52,
  `test_efficientnet_checkpoint.py` 48, `__init__.py` 1
- Non-Python: `README.md` 258, `Dockerfile` 29, requirements 17+8+9+2

**Longest functions:** `compute_features` 54 (`features.py:87-140`), `analyze_face_scan` 54 (face `analysis.py:30-83`),
`evaluate_classifier.main` 53 (`:243-295`), `get_recent_scans` 42 (`main.py:137-178`), `_rbcg_ensemble` 39
(`features.py:46-84`), `extract_video` 35 (`extract.py:138-172`), `RigidTracker.update` 32 (`extract.py:84-115`),
`window_features` 31 (`heart_rate.py:28-58`), `analyze_food_images` 31 (`analysis.py:306-336`), `measure_hr` 27
(`heart_rate.py:89-115`).

**Hardcoded literals outside settings:** ≈90 — `main.py` ≈18 (4 env defaults duplicating settings, 3× timestamp
format, 6 S3 key strings, 2× 2048, 2× 60, 2 text sentinels); `food_scan` ≈6 (JPEG 85, resize 256, plus checkpoint
defaults 224/mean/std/architecture, acceptable as named constants); `face_scan_biomarkers` ≈65 (≈25 product/tuning
knobs that belong in settings, the rest DSP epsilons/algorithm constants that should at least be named).

**I/O without explicit timeout:** 4 construction sites (`main.py:57`, `main.py:58`, `main.py:263`, face
`services.py:75`) covering 13 call sites (`main.py:145,157,185,199,208,219,233,283,296`; face `services.py:41,59`;
face `analysis.py:35,41`); plus no compute deadline on `extract_video`. All `food_scan` clients carry explicit timeouts.

**Tests:** 7 files in `food_scan/tests/` (5 test modules + conftest + `__init__`), 50 test functions (25 analysis,
13 settings, 5 ensemble, 5 model_store, 2 opt-in checkpoint smoke), ≈95 `assert` statements; all unit-level with
hand-rolled fakes. `face_scan_biomarkers`: 0 test files. **pytest: not run** (venv interpreter missing).
