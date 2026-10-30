"""Lógica pura del contexto: qué tipo de evento es, cuándo recordarlo, y qué
postulación confirma un mail.

Nada de esto toca Google, así que se testea sin shims.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from inbox_digest.rules import normalize_text
from inbox_digest.types import Classified, EventFacts, EventKind, Reminder

# Cuántos días antes avisar, según qué tan importante sea el evento.
_REMINDER_OFFSETS: dict[EventKind, list[int]] = {
    "interview": [7, 3, 1, 0],
    "defense": [7, 3, 1, 0],
    "assessment": [3, 1, 0],
    "meetup": [1, 0],
    "generic": [0],
}

# El orden es semántico: la primera categoría que matchea gana.
_KIND_KEYWORDS: list[tuple[EventKind, list[str]]] = [
    ("defense", ["defensa", "presentacion final", "tesis", "demo day"]),
    ("interview", ["entrevista", "interview", "call con", "screening", "rrhh", "1:1 con"]),
    (
        "assessment",
        ["tecnica", "technical", "challenge", "live coding", "pair programming", "test"],
    ),
    ("meetup", ["meetup", "webinar", "charla", "conferencia", "workshop"]),
]


@dataclass(frozen=True)
class ApplicationRef:
    company: str
    role: str


def classify_event(title: str, guest_domains: tuple[str, ...] = ()) -> EventKind:
    haystack = normalize_text(title)
    for kind, words in _KIND_KEYWORDS:
        if any(normalize_text(w) in haystack for w in words):
            return kind
    # Un evento con invitados de afuera pesa más que uno propio, aunque el título
    # no diga nada.
    external = [d for d in guest_domains if not d.endswith("gmail.com")]
    return "interview" if external else "generic"


def reminder_offsets(kind: EventKind) -> list[int]:
    return _REMINDER_OFFSETS[kind]


def due_reminders(events: list[EventFacts], already_sent: set[str]) -> list[Reminder]:
    """Recordatorios que corresponden hoy y todavía no se mandaron.

    La clave (`event_id@offset`) es lo que se guarda en el Sheet para no repetir.
    """
    due: list[Reminder] = []
    for event in events:
        if event.days_away < 0:
            continue
        if event.days_away not in reminder_offsets(event.kind):
            continue
        key = f"{event.id}@{event.days_away}"
        if key in already_sent:
            continue
        due.append(Reminder(event.id, event.title, event.days_away, key))
    return due


def relative_time(date: datetime, now: datetime) -> str:
    """ "hace 3 h", "ayer", "hace 2 d". Igual que la marca de tiempo de Reddit.

    Pura a propósito: la fecha ya viene parseada, así que el caso "fecha inválida"
    del original se resuelve en el adaptador, no acá.
    """
    minutes = int((now - date).total_seconds() // 60)
    if minutes < 1:
        return "recién"
    if minutes < 60:
        return f"hace {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"hace {hours} h"
    days = hours // 24
    if days == 1:
        return "ayer"
    return f"hace {days} d"


def parse_application(mail: Classified) -> ApplicationRef | None:
    """Empresa + puesto a partir del asunto de una confirmación de postulación."""
    if mail.category != "application":
        return None
    company = mail.sender_domain.split(".")[0] or mail.sender_domain
    # "Recibimos tu postulación para Backend Developer" -> "Backend Developer"
    role_match = re.search(
        r"(?:para|for|al puesto de|como)\s+(.{3,60})", mail.subject, re.IGNORECASE
    )
    role = (
        re.sub(r"[.!—-].*$", "", role_match.group(1), count=1).strip()
        if role_match
        else mail.subject[:60]
    )
    return ApplicationRef(company=company, role=role)
