# 0002. Python + APIs de Google + GitHub Actions en lugar de Apps Script

## Status

Accepted

## Date

2026-10-30

## Context

DailyReminderBot corre en Google Apps Script (TS → esbuild → IIFE → clasp). Funciona,
pero es difícil de debuguear, los logs son pobres, el bundle necesita trucos (entry
points globales) y el botón de feedback exige una web app con HMAC y redeploy en cada
push. Loren prefiere Python para automatizaciones y lo está aprendiendo.

## Decision

Script en Python 3.13 (`uv`) que usa las APIs oficiales (`google-api-python-client`,
`gspread`, `google-genai`) con un OAuth de usuario (refresh token), ejecutado por dos
workflows con `schedule:` en GitHub Actions. El estado sigue en el mismo Google Sheet. El
botón "No es importante" se reemplaza por una etiqueta de Gmail (`No importante`) que
`classify` procesa: no hace falta ningún servidor.

## Alternatives considered

- **Seguir en Apps Script** — cero infraestructura y OAuth implícito, pero es justo lo que se quiere dejar.
- **Node/TS + googleapis** — reusaría casi todo el código, pero Loren prefiere Python para automatizaciones.
- **AWS Lambda + EventBridge** — cron exacto y un endpoint para el botón, a cambio de IAM, SAM y costos. Excesivo para una cuenta.
- **Cron en un VPS o Raspberry** — exige una máquina prendida y mantenida.
- **n8n / Make / Zapier** — el Naive Bayes y las reglas ordenadas no entran bien.

## Consequences

- OAuth manual: crear un cliente en Google Cloud y pasar la app a "In production" (sin
  verificar, 1 usuario). En "Testing" el refresh token de Gmail vence a los 7 días.
- Repo público ⇒ logs de Actions públicos: solo se loguean conteos.
- El cron de Actions es aproximado (5–15 min de atraso) y GitHub lo desactiva tras 60 días
  sin actividad: `keepalive.yml`.
- El feedback por etiqueta es menos directo que un botón (abrir el hilo y etiquetar),
  pero no necesita web app, firma ni deployments.
- Si algún día hace falta un endpoint (botón de un click), se agrega una función chica
  (Cloud Run o Lambda) sin cambiar el resto.
