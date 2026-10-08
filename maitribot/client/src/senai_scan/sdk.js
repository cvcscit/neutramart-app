// Shen.AI SDK runtime loader (singleton).
//
// The SDK is a WASM runtime, so it must be created once per page and torn down
// explicitly. Vite cannot bundle its .wasm / worker files, so they are served from
// public/shenai-sdk (see the dev/build scripts in package.json) and `locateFile`
// points the runtime there.

// The SDK is loaded at RUNTIME from /shenai-sdk/ (copied out of node_modules by
// `npm run prepare:shenai`), not imported as an npm module.
//
// Importing "@shenai/sdk" directly makes Vite's dep optimizer pre-bundle it, which
// rewrites the path of the worker the SDK spawns:
//   "…/.vite/deps/shenai_sdk.mjs?worker_file&type=module" — file does not exist
// The worker then never loads and initialization hangs forever. Loading from the public
// directory keeps the SDK's own relative paths intact (this is the approach the SDK's
// js-minimal example uses), and also keeps the 33MB wasm out of our bundle.
// Built at call time into a fully-qualified URL. A bare "/shenai-sdk/index.mjs" literal
// gets constant-folded and resolved by Vite's import analysis, which then refuses it
// ("This file is in /public … should not be imported from source code"). An absolute
// http(s) URL computed at runtime is treated as external and left alone.
const sdkEntryUrl = () => new URL("/shenai-sdk/index.mjs", window.location.href).href;

const API_KEY = import.meta.env.VITE_SHENAI_API_KEY ?? "";

let runtimePromise = null; // the WASM runtime, loaded at most once per page
let runtime = null;

// The runtime is a ~33MB WASM binary; fetching is quick locally but compiling it takes
// seconds (longer in Safari), so callers get stage updates rather than one long wait.
const LICENCE_TIMEOUT_MS = 45_000;

/** Load the WASM runtime (idempotent). Does not activate the licence. */
function loadRuntime(onProgress) {
  if (!runtimePromise) {
    // @vite-ignore keeps Vite from resolving this at build time, so it stays a plain
    // runtime fetch of the file in public/.
    runtimePromise = import(/* @vite-ignore */ sdkEntryUrl())
      .then((mod) =>
        mod.default({
          locateFile: (filename) => "/shenai-sdk/" + filename,
          onWasmLoadingProgress: onProgress,
          // The SDK paints its own loading animation into #mxcanvas while the wasm
          // downloads, which is better feedback than a static label.
          enablePreloadDisplay: true,
          preloadDisplayCanvasId: "mxcanvas",
        })
      )
      .then((sdk) => {
        runtime = sdk;
        return sdk;
      })
      .catch((err) => {
        runtimePromise = null; // let a later attempt retry
        throw err;
      });
  }
  return runtimePromise;
}

export class ShenaiInitError extends Error {}

/**
 * The SDK hard-requires SharedArrayBuffer, which browsers only expose on
 * cross-origin-isolated pages (see @shenai/sdk's README). Checking up front gives a
 * precise, actionable message instead of the SDK's generic "browser incompatible".
 */
function assertBrowserCanRunSdk() {
  const isolated = typeof crossOriginIsolated !== "undefined" ? crossOriginIsolated : null;
  const hasSab = typeof SharedArrayBuffer !== "undefined";

  console.log(
    `[senai_scan] crossOriginIsolated=${isolated} SharedArrayBuffer=${hasSab} ua=${navigator.userAgent}`
  );

  if (!hasSab) {
    throw new ShenaiInitError(
      `This browser can't run the Shen.AI scan: SharedArrayBuffer is unavailable ` +
        `(crossOriginIsolated=${isolated}). The SDK requires COOP/COEP isolation headers, ` +
        `which we can't set on this page without breaking Google login — see ` +
        `src/senai_scan/README.md. Try Chrome, or move the scan to its own isolated page.`
    );
  }
}

/**
 * Load + licence-activate the SDK, ready to measure.
 * `userId` lets Shen.AI tie calibration/history to a person; we pass the user's email.
 */
export async function initShenai(userId = "", settings = {}, onStage = () => {}) {
  if (!API_KEY) {
    throw new ShenaiInitError(
      "Missing VITE_SHENAI_API_KEY. Add your Shen.AI API key (developer.shen.ai) to maitribot/client/.env"
    );
  }

  assertBrowserCanRunSdk();

  const t0 = performance.now();
  onStage("runtime", 0);
  const sdk = await loadRuntime((p) => {
    // The SDK reports this as a percentage (0-100), not a 0..1 fraction; normalise so
    // either convention renders sensibly.
    const n = typeof p === "number" ? p : 0;
    onStage("runtime", n > 1 ? n / 100 : n);
  });
  console.log(`[senai_scan] WASM runtime ready in ${Math.round(performance.now() - t0)}ms`);

  // Re-initializing an already-initialized runtime throws; reuse it instead.
  if (sdk.isInitialized()) return sdk;

  const t1 = performance.now();
  onStage("licence");
  await new Promise((resolve, reject) => {
    // The SDK's callback is the only completion signal; if its licence request stalls it
    // never fires, so without this the page would sit on "loading" forever.
    const timer = setTimeout(() => {
      reject(new ShenaiInitError(
        `Shen.AI licence activation timed out after ${LICENCE_TIMEOUT_MS / 1000}s. ` +
        `The SDK loaded fine, so this is the licence request — check your network, or ` +
        `whether the API key is valid for this origin.`
      ));
    }, LICENCE_TIMEOUT_MS);

    sdk.initialize(API_KEY, userId, settings, (result) => {
      clearTimeout(timer);
      if (result === sdk.InitializationResult.OK) {
        console.log(`[senai_scan] licence activated in ${Math.round(performance.now() - t1)}ms`);
        resolve();
      } else {
        reject(new ShenaiInitError(licenceErrorMessage(sdk, result)));
      }
    });
  });

  return sdk;
}

function licenceErrorMessage(sdk, result) {
  if (result === sdk.InitializationResult.INVALID_API_KEY) {
    return "Shen.AI rejected the API key. Check VITE_SHENAI_API_KEY.";
  }
  if (result === sdk.InitializationResult.CONNECTION_ERROR) {
    return "Could not reach Shen.AI to activate the licence. Check your connection.";
  }
  return "Shen.AI failed to initialize (internal error).";
}

/**
 * Release the camera + measurement session but keep the WASM runtime loaded, so
 * reopening the scanner doesn't pay the (slow) runtime load again.
 */
export function deinitShenai() {
  if (runtime?.isInitialized()) runtime.deinitialize();
}
