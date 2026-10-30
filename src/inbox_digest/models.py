"""Tipos compartidos. Datos inmutables, sin dependencias de Google, para que sean testeables.

Las fechas son `datetime` con zona (aware): quien las construye (los adaptadores)
valida en el borde, y de ahí para adentro nadie parsea strings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Bucket = Literal["important", "later"]

Category = Literal[
    "personal-reply",
    "meeting",
    "account",
    "assessment",
    "application",
    "job-alert",
    "freelance",
    "marketing",
    "event",
    "other",
]

EventKind = Literal["interview", "defense", "assessment", "meetup", "generic"]


@dataclass(frozen=True)
class MailFacts:
    """Lo mínimo que necesitamos de un mail para clasificarlo. Nunca el cuerpo completo.

    `sender` es el header From crudo (`from` es palabra reservada en Python).
    """

    thread_id: str
    sender: str
    sender_domain: str
    subject: str
    snippet: str
    date: datetime
    permalink: str
    # Gmail lo puso en la categoría Promociones. La API no lo expone por mensaje,
    # así que el adaptador lo resuelve con una búsqueda aparte `category:promotions`
    # y la intersección por thread_id.
    is_promotion: bool


@dataclass(frozen=True)
class Classified(MailFacts):
    bucket: Bucket
    category: Category
    reason: str
    # Lo decidió una regla dura (el propio digest, lista blanca, seguridad). Lo
    # aprendido de tus clicks nunca lo pisa. En TS era `true | undefined`; acá
    # `False` hace de ausente.
    locked: bool = False
    # P(importante) según Naive Bayes; None cuando todavía no hay evidencia.
    score: float | None = None


@dataclass(frozen=True)
class EventFacts:
    id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str
    guest_domains: tuple[str, ...]
    kind: EventKind
    days_away: int


@dataclass(frozen=True)
class Reminder:
    event_id: str
    title: str
    days_away: int
    # Clave de idempotencia: un recordatorio por evento y por offset.
    key: str


@dataclass(frozen=True)
class Application:
    company: str
    role: str
    applied_at: datetime
    status: Literal["open", "closed"]
    last_update: datetime


@dataclass(frozen=True)
class AiItem:
    index: int
    note: str


@dataclass(frozen=True)
class AiGroup:
    title: str
    items: list[AiItem]


@dataclass(frozen=True)
class AiSummary:
    """Salida de Gemini, ya validada.

    El modelo nunca devuelve HTML ni URLs: solo texto e `index`, que apunta a la
    posición del mail en `DigestModel.important`. El link lo pone el render con
    el permalink real. Así una inyección en el asunto de un mail no puede meter
    un enlace ni markup en el digest.
    """

    summary: str
    groups: list[AiGroup]
    # Índices de los pocos mails que merecen aparecer en el mail, por urgencia.
    highlights: list[int]


@dataclass(frozen=True)
class DigestModel:
    """Todo lo que el render (y opcionalmente Gemini) necesita saber del día."""

    date: str
    today: list[EventFacts] = field(default_factory=list)
    upcoming: list[EventFacts] = field(default_factory=list)
    reminders: list[Reminder] = field(default_factory=list)
    important: list[Classified] = field(default_factory=list)
    stale_applications: list[Application] = field(default_factory=list)
    # Resultado de Gemini; None cuando falla o está desactivado.
    ai: AiSummary | None = None
