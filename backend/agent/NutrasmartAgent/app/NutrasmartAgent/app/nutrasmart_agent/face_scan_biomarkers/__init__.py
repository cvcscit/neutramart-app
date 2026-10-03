"""Face-scan biomarker feature: heart rate, blood pressure and SpO2 estimated from a face
video. Self-contained -- owns its own settings, S3 client and model cache, independent of
the rest of the agent (food_scan, chat, summary).

IMPORTANT STATUS NOTE: only the heart-rate gate has been validated against a held-out test
set with meaningful accuracy (see BP_measurement/README.md, "Results"). The BP and SpO2
models trained by this pipeline so far are either unvalidated (SpO2 -- never run against
real ground truth) or shown in the source repo's own benchmarks to not beat a naive
age/sex baseline (BP, on the MCD-rPPG dataset). They are wired up and returned because the
product decision was to surface all three, but every bp/spo2 response carries an explicit
"experimental" flag that callers must not hide from the user.
"""
