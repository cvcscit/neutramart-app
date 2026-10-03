"""Signal processing: filtering, rPPG (POS), rBCG (PCA on head motion), beats, fusion, HRV."""
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, welch, hilbert
from scipy.interpolate import CubicSpline

HR_BAND = (0.7, 3.0)      # 42-180 bpm
UP_FS = 250.0             # upsample rate for sub-frame beat timing


def bandpass(x, lo, hi, fs, order=3):
    b, a = butter(order, [lo / (fs / 2), hi / (fs / 2)], btype="band")
    return filtfilt(b, a, x, axis=0)


def upsample(x, fs, new_fs=UP_FS):
    t = np.arange(len(x)) / fs
    tn = np.arange(0, t[-1], 1 / new_fs)
    return CubicSpline(t, x)(tn), new_fs


def spectral_peak(x, fs, band=HR_BAND, harmonics=1):
    """Dominant frequency. harmonics>1 uses harmonic summation, so a waveform with a strong
    2nd harmonic (typical of BCG's I-J-K complex) is not mistaken for double the heart rate."""
    f, p = welch(x, fs=fs, nperseg=min(len(x), int(fs * 10)), nfft=4096)
    m = (f >= band[0]) & (f <= band[1])
    score = sum(np.interp(f[m] * h, f, p) / h ** 0.5 for h in range(1, harmonics + 1))
    return f[m][np.argmax(score)]


def snr(x, fs, band=HR_BAND, harmonics=1):
    """Power within +/-0.1 Hz of HR peak and first harmonic, over the rest of the band (dB)."""
    f, p = welch(x, fs=fs, nperseg=min(len(x), int(fs * 10)))
    f0 = spectral_peak(x, fs, band, harmonics)
    sig = (np.abs(f - f0) < 0.1) | (np.abs(f - 2 * f0) < 0.1)
    m = (f >= band[0]) & (f <= 2 * band[1])
    return 10 * np.log10(p[sig & m].sum() / max(p[~sig & m].sum(), 1e-12))


# ---------------- rPPG ----------------
def pos(rgb, fs, win_sec=1.6):
    """Plane-Orthogonal-to-Skin (Wang et al. 2017), vectorised overlap-add. rgb: (T,3) spatial means."""
    rgb = np.asarray(rgb, float)
    n, l = len(rgb), int(win_sec * fs)
    if n < l:
        return np.zeros(n)
    W = np.lib.stride_tricks.sliding_window_view(rgb, l, axis=0)          # (n-l+1, 3, l)
    cn = W / (W.mean(axis=2, keepdims=True) + 1e-9)
    S = np.einsum("ij,wjl->wil", np.array([[0, 1, -1], [-2, 1, 1]], float), cn)
    h = S[:, 0] + (S[:, 0].std(1) / (S[:, 1].std(1) + 1e-9))[:, None] * S[:, 1]
    h -= h.mean(1, keepdims=True)
    H = np.zeros(n)
    for k in range(l):
        H[k:k + len(h)] += h[:, k]
    return H


def rppg_multi_roi(roi_rgb, fs):
    """roi_rgb: (T,R,3). POS per ROI, SNR-weighted ensemble. Returns signal, snr_db."""
    sigs, w = [], []
    for r in range(roi_rgb.shape[1]):
        s = bandpass(pos(roi_rgb[:, r], fs), *HR_BAND, fs)
        s = (s - s.mean()) / (s.std() + 1e-9)
        sigs.append(s)
        w.append(max(snr(s, fs), -10) + 10)   # shift so weights are >= 0
    w = np.array(w) + 1e-6
    out = np.sum(np.array(sigs) * w[:, None], axis=0) / w.sum()
    return out, snr(out, fs)


# ---------------- rBCG ----------------
def bcg_envelope(x, fs):
    """Energy envelope of the I-J-K complex: one hump per heartbeat, so its fundamental is the HR
    even when the raw BCG spectrum is dominated by harmonics."""
    return bandpass(np.abs(hilbert(x)), *HR_BAND, fs)


def bcg_hr(x, fs):
    return spectral_peak(bcg_envelope(x, fs), fs, harmonics=2)

