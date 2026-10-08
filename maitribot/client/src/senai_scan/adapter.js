// Maps Shen.AI's MeasurementResults onto the vitals shape App.jsx's VitalsCard
// already renders, so a Shen.AI scan is a drop-in alternative to the in-house
// face_scan_biomarkers pipeline.
//
// Shen.AI's own wellness/accuracy caveats apply: these are wellness estimates, not
// medical measurements, so bp is flagged experimental exactly like the in-house
// pipeline flags its own research-grade BP.

const BP_DISCLAIMER = "Wellness estimate from Shen.AI — not a medical measurement";

/** Shen.AI MeasurementResults -> { heart_rate, bp, spo2, extras } */
export function toVitals(results) {
  if (!results) {
    return {
      heart_rate: { status: "unavailable", reason: "No measurement returned." },
      bp: { status: "unavailable" },
      spo2: { status: "unavailable" },
    };
  }

  const hr = results.heart_rate_bpm;
  const sbp = results.systolic_blood_pressure_mmhg;
  const dbp = results.diastolic_blood_pressure_mmhg;

  return {
    heart_rate:
      typeof hr === "number"
        ? { status: "ok", heart_rate_bpm: Math.round(hr) }
        : { reason: "Heart rate could not be read — please rescan." },

    bp:
      typeof sbp === "number" && typeof dbp === "number"
        ? {
            status: "ok",
            sbp: Math.round(sbp),
            dbp: Math.round(dbp),
            experimental: true,
            disclaimer: BP_DISCLAIMER,
          }
        : {
            status: "unavailable",
            // BP only comes back on the "all metrics" presets, and needs a good signal.
            reason: "Blood pressure needs a full-length scan with a steady signal.",
          },

    // Shen.AI does not report SpO2 at all (see MeasurementResults in @shenai/sdk).
    spo2: { status: "unavailable", reason: "Not measured by Shen.AI." },

    // Metrics the current VitalsCard doesn't show, kept so callers can use them
    // without re-reading the SDK.
    extras: {
      hrv_sdnn_ms: numOrNull(results.hrv_sdnn_ms),
      hrv_lnrmssd_ms: numOrNull(results.hrv_lnrmssd_ms),
      breathing_rate_bpm: numOrNull(results.breathing_rate_bpm),
      stress_index: numOrNull(results.stress_index),
      parasympathetic_activity: numOrNull(results.parasympathetic_activity),
      cardiac_workload_mmhg_per_sec: numOrNull(results.cardiac_workload_mmhg_per_sec),
      average_signal_quality: numOrNull(results.average_signal_quality),
    },
    source: "shenai",
  };
}

function numOrNull(v) {
  return typeof v === "number" ? v : null;
}

/** Human-readable guidance for the SDK's measurement/face states. */
export function statusText(sdk, measurementState, faceState) {
  if (!sdk) return "Starting…";

  const M = sdk.MeasurementState;
  const F = sdk.FaceState;

  if (measurementState === M.WAITING_FOR_FACE) {
    if (faceState === F.TOO_FAR) return "Move a little closer";
    if (faceState === F.TOO_CLOSE) return "Move a little back";
    if (faceState === F.NOT_CENTERED) return "Center your face in the frame";
    if (faceState === F.TURNED_AWAY) return "Look straight at the camera";
    return "Position your face in the frame";
  }
  if (measurementState === M.NOT_STARTED) return "Getting ready…";
  if (measurementState === M.RUNNING_SIGNAL_SHORT) return "Hold still — collecting signal";
  if (measurementState === M.RUNNING_SIGNAL_GOOD) return "Good signal — keep still";
  if (measurementState === M.RUNNING_SIGNAL_BAD) return "Weak signal — hold still, keep your face lit";
  if (measurementState === M.RUNNING_SIGNAL_BAD_DEVICE_UNSTABLE) return "Hold your device steady";
  if (measurementState === M.FINALIZING) return "Finalizing…";
  if (measurementState === M.FINISHED) return "Done";
  if (measurementState === M.FAILED) return "Scan failed — please try again";
  return "Scanning…";
}
