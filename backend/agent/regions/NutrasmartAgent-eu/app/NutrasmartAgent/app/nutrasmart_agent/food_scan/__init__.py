"""Food-scan feature: local EfficientNet classifier + vision-LLM fallback for food
image analysis. Self-contained -- owns its own settings, AWS clients and classifier,
independent of the rest of the agent (biomarker face-scan, chat, summary)."""
