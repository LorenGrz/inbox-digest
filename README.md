# inbox-digest

Digest diario de Gmail + Calendar y clasificación del inbox, en Python, corriendo
como cron en GitHub Actions. Reemplaza a
[DailyReminderBot](https://github.com/LorenGrz/DailyReminderBot) (Apps Script).

> En construcción: ver `docs/superpowers/plans/2026-10-30-inbox-digest-port.md`.

## Stack

Python 3.13 · uv · APIs oficiales de Google (Gmail, Calendar, Sheets) · Gemini
(`google-genai`) · GitHub Actions como cron · ruff, mypy --strict, pytest.

## Comandos

| Comando | Para qué |
|---|---|
| `uv sync` | Instalar dependencias |
| `bash scripts/check.sh` | Formato, lint, tipos, tests y chequeo de secretos (lo mismo que CI) |
| `uv run ruff format .` | Formatear |
| `uv run pytest` | Tests |

## Decisiones

Ver `docs/decisions/`.
