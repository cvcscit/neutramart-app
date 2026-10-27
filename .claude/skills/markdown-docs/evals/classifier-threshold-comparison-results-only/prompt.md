---
tags: [markdown-docs]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

I ran the three cuisine classifiers over the 400-image eval set at thresholds 0.60, 0.70 and 0.80, results in the csv. write it up as a comparison report in documents/notes. my take: keep 0.70 for chinese and thai, indian can drop to 0.60, and the thai fallback rate at 0.80 means we need more thai training data before raising anything

Input files: results.csv
