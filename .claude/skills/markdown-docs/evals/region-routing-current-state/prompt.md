---
tags: [markdown-docs]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

write a note in documents/notes on how the edge decides which region, bucket and agent runtime a request uses today — start from backend/app/regions.py and backend/app/config.py and follow it into the routes. I want to know what every route shares, where the fallbacks are, and what happens when a header is missing, with file:line refs
