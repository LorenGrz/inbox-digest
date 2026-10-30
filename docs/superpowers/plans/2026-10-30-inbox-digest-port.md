# Nuevo proyecto: inbox-digest (Python) — port de DailyReminderBot

## Context
DailyReminderBot (Apps Script + TS, ~1.9k líneas de src) funciona, pero Loren no quiere
seguir con Apps Script y prefiere Python para automatizaciones. Se arranca un repo nuevo
que replica el comportamiento actual con el stack estándar: Python + APIs oficiales de
Google + cron en GitHub Actions. El botón "No es importante" (web app + HMAC) se reemplaza
por una etiqueta de Gmail, así no hace falta ningún servidor. El bot viejo sigue corriendo
hasta que el nuevo esté validado.

## Decisiones (ADR 0001 en el repo nuevo)
- **Repo:** `~/projects/inbox-digest`, público en `LorenGrz/inbox-digest`, scaffold con la skill `project-init`.
- **Stack:** Python 3.13 (`uv`), `google-api-python-client` + `google-auth-oauthlib`,
  `google-genai`, `gspread`, `jinja2` (HTML del mail), `pydantic` (salida de Gemini).
  Dev: `ruff` (lint+format), `mypy --strict`, `pytest`.
- **Cron:** GitHub Actions. `digest.yml` → `30 12 * * *` (09:30 ART); `classify.yml` → `*/30 * * * *`.
  `concurrency: inbox-digest` para que no se pisen escribiendo el Sheet.
- **Auth:** OAuth de usuario; app en Google Cloud pasada a "In production" (sin verificar,
  1 usuario) para que el refresh token no venza a los 7 días. Scopes: `gmail.modify`,
  `calendar.readonly`, `spreadsheets`. `scripts/get_token.py` lo genera una vez en local.
- **Secretos:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`,
  `GEMINI_API_KEY`, `STATE_SHEET_ID` en GitHub Secrets; local en `.env` (gitignoreado).
  `scripts/check_secrets.sh` portado al CI.
- **Estado:** el **mismo Sheet** de hoy (pestañas `reminders`, `applications`, `feedback`),
  así no se pierde el entrenamiento.
- **Feedback:** etiqueta Gmail `No importante`. Cada corrida de `classify` la busca, guarda
  el ejemplo (`label=later`, peso 1) en `feedback`, saca la etiqueta y lo manda a
  "Revisar después". Las tarjetas sin etiquetar a las 20 h siguen contando como importantes
  (peso `IMPLICIT_WEIGHT`). Cada tarjeta del digest linkea al hilo.
- **Logs públicos:** el repo es público, así que los logs de Actions también. Solo se
  loguean conteos, nunca asuntos, remitentes ni contenido. Un test lo chequea.
- **Riesgo conocido:** GitHub desactiva los cron de repos públicos después de 60 días sin
  actividad. Se agrega un workflow mensual de keepalive (con `gh api` reactiva el workflow)
  y una nota en AGENTS.md.

## Estructura
```
src/inbox_digest/
  config.py      # env vars, TIMEZONE, LOOKAHEAD_DAYS, labels, modelo Gemini
  models.py       # dataclasses: MailFacts, Classified, EventFacts, DigestModel...
  rules.py       # port 1:1 de src/rules.ts (el ORDEN de RULES es semántico)
  context.py     # port de src/context.ts
  learn.py       # port de src/learn.ts (Naive Bayes, umbrales 0.15/0.85, ≥5 por clase)
  render.py      # port de src/render.ts + templates/digest.html.j2; incluye rule_summary
  gemini.py      # port de src/gemini.ts: prompt, schema, retry/backoff, thinking config,
                 #   payload con horario LOCAL ya formateado (fix del 30/10)
  google_api.py  # credenciales + clientes Gmail/Calendar/Sheets
  gmail.py calendar.py state.py   # adaptadores (los únicos que tocan la red)
  main.py        # CLI: `digest`, `classify`, `test-digest` (no manda nada), `diagnose-gemini`
tests/           # port de tests/*.test.ts a pytest
```
Misma regla que hoy: `rules`, `context`, `learn`, `render`, `gemini.build_payload` no
importan nada de red y se testean puros. Fechas con `zoneinfo("America/Argentina/Buenos_Aires")`.
A Gemini solo le llegan remitente, asunto y ≤200 caracteres; prompt verbatim en `docs/prompts.md`.

## Fases (un PR cada una, vía el flujo que deje `project-init`)
1. **Scaffold:** `project-init` → AGENTS.md, CI (ruff, mypy, pytest, check_secrets), `.gitignore`, README, ADR 0001, `docs/prompts.md`, spec y este plan en `docs/superpowers/`.
2. **Lógica pura + tests:** types, rules, context, learn, render, gemini (sin red). Port con
   los mismos casos de los tests TS. Esto lo hace un `worker` en bulk; el criterio de
   aceptación es `uv run pytest && uv run mypy && uv run ruff check`.
3. **Adaptadores + CLI:** google_api, gmail, calendar, state, main; `scripts/get_token.py`.
4. **Workflows:** digest, classify, keepalive. Arrancan con `DRY_RUN=true`.
5. **Cutover:** comparar 2–3 días el digest dry-run con el de Apps Script, después
   `DRY_RUN=false`, correr `removeTriggers` en el bot viejo y archivar DailyReminderBot
   (README apuntando al nuevo).

## Pasos manuales de Loren (no los puedo hacer yo)
- Crear el proyecto en Google Cloud, habilitar las APIs de Gmail, Calendar y Sheets, armar la
  pantalla de consentimiento (External → In production) y un OAuth client "Desktop".
- Correr `uv run scripts/get_token.py` una vez y cargar los 5 secretos en GitHub.

## Verificación
- Local: `uv run pytest`, `uv run mypy src`, `uv run ruff check`.
- Contra la cuenta real sin efectos: `uv run inbox-digest test-digest` con `.env`.
- Actions: `gh workflow run digest.yml` con DRY_RUN y revisar que el log solo traiga conteos.
- Cutover: el digest nuevo coincide con el viejo (eventos con hora local, mismos importantes).
