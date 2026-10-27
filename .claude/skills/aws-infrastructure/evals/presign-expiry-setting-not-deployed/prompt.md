---
tags: [aws-infrastructure]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

make the presigned-upload expiry configurable per deployment instead of the literal in config.py — keep the current value as the local default, wire it into the ECS task so prod can set it, and document it. don't deploy anything
