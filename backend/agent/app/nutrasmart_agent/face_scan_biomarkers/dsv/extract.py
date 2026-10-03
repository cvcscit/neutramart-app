"""Video -> raw per-frame traces (the slow step). Saves an .npz per video:
   roi_rgb (T,R,3) : mean RGB of forehead / left cheek / right cheek  -> rPPG + SpO2
   traj_y  (T,K)   : vertical sub-pixel trajectories of KLT-tracked points on forehead+nose -> rBCG
   face_px         : inter-ocular distance (pixels) to normalise rBCG amplitude
   fs              : frame rate
RigidTracker below can be replaced by another head-motion tracker as long as it returns the same traces."""
import glob, os, re
import cv2
import numpy as np
import mediapipe as mp

IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp")


def _natural_key(p):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", os.path.basename(p))]


def iter_frames(path, fps=None):
    """Yields BGR frames from a video file OR a folder of images (PURE, BP4D+ ship frames as images).
    Returns (generator, fs)."""
    if os.path.isdir(path):
        files = sorted([f for f in glob.glob(os.path.join(path, "*")) if f.lower().endswith(IMG_EXT)], key=_natural_key)
        if not files:
            raise FileNotFoundError(f"no image frames in {path}")
        return (cv2.imread(f) for f in files), float(fps or 30.0)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(path)
    fs = float(fps or cap.get(cv2.CAP_PROP_FPS) or 30.0)

    def gen():
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            yield fr
        cap.release()
    return gen(), fs

ROIS = {
    "forehead": [10, 67, 109, 338, 297, 151, 108, 337, 69, 299],
    "cheek_l": [50, 101, 118, 117, 123, 187, 205, 36],
    "cheek_r": [280, 330, 347, 346, 352, 411, 425, 266],
}
RIGID = [10, 151, 9, 8, 168, 6, 197, 195, 5, 4, 67, 297, 109, 338]  # forehead + nose bridge (no jaw)
EYES = (33, 263)


def _poly_mean(frame, pts):
    mask = np.zeros(frame.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, cv2.convexHull(pts.astype(np.int32)), 1)
    return cv2.mean(frame, mask=mask)[:3]          # BGR


