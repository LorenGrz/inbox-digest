# Handoff - inbox-digest

<!--
First file a new session reads after AGENTS.md when work is mid-flight. Update it whenever
work pauses mid-task - before stopping, not after (see AGENTS.md "Documentation rules").
Keep it current rather than complete: stale beats missing, but wrong is worse than either,
so replace sections instead of only appending to them.
-->

Last updated: 2026-10-31

## Current state

Fases 1 y 2 del port terminadas y mergeadas en `dev` (PR #1): scaffold, GitHub configurado
y toda la lógica sin red en Python (135 tests, CI en verde). Todavía no corre contra Google:
faltan los adaptadores, la CLI real y los workflows. **En pausa hasta que Loren tenga la
cuenta/proyecto de GCP.**

DailyReminderBot (Apps Script) sigue en producción y es el que manda el digest diario. No
tocar sus triggers hasta el cutover (fase 5). Su fix de horario UTC ya está desplegado, pero
falta confirmar en un digest real que el resumen use la hora local.

## Active plan

[`2026-10-30-inbox-digest-port.md`](../superpowers/plans/2026-10-30-inbox-digest-port.md).
Decisiones: [ADR 0002](../decisions/0002-python-github-actions.md).

## Pending work

1. **Loren — GCP:**
   - Crear proyecto y habilitar Gmail API, Google Calendar API y Google Sheets API.
   - OAuth consent screen: External, su mail como usuario, **Publish app → In production**
     (en "Testing" el refresh token vence a los 7 días).
   - Credentials → OAuth client ID tipo **Desktop app**.
   - Crear `.env` desde `.env.example` con `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
     `GEMINI_API_KEY` y `STATE_SHEET_ID` (está en las Script Properties del bot viejo).
2. **Fase 3 (no arrancada, nada escrito):** `google_api.py`, `gmail.py`, `calendar.py`,
   `state.py`, `main.py` (`digest`, `classify`, `test-digest`, `diagnose-gemini`) y
   `scripts/get_token.py`. Incluye lo que quedó afuera de la fase 2: lectura de env vars en
   `config.py`, `summarize` y `diagnose_gemini` (HTTP), `apiErrorReason`. Crear la etiqueta
   `No importante`. Sumar `google-api-python-client`, `google-auth-oauthlib`, `google-genai`,
   `gspread`. Validar el parseo de fechas en los adaptadores.
3. Correr `get_token.py`, probar con `uv run inbox-digest test-digest` (no manda nada).
4. **Fase 4:** `digest.yml`, `classify.yml`, `keepalive.yml` con `DRY_RUN=true` y `concurrency`.
   Cargar los 5 secretos en GitHub. El log solo puede traer conteos: los logs son públicos.
5. **Fase 5 (cutover):** comparar 2–3 días con el digest viejo, `DRY_RUN=false`, correr
   `removeTriggers` en el bot viejo, archivarlo y hacer `scripts/gh-flow.sh release`.

## Notas para retomar

- Los modelos usan snake_case: `from` → `sender`, `fromDomain` → `sender_domain`,
  `threadId` → `thread_id`. Fechas `datetime` aware. Tipos en `src/inbox_digest/models.py`.
- `project-init` no tiene stack Python: la capa común se adaptó a mano.
- `dev` y `main` están protegidas: todo va por `scripts/gh-flow.sh` (PR + squash a `dev`).
- `gh repo create --source .` falla dentro de un worktree.

## How to resume

1. Read `AGENTS.md`, then `.agents/CONTEXT.md`.
2. Read the active plan above (if any) and its spec in `docs/superpowers/specs/`.
3. Check `docs/decisions/` for any ADR relevant to the area you're about to touch.
4. Pick up "Pending work" from the top.
