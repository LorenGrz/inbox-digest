"""Fábricas de datos para los tests.

Todas las fechas son datetimes en ART de verdad (a diferencia del shim de TS, que
formateaba en UTC): `art(2026, 10, 29, 18, 30)` se muestra como "18:30".
"""

from datetime import datetime

from inbox_digest.config import TIMEZONE
from inbox_digest.models import (
    AiSummary,
    Application,
    Bucket,
    Category,
    Classified,
    DigestModel,
    EventFacts,
    EventKind,
    MailFacts,
    Reminder,
)


def art(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TIMEZONE)


def mail_facts(
    *,
    sender: str = "Alguien <alguien@ejemplo.com>",
    sender_domain: str = "ejemplo.com",
    subject: str = "",
    snippet: str = "",
    is_promotion: bool = False,
) -> MailFacts:
    return MailFacts(
        thread_id="t1",
        sender=sender,
        sender_domain=sender_domain,
        subject=subject,
        snippet=snippet,
        date=art(2026, 9, 23, 7),
        permalink="https://mail.google.com/x",
        is_promotion=is_promotion,
    )


def classified(
    subject: str = "",
    *,
    sender: str = "Alguien <alguien@ejemplo.com>",
    sender_domain: str = "ejemplo.com",
    snippet: str = "",
    permalink: str = "https://mail.google.com/x",
    date: datetime | None = None,
    bucket: Bucket = "important",
    category: Category = "other",
    reason: str = "",
    locked: bool = False,
    score: float | None = None,
) -> Classified:
    return Classified(
        thread_id="t1",
        sender=sender,
        sender_domain=sender_domain,
        subject=subject,
        snippet=snippet,
        date=date or art(2026, 9, 23, 7),
        permalink=permalink,
        is_promotion=False,
        bucket=bucket,
        category=category,
        reason=reason,
        locked=locked,
        score=score,
    )


def event(
    title: str = "Evento",
    *,
    id: str = "e1",
    start: datetime | None = None,
    end: datetime | None = None,
    all_day: bool = False,
    location: str = "",
    kind: EventKind = "generic",
    days_away: int = 7,
) -> EventFacts:
    return EventFacts(
        id=id,
        title=title,
        start=start or art(2026, 9, 30, 10),
        end=end or art(2026, 9, 30, 11),
        all_day=all_day,
        location=location,
        guest_domains=(),
        kind=kind,
        days_away=days_away,
    )


def digest(
    *,
    date: str = "jueves 24 septiembre 2026",
    today: list[EventFacts] | None = None,
    upcoming: list[EventFacts] | None = None,
    reminders: list[Reminder] | None = None,
    important: list[Classified] | None = None,
    stale_applications: list[Application] | None = None,
    ai: AiSummary | None = None,
) -> DigestModel:
    return DigestModel(
        date=date,
        today=today or [],
        upcoming=upcoming or [],
        reminders=reminders or [],
        important=important or [],
        stale_applications=stale_applications or [],
        ai=ai,
    )
