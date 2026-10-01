"""Raw traces -> feature vector. Column prefixes define feature groups for ablations:
   rppg_*  rPPG-only features         rbcg_*  rBCG-only features
   fused_* features needing both      q_*     quality/motion      demo_*  demographics"""
import numpy as np
from .signals import (bandpass, bcg_hr, upsample, rppg_multi_roi, rbcg_from_trajectories, spectral_peak, snr,
                      detect_beats, match_beats, fuse_ibis, hrv_time, HR_BAND)


def _ratio_of_ratios(a, b, fs):
    af, bf = bandpass(a, *HR_BAND, fs), bandpass(b, *HR_BAND, fs)
    return (af.std() / a.mean()) / (bf.std() / b.mean() + 1e-12)


def _beat_sync_R(a, b, fs, beats_s):
    """AC from per-beat peak-to-trough on band-passed channel, DC from raw mean. Median over beats."""
    af, bf = bandpass(a, *HR_BAND, fs), bandpass(b, *HR_BAND, fs)
    idx = (np.asarray(beats_s) * fs).astype(int)
    rs = []
    for i0, i1 in zip(idx[:-1], idx[1:]):
        if i1 - i0 < 5 or i1 > len(a):
            continue
        ac_a, ac_b = np.ptp(af[i0:i1]), np.ptp(bf[i0:i1])
        rs.append((ac_a / a[i0:i1].mean()) / (ac_b / b[i0:i1].mean() + 1e-12))
    return np.median(rs) if rs else np.nan


def _morphology(u, ufs, peaks_s, ups_s, hr_hz):
    """Beat-averaged rPPG template: rise time, 50% width, systolic/diastolic area ratio."""
    L = int(ufs / hr_hz)
    segs = []
    for t in ups_s:
        s = int(t * ufs) - int(0.1 * L)
        if s >= 0 and s + L <= len(u):
            seg = u[s:s + L]
            segs.append((seg - seg.min()) / (np.ptp(seg) + 1e-9))
    if len(segs) < 3:
        return dict(rise=np.nan, width50=np.nan, area_ratio=np.nan)
    tpl = np.median(segs, axis=0)
    pk = int(np.argmax(tpl))
    foot = int(np.argmin(tpl[:pk + 1])) if pk > 0 else 0
    above = np.where(tpl > 0.5)[0]
    return dict(rise=(pk - foot) / ufs * 1000, width50=(above[-1] - above[0]) / ufs * 1000 if len(above) else np.nan,
                area_ratio=tpl[foot:pk + 1].sum() / (tpl[pk:].sum() + 1e-9))


def _rbcg_ensemble(bcg, fs, anchors_s, amp_px, face_px, pre=0.3, post=0.7):
    """Average the rBCG signal over all heartbeats, each segment aligned to that beat's rPPG upstroke.
    Single beats are too weak in real video; the average of ~100-250 beats reveals the waveform.
    Returns sign-independent timing/amplitude features (ms relative to the rPPG upstroke) + split-half r."""
    out = dict(ens_r=np.nan, ens_z=np.nan, ens_p=np.nan, ens_t_peak=np.nan, ens_t_trough=np.nan,
               ens_amp_rel=np.nan, ens_n=0)
    a0, b0 = int(round(pre * fs)), int(round(post * fs))

    def cut(idx):
        s_ = np.array([bcg[i - a0:i + b0] for i in idx if i - a0 >= 0 and i + b0 <= len(bcg)])
        return s_ - s_.mean(axis=1, keepdims=True) if len(s_) else s_

    def split_r(s_):
        return float(np.corrcoef(s_[0::2].mean(0), s_[1::2].mean(0))[0, 1])

    def avg_snr(s_):
        """Signal-averaging SNR: power of the beat average vs the noise left in it (residual var / N)."""
        m_ = s_.mean(0)
        return float(np.var(m_) * len(s_) / (np.mean(np.var(s_ - m_, axis=1)) + 1e-12))

    segs = cut(np.round(np.asarray(anchors_s) * fs).astype(int))
    if len(segs) < 20:
        return out
    avg = segs.mean(axis=0)
    out["ens_n"] = len(segs)
    out["ens_r"] = split_r(segs)
    # chance level: split-half r of band-limited noise can be high, so compare with 30 random-timing controls
    rng = np.random.default_rng(0)
    real = avg_snr(segs)
    null = np.array([avg_snr(cut(np.sort(rng.integers(a0, len(bcg) - b0, len(segs))))) for _ in range(30)])
    out["ens_z"] = float(np.log10(real / np.median(null)))     # 0 = chance; 1 = 10x chance power
    out["ens_p"] = float((np.sum(null >= real) + 1) / (len(null) + 1))
    u, ufs = upsample(avg, fs)
    if abs(u.min()) > abs(u.max()):          # PCA sign is arbitrary: make the dominant deflection positive
        u = -u
    out["ens_t_peak"] = (np.argmax(u) / ufs - pre) * 1000
    out["ens_t_trough"] = (np.argmin(u) / ufs - pre) * 1000
    out["ens_amp_rel"] = float(np.ptp(u) * amp_px / (face_px + 1e-9))
    return out