def rbcg_from_trajectories(traj_y, fs):
    """traj_y: (T,K) vertical positions of tracked rigid facial points (pixels).
    Band-pass each, PCA, pick the component with best cardiac SNR. Returns signal, snr_db, motion."""
    x = traj_y - traj_y.mean(axis=0)
    motion = np.sqrt(np.mean(bandpass(x, 0.05, 0.6, fs) ** 2))       # non-cardiac (breathing/posture) motion
    xf = bandpass(x, 0.75, 5.0, fs)
    keep = np.percentile(np.abs(xf).max(axis=0), 75) >= np.abs(xf).max(axis=0)  # drop the 25% jumpiest points
    xf = xf[:, keep]
    u, s, vt = np.linalg.svd(xf - xf.mean(0), full_matrices=False)
    comps = u[:, :5] * s[:5]
    snrs = [snr(bcg_envelope(bandpass(c, 0.75, 5.0, fs), fs), fs, harmonics=2) for c in comps.T]
    best = comps[:, int(np.argmax(snrs))]
    sig = bandpass(best, 0.75, 8.0, fs)  # keep J-peak sharpness for timing
    # PCA sign is arbitrary: orient so the dominant (J) deflections are positive peaks
    if np.mean((sig - sig.mean()) ** 3) < 0:
        sig = -sig
    amp_px = sig.std()
    return sig / (amp_px + 1e-9), max(snrs), motion, amp_px


# ---------------- beats ----------------
def detect_beats(sig, fs, hr_hz):
    """Peaks on an upsampled signal. Returns (peak_times_s, upstroke_times_s, upsampled_sig, up_fs)."""
    u, ufs = upsample(sig, fs)
    pk, _ = find_peaks(u, distance=int(0.6 * ufs / hr_hz), prominence=0.3 * np.std(u))
    d1 = np.gradient(u)
    ups = []
    for p in pk:
        a = max(0, p - int(0.35 * ufs / hr_hz))
        ups.append(a + int(np.argmax(d1[a:p + 1])) if p > a else p)   # max-slope point before peak
    return pk / ufs, np.array(ups) / ufs, u, ufs


def match_beats(t_ref, t_other, max_lag):
    """For each reference beat, nearest other-source beat within +/-max_lag. Returns index pairs."""
    pairs = []
    for i, t in enumerate(t_ref):
        if len(t_other) == 0:
            break
        j = int(np.argmin(np.abs(t_other - t)))
        if abs(t_other[j] - t) <= max_lag:
            pairs.append((i, j))
    return pairs


def fuse_ibis(t_ppg, t_bcg, pairs, tol=0.06):
    """IBIs from consecutive matched beats; keep where both sources agree within tol (s)."""
    ibi_p, ibi_b, fused = [], [], []
    for (i0, j0), (i1, j1) in zip(pairs[:-1], pairs[1:]):
        if i1 != i0 + 1 or j1 != j0 + 1:
            continue
        a, b = t_ppg[i1] - t_ppg[i0], t_bcg[j1] - t_bcg[j0]
        ibi_p.append(a); ibi_b.append(b)
        if abs(a - b) < tol:
            fused.append((a + b) / 2)
    n = max(len(ibi_p), 1)
    return np.array(fused), len(fused) / n


def clean_ibis(ibi):
    ibi = np.asarray(ibi)
    ibi = ibi[(ibi > 0.33) & (ibi < 1.5)]
    if len(ibi) < 3:
        return ibi
    med = np.median(ibi)
    return ibi[np.abs(ibi - med) < 0.25 * med]


def hrv_time(ibi):
    ibi = clean_ibis(ibi)
    if len(ibi) < 5:
        return dict(mean_ibi=np.nan, sdnn=np.nan, rmssd=np.nan, pnn50=np.nan, n_beats=len(ibi))
    d = np.diff(ibi)
    return dict(mean_ibi=ibi.mean() * 1000, sdnn=ibi.std(ddof=1) * 1000,
                rmssd=np.sqrt(np.mean(d ** 2)) * 1000, pnn50=np.mean(np.abs(d) > 0.05) * 100,
                n_beats=len(ibi))
