# Architecture - inbox-digest

## Overview

Dos comandos de CLI (`inbox-digest digest` y `inbox-digest classify`) que GitHub Actions corre
por cron. Leen Gmail y Calendar con las APIs oficiales, clasifican con reglas + Naive Bayes,
opcionalmente resumen con Gemini, y guardan estado en un Google Sheet editable a mano.

## Modules / boundaries

| Módulo | Responsabilidad | No hace |
|---|---|---|
| `rules.py`, `context.py`, `learn.py` | Clasificar mails y eventos, Naive Bayes | Red |
| `render.py` (+ `templates/`) | HTML del digest, resumen por reglas | Red |
| `gemini.py` | Prompt, payload, parseo/validación de la salida, retry | Leer Gmail |
| `gmail.py`, `calendar.py`, `state.py` | Adaptadores a Gmail, Calendar y el Sheet | Decidir |
| `google_api.py` | Credenciales y clientes | — |
| `main.py` | CLI y orquestación | Lógica de negocio |

## Data model

Sheet con tres pestañas (las mismas que DailyReminderBot): `reminders` (recordatorios
enviados), `applications` (postulaciones), `feedback` (ejemplos de entrenamiento). Tipos en
`src/inbox_digest/types.py`.

## Key flows

- **digest:** cerrar tarjetas de ayer sin feedback (cuentan como importantes) → eventos de
  hoy + 14 días → mails importantes de 24 h → Gemini (o `rule_summary`) → render → enviar → registrar.
- **classify:** procesar etiqueta `No importante` (ejemplo `later` → "Revisar después") →
  clasificar no leídos de 2 días → mover lo no importante.

## External services

Gmail API, Calendar API, Sheets API (OAuth de usuario) y Gemini API (key).

## Env vars

Ver `.env.example`. En Actions, los mismos nombres como GitHub Secrets.

## Deploy

GitHub Actions en este repo: `digest.yml` (`30 12 * * *` UTC = 09:30 ART), `classify.yml` (cada 30 min), `keepalive.yml` (mensual). No hay deploy: cada corrida hace checkout de `main`. Credenciales: ver `docs/decisions/0002-python-github-actions.md`.
