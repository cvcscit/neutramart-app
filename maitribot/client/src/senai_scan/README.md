# senai_scan — Shen.AI vitals scan

Browser-side vitals scan using the [Shen.AI SDK](https://github.com/mxlaboratories/shenai-sdk)
(`@shenai/sdk`), as an **alternative** to `../FaceScanModal.jsx`.

## How it differs from the in-house scan

| | `FaceScanModal.jsx` (in-house) | `senai_scan` (Shen.AI) |
|---|---|---|
| Where it runs | Records video → uploads to S3 → backend `face_scan_biomarkers/` | Entirely in the browser (WASM) |
| Network | Presigned upload + `/face-scan` call | None — no video leaves the device |
| Models | Our own rPPG pipeline + trained HR/BP/SpO2 models | Shen.AI's closed models |
| Licensing | Ours | Requires a Shen.AI API key (paid plans gate some metrics) |
| Returns | HR, BP, SpO2 | HR, BP, HRV, breathing rate, stress, parasympathetic activity — **no SpO2** |

Both expose the same props (`email`, `onClose`, `onResult`) and `onResult` receives the
same vitals shape, so they're interchangeable from `App.jsx`'s point of view.

## Setup

1. **Get an API key** from the [Shen.AI Developer Portal](https://developer.shen.ai).
2. **Add it to `maitribot/client/.env`** (gitignored):
   ```
   VITE_SHENAI_API_KEY=your_key_here
   ```
3. `npm install` (already includes `@shenai/sdk`), then `npm run dev`.

Without a key the modal shows an error telling you the key is missing — it won't fail silently.

## Why the build config is unusual

Three things in `package.json` / `vite.config.js` exist specifically for this SDK:

- **`npm run prepare:shenai`** copies `node_modules/@shenai/sdk` into `public/shenai-sdk`.
  Vite can't bundle the SDK's `.wasm` and worker files, so they're served statically
  instead, and `sdk.js` passes `locateFile` to point the runtime there. This runs
  automatically as part of `dev` and `build`.
- **`worker: { format: "es" }`** — the SDK ships ES-module workers; Vite's default
  (`iife`) can't load them.

## Why we do NOT set COOP/COEP (unlike the SDK's example)

The SDK's own example sets cross-origin-isolation headers
(`Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy: require-corp`)
to enable `SharedArrayBuffer`. **Don't add them here** — `COOP: same-origin` severs
`window.opener`, which breaks the Google Identity Services login popup this app uses.
(`COEP: credentialless` doesn't help: full isolation still requires `COOP: same-origin`.)

That's safe because `SharedArrayBuffer` is optional for this SDK, not required — in
`shenai_sdk.mjs` the atomics path is guarded and falls back when it's unavailable:

```js
if (typeof Atomics === "undefined" || typeof SharedArrayBuffer === "undefined"
    || !(F.buffer instanceof SharedArrayBuffer)) return 0;  // degrades, doesn't throw
```

So we give up one camera-counter optimization and keep working auth. If a future SDK
version hard-requires isolation, serve the scan from its own isolated page/iframe rather
than isolating the whole app.

## Files

- `sdk.js` — loads + licence-activates the WASM runtime once per page; `deinitShenai()`
  releases the camera on modal close while keeping the runtime warm for reopening.
- `adapter.js` — maps Shen.AI's `MeasurementResults` onto the vitals shape
  `VitalsCard` renders, plus `statusText()` for face/measurement-state guidance.
- `SenaiScanModal.jsx` — the modal. Renders `<canvas id="mxcanvas">` (the SDK draws its
  camera view + overlay into it), polls measurement state, and calls `onResult` on
  `FINISHED`.

## Preset

`THIRTY_SECONDS_ALL_METRICS` — matches the in-house scan's 30s duration while still
returning the full metric set including BP. Other options (`ONE_MINUTE_ALL_METRICS`,
`QUICK_HR_MODE`, …) are in `sdk.MeasurementPreset`; longer presets give better BP
confidence.