class RigidTracker:
    """KLT tracking of rigid facial points (forehead + nose) for rBCG, robust to long videos.

    Each of K "slots" keeps a continuous vertical trajectory built from frame-to-frame displacements.
    A point that fails the forward-backward check or leaves the rigid region is replaced by a fresh
    feature; for that frame its displacement is taken as the median of the good points, so no slot is
    ever dropped. This keeps all K trajectories alive over 3-minute recordings with occasional
    decoder glitches."""

    def __init__(self, k=60, fb_max=0.5, reseed_below=0.8):
        self.k, self.fb_max, self.reseed_below = k, fb_max, reseed_below
        self.prev, self.pts, self.alive = None, None, None
        self.lk = dict(winSize=(21, 21), maxLevel=3,
                       criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

    def _mask(self, gray, lm):
        m = np.zeros_like(gray)
        cv2.fillConvexPoly(m, cv2.convexHull(lm[RIGID].astype(np.int32)), 255)
        return m

    def _new_points(self, gray, lm, n, avoid=None):
        m = self._mask(gray, lm)
        if avoid is not None:
            for x, y in avoid.reshape(-1, 2):
                cv2.circle(m, (int(x), int(y)), 5, 0, -1)
        p = cv2.goodFeaturesToTrack(gray, n, 0.01, 5, mask=m)
        return None if p is None else p.reshape(-1, 2).astype(np.float32)

    def update(self, gray, lm):
        """Returns (dy per slot [k], fraction of slots with a genuine measurement this frame)."""
        if self.pts is None:
            p = self._new_points(gray, lm, self.k)
            if p is None or len(p) < 3:
                p = lm[RIGID].astype(np.float32)
            self.pts = np.zeros((self.k, 2), np.float32)
            self.pts[:] = p[np.arange(self.k) % len(p)]          # fill all slots
            self.alive = np.zeros(self.k, bool); self.alive[:min(len(p), self.k)] = True
            self.prev = gray
            return np.zeros(self.k), float(self.alive.mean())
        p0 = self.pts.reshape(-1, 1, 2)
        p1, st1, _ = cv2.calcOpticalFlowPyrLK(self.prev, gray, p0, None, **self.lk)
        pb, st2, _ = cv2.calcOpticalFlowPyrLK(gray, self.prev, p1, None, **self.lk)
        fb = np.linalg.norm((pb - p0).reshape(-1, 2), axis=1)
        p1 = p1.reshape(-1, 2)
        hull = cv2.convexHull(lm[RIGID].astype(np.float32))
        inside = np.array([cv2.pointPolygonTest(hull, (float(x), float(y)), False) >= 0 for x, y in p1])
        ok = self.alive & st1.ravel().astype(bool) & st2.ravel().astype(bool) & (fb < self.fb_max) & inside
        dy = p1[:, 1] - self.pts[:, 1]
        fill = float(np.median(dy[ok])) if ok.any() else 0.0
        dy = np.where(ok, dy, fill)
        self.pts = p1
        self.alive = ok
        if ok.mean() < self.reseed_below:                        # replace lost points with fresh features
            dead = np.where(~ok)[0]
            newp = self._new_points(gray, lm, len(dead), avoid=self.pts[ok] if ok.any() else None)
            if newp is not None:
                for slot, q in zip(dead, newp):
                    self.pts[slot] = q; self.alive[slot] = True
        self.prev = gray
        return dy, float(ok.mean())


def resample_uniform(raw, t, fs_out=None):
    """Resample traces recorded at irregular times t (s) onto a uniform grid (fixes dropped frames and
    wrong frame-rate headers). fs_out defaults to the median frame rate implied by t."""
    t = np.asarray(t, float); t = t - t[0]
    ok = np.concatenate([[True], np.diff(t) > 0])               # drop duplicate / backwards stamps
    t = t[ok]
    fs = fs_out or round(1.0 / np.median(np.diff(t)), 3)
    g = np.arange(0, t[-1], 1.0 / fs)
    out = dict(raw)
    rgb = raw["roi_rgb"][ok]
    out["roi_rgb"] = np.stack([np.stack([np.interp(g, t, rgb[:, r, c]) for c in range(rgb.shape[2])], -1)
                               for r in range(rgb.shape[1])], 1)
    tr = raw["traj_y"][ok]
    out["traj_y"] = np.stack([np.interp(g, t, tr[:, k]) for k in range(tr.shape[1])], 1)
    if "track_quality" in raw:
        out["track_quality"] = np.interp(g, t, raw["track_quality"][ok])
    out["fs"] = float(fs)
    return out


def extract_video(path, max_sec=None, klt_points=60, fps=None, timestamps=None):
    """timestamps: optional per-frame times (s) for every frame in the file; when given, the traces are
    resampled onto a uniform grid at the true frame rate instead of trusting the file header."""
    frames, fs = iter_frames(path, fps)
    fm = mp.solutions.face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=False,
                                         min_detection_confidence=0.5, min_tracking_confidence=0.5)
    tracker = RigidTracker(k=klt_points)
    roi_rgb, face_px, fidx, dys, tq = [], [], [], [], []
    last_lm = None
    n = 0
    for frame in frames:
        if frame is None or (max_sec and n >= max_sec * fs):
            break
        h, w = frame.shape[:2]
        res = fm.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if res.multi_face_landmarks:
            last_lm = np.array([[p.x * w, p.y * h] for p in res.multi_face_landmarks[0].landmark])
        elif last_lm is None:
            n += 1
            continue
        lm = last_lm
        roi_rgb.append([_poly_mean(frame, lm[idx])[::-1] for idx in ROIS.values()])  # -> RGB
        face_px.append(np.linalg.norm(lm[EYES[0]] - lm[EYES[1]]))
        dy, q = tracker.update(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), lm)
        dys.append(dy); tq.append(q); fidx.append(n)
        n += 1
    if not roi_rgb:
        return dict(roi_rgb=np.zeros((0,)), traj_y=np.zeros((0, 0)), face_px=np.nan, fs=float(fs))
    raw = dict(roi_rgb=np.array(roi_rgb, float), traj_y=np.cumsum(np.array(dys), axis=0),
               face_px=float(np.median(face_px)), fs=float(fs), track_quality=np.array(tq),
               n_frames_file=n)
    if timestamps is not None and len(timestamps) >= max(fidx) + 1:
        raw = resample_uniform(raw, np.asarray(timestamps, float)[fidx])
        raw["fs_header"] = float(fs)
    return raw
