"""Heart rate from face video, with a trained reliability gate.

The HR itself needs no training: POS rPPG on three skin regions (forehead, both cheeks), SNR-weighted, spectral
peak. What is trained is the GATE: a small classifier that predicts, from signal-quality features, whether a
30 s window's HR is within 5 bpm of the truth. At scan time the scan is cut into overlapping 30 s windows, only
windows the gate accepts are kept, and the reported HR is their median. If none pass, HR is withheld and the app
asks for a rescan. This is what turns "usually right" into "right when shown".
"""
import numpy as np
from scipy.signal import welch
from .signals import bandpass, pos, spectral_peak, snr, rbcg_from_trajectories, HR_BAND

WIN_SEC, HOP_SEC = 30.0, 10.0
FEATURES = ["hr_bpm", "snr_db", "roi_hr_spread", "roi_agree", "peak_ratio", "half_diff_bpm",
            "motion", "track", "brightness", "brightness_cv"]


def _peak_ratio(x, fs):
    """Height of the main spectral peak over the highest peak elsewhere in the HR band (>1 = unambiguous)."""
    f, p = welch(x, fs=fs, nperseg=min(len(x), int(fs * 10)), nfft=4096)
    m = (f >= HR_BAND[0]) & (f <= HR_BAND[1])
    f, p = f[m], p[m]
    i = int(np.argmax(p))
    far = np.abs(f - f[i]) > 0.15
    return float(p[i] / (p[far].max() + 1e-12)) if far.any() else np.nan


def window_features(raw, t0, t1):
    """Quality features + HR for one window of cached traces (raw = dsv.extract.extract_video output)."""
    fs = float(raw["fs"])
    a, b = int(t0 * fs), int(t1 * fs)
    rgb = raw["roi_rgb"][a:b]
    if len(rgb) < 10 * fs:
        return None
    sigs, w, roi_hr = [], [], []
    for r in range(rgb.shape[1]):
        s = bandpass(pos(rgb[:, r], fs), *HR_BAND, fs)
        s = (s - s.mean()) / (s.std() + 1e-9)
        sigs.append(s)
        w.append(max(snr(s, fs), -10) + 10)
        roi_hr.append(spectral_peak(s, fs) * 60)
    w = np.array(w) + 1e-6
    ens = np.sum(np.array(sigs) * w[:, None], axis=0) / w.sum()
    hr = spectral_peak(ens, fs) * 60
    h = len(ens) // 2
    half = abs(spectral_peak(ens[:h], fs) - spectral_peak(ens[h:], fs)) * 60
    g = rgb.mean(axis=1)[:, 1]
    f = dict(hr_bpm=hr, snr_db=snr(ens, fs), roi_hr_spread=float(np.std(roi_hr)),
             roi_agree=float(np.sum(np.abs(np.array(roi_hr) - hr) <= 5)), peak_ratio=_peak_ratio(ens, fs),
             half_diff_bpm=half, brightness=float(g.mean()), brightness_cv=float(g.std() / (g.mean() + 1e-9)))
    traj = raw.get("traj_y")
    if traj is not None and np.ndim(traj) == 2 and traj.shape[1] >= 5 and len(traj) >= b:
        f["motion"] = float(rbcg_from_trajectories(traj[a:b], fs)[2])
    else:
        f["motion"] = np.nan
    tq = raw.get("track_quality")
    f["track"] = float(np.mean(tq[a:b])) if tq is not None and len(tq) >= b else np.nan
    return f


def windows(duration_s, win=WIN_SEC, hop=HOP_SEC):
    if duration_s < win:
        return [(0.0, duration_s)] if duration_s >= 15 else []
    return [(t, t + win) for t in np.arange(0, duration_s - win + 1e-6, hop)]


class HRGate:
    """Trained reliability gate. Saved/loaded with joblib as a plain dict for portability."""

    def __init__(self, model=None, threshold=0.5, features=FEATURES, info=None):
        self.model, self.threshold, self.features, self.info = model, threshold, list(features), info or {}

    def proba(self, feats):
        import pandas as pd
        X = pd.DataFrame([{k: d.get(k, np.nan) for k in self.features} for d in feats])
        return self.model.predict_proba(X)[:, 1]

    def save(self, path):
        import joblib
        joblib.dump(dict(model=self.model, threshold=self.threshold, features=self.features, info=self.info), path)

    @classmethod
    def load(cls, path):
        import joblib
        d = joblib.load(path)
        return cls(d["model"], d["threshold"], d["features"], d.get("info"))


def measure_hr(raw, gate=None, min_snr_db=-3.0):
    """Scan -> heart rate. With a trained gate, only windows it trusts are used; without one, a plain SNR
    threshold is used. Returns dict(heart_rate_bpm or None, status, windows_used, windows_total, reliability)."""
    dur = len(raw["roi_rgb"]) / float(raw["fs"])
    feats = [f for f in (window_features(raw, t0, t1) for t0, t1 in windows(dur)) if f is not None]
    if not feats:
        return dict(heart_rate_bpm=None, status="withheld", reason="scan too short (need at least 15-30 s)",
                    windows_used=0, windows_total=0)
    if gate is not None:
        p = gate.proba(feats)
        ok = p >= gate.threshold
        rel = float(np.max(p))
    else:
        p = None
        ok = np.array([f["snr_db"] >= min_snr_db for f in feats])
        rel = None
    out = dict(windows_used=int(ok.sum()), windows_total=len(feats), gate="trained" if gate else "snr")
    if not ok.any():
        out.update(heart_rate_bpm=None, status="withheld",
                   reason="signal not reliable enough (movement, lighting or face too small) - please rescan",
                   reliability=rel)
        return out
    hrs = np.array([f["hr_bpm"] for f in feats])[ok]
    out.update(heart_rate_bpm=round(float(np.median(hrs)), 1), status="ok",
               reliability=round(float(np.mean(p[ok])), 3) if p is not None else None,
               spread_bpm=round(float(np.ptp(hrs)), 1) if len(hrs) > 1 else 0.0)
    return out
