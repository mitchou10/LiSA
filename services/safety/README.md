# LiSA Safety Service

Detects **prompt injection**, **toxicity**, and **secrets/API keys** in prompts
using [llm-guard](https://github.com/protectai/llm-guard)'s input scanners.

## Scanners

| Scanner | Classification | Description |
|---------|---------------|-------------|
| `PromptInjection` | `prompt_injection` | Detects prompt injection / jailbreak attempts |
| `Toxicity` | `toxicity` | Detects toxic, insulting, or hateful content |
| `Secrets` | `secret_leak` | Detects API keys, tokens, and other secrets |

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `CELERY_QUEUE` | `llm-guard-safety` | Celery queue to consume from |
| `ENABLED_SCANNERS` | `prompt_injection,toxicity,secrets` | Comma-separated list of scanners to enable |

## Running

```bash
docker compose up -d --build safety
```
