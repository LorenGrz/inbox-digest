"""HTML del mail.

Gmail descarta `<style>` en buena parte de sus clientes, así que el template va
con CSS inline y tablas para el layout. Nada de flexbox ni grid.

Este módulo decide *qué* se muestra (tarjetas, resumen, grupos); el *cómo* vive en
`templates/digest.html.j2`, con autoescape activado: todo texto de terceros se
escapa en el sink y no hay que acordarse de hacerlo a mano.
"""

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from inbox_digest.config import FEEDBACK_LABEL, TIMEZONE
from inbox_digest.context import relative_time
from inbox_digest.gemini import MAX_HIGHLIGHTS
from inbox_digest.rules import CATEGORY_LABELS, CATEGORY_PRIORITY
from inbox_digest.timeutil import event_time_label, is_multi_day
from inbox_digest.types import AiGroup, AiItem, Classified, DigestModel, EventFacts

# Un color por categoría, para el avatar. Suficiente contraste sobre blanco.
_CATEGORY_COLORS: dict[str, str] = {
    "application": "#7c3aed",
    "meeting": "#0891b2",
    "account": "#dc2626",
    "assessment": "#ea580c",
    "personal-reply": "#2563eb",
    "job-alert": "#65a30d",
    "freelance": "#ca8a04",
    "marketing": "#6b7280",
    "event": "#db2777",
    "other": "#475569",
}

# Los conteos y las tarjetas se indexan por str, no por el Literal de Category.
_LABELS: dict[str, str] = {str(k): v for k, v in CATEGORY_LABELS.items()}

_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def sender_name(sender: str, fallback_domain: str) -> str:
    """Nombre legible del remitente.

    El header From viene como `"SMG Selección" <noreply@successfactors.com>` y
    mostrarlo crudo queda feo. Preferimos el display name; si no hay, el dominio.
    """
    match = re.match(r'^\s*"?([^"<]+?)"?\s*<', sender)
    name = match.group(1).strip() if match else ""
    if name and "@" not in name:
        return name
    return fallback_domain or sender


def _avatar_letter(name: str) -> str:
    """Inicial del remitente, en mayúscula; "?" si no hay letras ni números."""
    for char in name:
        if char.isalpha() or char.isnumeric():
            return char.upper()
    return "?"


def summarize_counts(counts: dict[str, int]) -> str:
    """ "4 postulaciones, 3 alertas de cuenta"."""
    parts = [
        f"{n} {_LABELS.get(category, category)}"
        for category, n in sorted(counts.items(), key=lambda entry: -entry[1])
    ]
    return ", ".join(parts) if parts else "nada"


def groups_with_rest(model: DigestModel) -> list[AiGroup]:
    """Grupos de Gemini + un grupo final con lo que haya quedado afuera.

    Nunca perdemos un mail: si el modelo falla, se confunde o una inyección lo
    empuja a omitir algo, ese mail igual se renderiza. Sin IA, un solo grupo.
    """
    if model.ai is None or not model.ai.groups:
        return [AiGroup(title="", items=[AiItem(i, "") for i in range(len(model.important))])]
    grouped = {item.index for group in model.ai.groups for item in group.items}
    rest = [AiItem(i, "") for i in range(len(model.important)) if i not in grouped]
    if rest:
        return [*model.ai.groups, AiGroup(title="Lo demás", items=rest)]
    return model.ai.groups


def highlight_indexes(model: DigestModel) -> list[int]:
    """Los pocos mails que se muestran como tarjeta.

    La decisión la toma el modelo (`highlights`, ordenado por urgencia). Sin IA,
    cae a lo aprendido de tus clicks (`score`) y después al orden por categoría,
    para que el mail siga siendo útil. Devuelve índices sobre `model.important`.
    """
    if model.ai is not None and model.ai.highlights:
        return model.ai.highlights
    ranked = sorted(
        enumerate(model.important),
        # Sin evidencia, 0.5: ni arriba ni abajo de lo que ya se aprendió. Orden
        # estable, así que los empates conservan el orden de llegada.
        key=lambda entry: (
            -(entry[1].score if entry[1].score is not None else 0.5),
            CATEGORY_PRIORITY.get(entry[1].category, 99),
        ),
    )
    return [index for index, _ in ranked[:MAX_HIGHLIGHTS]]


def _local_date(date: datetime) -> str:
    return f"{date.astimezone(TIMEZONE):%Y-%m-%d}"


def _list_es(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} y {items[-1]}"


def _overlaps(a: EventFacts, b: EventFacts) -> bool:
    """Choque real de horarios. Los de todo el día y los de varios días (un viaje)
    se solapan con todo, así que avisar no aporta nada.
    """
    if a.all_day or b.all_day or is_multi_day(a) or is_multi_day(b):
        return False
    return a.start < b.end and b.start < a.end