def compute_features(raw, t0=0.0, t1=None):
    fs = raw["fs"]
    a, b = int(t0 * fs), int(t1 * fs) if t1 else len(raw["roi_rgb"])
    rgb, traj = raw["roi_rgb"][a:b], raw["traj_y"][a:b]
    f = {}
    if "track_quality" in raw:                                   # share of slots with a genuine KLT measurement
        f["q_track"] = float(np.mean(raw["track_quality"][a:b]))

    # --- rPPG ---
    ppg, f["q_snr_rppg"] = rppg_multi_roi(rgb, fs)
    hr_p = spectral_peak(ppg, fs)
    pk_p, up_p, u_p, ufs = detect_beats(ppg, fs, hr_p)
    f["rppg_hr"] = hr_p * 60
    for k, v in hrv_time(np.diff(up_p)).items():
        f[f"rppg_{k}"] = v
    for k, v in _morphology(u_p, ufs, pk_p, up_p, hr_p).items():
        f[f"rppg_{k}"] = v
    m = rgb.mean(axis=1)                               # (T,3) all-ROI mean for colour ratios
    f["rppg_R_rb"] = _ratio_of_ratios(m[:, 0], m[:, 2], fs)
    f["rppg_R_rg"] = _ratio_of_ratios(m[:, 0], m[:, 1], fs)

    # --- rBCG ---
    bcg, f["q_snr_rbcg"], f["q_motion"], amp_px = rbcg_from_trajectories(traj, fs)
    f["rbcg_amp_rel"] = amp_px / (raw["face_px"] + 1e-9)     # ~ stroke-force proxy, scale-free
    hr_b = bcg_hr(bcg, fs)
    pk_b, _, _, _ = detect_beats(bcg, fs, hr_b)
    f["rbcg_hr"] = hr_b * 60
    for k, v in hrv_time(np.diff(pk_b)).items():
        f[f"rbcg_{k}"] = v

    # --- fused (needs both) ---
    ibi_ref = 1 / hr_p
    pairs = match_beats(up_p, pk_b, max_lag=0.45 * ibi_ref)
    delays = np.array([up_p[i] - pk_b[j] for i, j in pairs])   # signed rPPG-upstroke minus rBCG J-peak
    f["q_match_ratio"] = len(pairs) / max(len(up_p), 1)
    f["fused_delay_med"] = np.median(delays) * 1000 if len(delays) > 2 else np.nan
    f["fused_delay_iqr"] = np.subtract(*np.percentile(delays, [75, 25])) * 1000 if len(delays) > 2 else np.nan
    fused_ibi, f["q_agreement"] = fuse_ibis(up_p, pk_b, pairs)
    for k, v in hrv_time(fused_ibi).items():
        f[f"fused_{k}"] = v
    f["fused_hr_diff"] = abs(f["rppg_hr"] - f["rbcg_hr"])
    # beat-synchronous SpO2 ratio using agreed beats only, gated by motion
    good_beats = [up_p[i] for i, _ in pairs]
    f["fused_R_rb_sync"] = _beat_sync_R(m[:, 0], m[:, 2], fs, good_beats)
    f["fused_R_rg_sync"] = _beat_sync_R(m[:, 0], m[:, 1], fs, good_beats)
    # beat-averaged rBCG anchored on rPPG beats: the dual-source timing feature that works on real video
    ens = _rbcg_ensemble(bcg, fs, up_p, amp_px, raw["face_px"])
    f["q_rbcg_ens_r"] = ens["ens_r"]
    f["q_rbcg_ens_z"] = ens["ens_z"]   # log10(beat-average power / chance level); >0.5 = real beat-locked rBCG
    f["q_rbcg_ens_n"] = ens["ens_n"]
    f["fused_ens_t_peak"] = ens["ens_t_peak"]
    f["fused_ens_t_trough"] = ens["ens_t_trough"]
    f["fused_ens_amp_rel"] = ens["ens_amp_rel"]
    return f
