# inbox-digest - Repository Context

<!-- Keep this file <= 60 lines: CLAUDE.md imports it into every session automatically. -->

## Purpose

Digest diario de Gmail + Calendar y clasificador del inbox, en Python sobre GitHub Actions. Port de DailyReminderBot (Apps Script).

## Stack

Python 3.13 + uv; google-api-python-client, gspread, google-genai; ruff, mypy --strict, pytest.

## Commands

See AGENTS.md for the full table (dev/test/lint/typecheck/format/format:check).

## Architecture

Ver `docs/architecture.md`. Estado: fase 1 (scaffold) del plan `docs/superpowers/plans/2026-10-30-inbox-digest-port.md`.

## Conventions

Ver "Reglas del proyecto" en AGENTS.md.

## Known issues

<!-- Keep current. -->

## Repo facts

- Owner: LorenGrz
- Base branch: dev (main is release-only) — full git rules + where each is enforced: "Workflow contract" in AGENTS.md
- Project number: TBD

Last validated: 2026-10-30
