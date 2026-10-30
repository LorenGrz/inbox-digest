# Fase 2 — spec para el worker: port de la lógica pura

Fuente: `~/projects/DailyReminderBot` (TS, solo lectura). Destino: `~/projects/inbox-digest`,
rama `feat/port-pure-logic`. Plan general: `2026-10-30-inbox-digest-port.md`.

## Qué portar (sin red, sin APIs de Google)
| TS (fuente) | Python (destino) |
|---|---|
| `src/types.ts` | `src/inbox_digest/types.py` — `@dataclass(frozen=True)` + `Literal`; fechas como `datetime` aware |
| `src/config.ts` (solo constantes) | `src/inbox_digest/config.py` — `TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")`, `LOOKAHEAD_DAYS`, `LATER_LABEL`, `FEEDBACK_LABEL = "No importante"`, `DEFAULT_GEMINI_MODEL`. Lectura de env vars en fase 3 |
| `src/rules.ts` | `rules.py` — 1:1, **mismo orden de `RULES`** |
| `src/context.ts` | `context.py` |
| `src/learn.ts` | `learn.py` — mismos umbrales y features |
| helpers puros de `src/calendar.ts` (`start_of_day`, `add_days`, `days_between`, `overlaps_day`, `is_multi_day`, `event_time_label`, `long_date_es`) | `timeutil.py`, con `zoneinfo` (sin `Utilities`) |
| `src/render.ts` | `render.py` + `src/inbox_digest/templates/digest.html.j2` (jinja2, autoescape on). Mismo HTML visual. Cada tarjeta linkea al hilo (`permalink`); **no** hay botón "No es importante": en su lugar una línea al pie: "¿Algo no era importante? Ponele la etiqueta «No importante» y aprendo." |
| partes puras de `src/gemini.ts` | `gemini.py`: `SYSTEM_PROMPT` verbatim, response schema, `build_payload` (con `horario` local vía `event_time_label`, `lugar`, como en el fix del 30/10), `parse_ai_summary` (validar con pydantic, la salida es dato hostil), `sanitize_text`, `backoff_ms`, `thinking_config`, `MAX_HIGHLIGHTS`. La llamada HTTP queda para fase 3 |

## Tests
Portar `tests/{rules,context,learn,render,gemini}.test.ts` a `tests/test_*.py` con los
mismos casos. Ojo: el shim de TS formateaba en UTC; en Python se formatea en ART de verdad,
así que armar los fixtures con datetimes en ART (ej. `datetime(2026,10,29,18,30,tzinfo=TIMEZONE)`
→ `"18:30–21:30"`). Agregar: `build_payload` contiene el horario local y nunca un ISO.
Nombres: `test_should_<esperado>_when_<condicion>`.

## Restricciones
- Ningún módulo de esta fase importa `googleapiclient`, `gspread`, `google.genai` ni hace red.
- mypy --strict sin `Any` ni `type: ignore` salvo justificado.
- Dependencias runtime: `uv add jinja2 pydantic`. Nada más.
- `docs/prompts.md`: completar con el prompt verbatim, dónde vive y la historia (traer la de `~/projects/DailyReminderBot/docs/prompts.md`, más "port a Python").
- Borrar `tests/test_smoke.py` si queda redundante.

## Aceptación
`bash scripts/check.sh` en verde. Commits Conventional en la rama `feat/port-pure-logic`
(no pushear, no tocar `main`).
