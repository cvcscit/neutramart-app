---
tags: [markdown-docs]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

update documents/MIGRATION_OUTSTANDING_TASKS.md: AWS support cleared the CloudFront block on the new account today (case 123456789), the distribution now reaches the ALB and /health answers through it. the domain alias is still on the old distribution, nothing else changed. don't touch the other items