def rule_summary(model: DigestModel) -> str:
    """Resumen armado por reglas, para cuando Gemini no responde.

    Antes, sin IA el bloque "Tu día en breve" desaparecía en silencio. Ahora
    siempre hay un briefing: qué tenés hoy (y si algo se pisa), qué mails mirar,
    y qué se viene.
    """
    paragraphs: list[str] = []

    if not model.today:
        paragraphs.append("Hoy no tenés nada en la agenda.")
    else:
        items = [f"{e.title} ({event_time_label(e)})" for e in model.today]
        text = f"Hoy tenés {len(model.today)} evento(s): {_list_es(items)}."
        clashes = [
            f"{a.title} y {b.title}"
            for i, a in enumerate(model.today)
            for b in model.today[i + 1 :]
            if _overlaps(a, b)
        ]
        if clashes:
            text += f" Ojo: se pisan {_list_es(clashes)}."
        paragraphs.append(text)

    # El índice puede venir de un modelo: se descarta lo que caiga fuera de rango.
    shown = [model.important[i] for i in highlight_indexes(model) if 0 <= i < len(model.important)][
        :3
    ]
    if not shown:
        paragraphs.append("En el correo no hay nada que pida tu atención.")
    else:
        items = [f"«{m.subject}» de {sender_name(m.sender, m.sender_domain)}" for m in shown]
        extra = len(model.important) - len(shown)
        paragraphs.append(
            f"Para mirar en el correo: {_list_es(items)}{f', y {extra} más' if extra > 0 else ''}."
        )

    coming = [r for r in model.reminders if r.days_away > 0]
    if coming:
        items = [f"{r.title} en {r.days_away} día(s)" for r in coming]
        paragraphs.append(f"Se viene: {_list_es(items)}.")

    return "\n".join(paragraphs)


def _rest_line(model: DigestModel, shown: list[int]) -> str:
    """ "9 más: 4 postulaciones, 3 cuentas". Lo que no entró como tarjeta."""
    hidden = [m for i, m in enumerate(model.important) if i not in shown]
    if not hidden:
        return ""
    counts: dict[str, int] = {}
    for mail in hidden:
        counts[mail.category] = counts.get(mail.category, 0) + 1
    return f"{len(hidden)} mail(s) importantes más — {summarize_counts(counts)}"


def _card(mail: Classified, now: datetime, notes: dict[int, str], index: int) -> dict[str, str]:
    snippet = mail.snippet[:160] + ("…" if len(mail.snippet) > 160 else "")
    return {
        "subject": mail.subject,
        "name": sender_name(mail.sender, mail.sender_domain),
        "domain": mail.sender_domain,
        "when": relative_time(mail.date, now),
        "snippet": snippet,
        "note": notes.get(index, ""),
        "label": _LABELS.get(mail.category, mail.category),
        "color": _CATEGORY_COLORS.get(mail.category, _CATEGORY_COLORS["other"]),
        "letter": _avatar_letter(mail.sender or mail.sender_domain),
        # El link sale del permalink real, nunca de algo que dijo el modelo.
        "link": mail.permalink,
    }


def render_digest(model: DigestModel, now: datetime | None = None) -> str:
    now = now or datetime.now(TIMEZONE)

    # Notas de la IA, indexadas por mail, para colgarlas de la tarjeta.
    notes: dict[int, str] = {}
    if model.ai is not None:
        for group in model.ai.groups:
            for item in group.items:
                if item.note:
                    notes[item.index] = item.note

    shown = highlight_indexes(model)
    cards = [
        _card(model.important[i], now, notes, i) for i in shown if 0 <= i < len(model.important)
    ]

    # El resumen puede venir en varios párrafos; respetamos los saltos de línea.
    # Sin IA sale el de reglas: el bloque nunca desaparece.
    summary_text = model.ai.summary if model.ai and model.ai.summary.strip() else None
    summary_text = summary_text or rule_summary(model)
    summary_paragraphs = [p.strip() for p in summary_text.split("\n") if p.strip()]

    return _ENV.get_template("digest.html.j2").render(
        date=model.date,
        counts=f"{len(model.today)} evento(s) · {len(model.important)} mail(s) importantes",
        summary_paragraphs=summary_paragraphs,
        today=[
            {
                "time": event_time_label(e),
                "title": e.title,
                "badge": "" if e.kind == "generic" else e.kind,
                "location": e.location,
            }
            for e in model.today
        ],
        cards=cards,
        rest_line=_rest_line(model, shown),
        # Lo de hoy ya está en la agenda; acá va solo lo que viene.
        reminders=[
            f"En {r.days_away} día(s): {r.title}" for r in model.reminders if r.days_away > 0
        ],
        applications=[
            f"{a.company} · {a.role} — sin respuesta desde {_local_date(a.applied_at)}"
            for a in model.stale_applications
        ],
        generated=f"{now.astimezone(TIMEZONE):%H:%M}",
        has_ai=model.ai is not None,
        feedback_label=FEEDBACK_LABEL,
    )
