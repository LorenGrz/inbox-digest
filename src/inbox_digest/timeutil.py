"""Helpers de fechas en la zona del digest. Puros: solo `zoneinfo`, sin Apps Script."""

from datetime import datetime, timedelta

from inbox_digest.config import TIMEZONE
from inbox_digest.types import EventFacts

_DIAS = ("domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado")
_MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def start_of_day(date: datetime) -> datetime:
    """Medianoche, en la zona del digest, del día en que cae `date`."""
    return date.astimezone(TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)


def add_days(date: datetime, days: int) -> datetime:
    """Suma días calendario conservando la hora de pared (no 24 h exactas)."""
    return date.astimezone(TIMEZONE) + timedelta(days=days)


def days_between(start: datetime, end: datetime) -> int:
    """Días calendario entre dos fechas, ignorando la hora."""
    return (end.astimezone(TIMEZONE).date() - start.astimezone(TIMEZONE).date()).days


def overlaps_day(event: EventFacts, day: datetime) -> bool:
    """Un evento cuenta como "de hoy" si se solapa con hoy, aunque haya arrancado antes.

    Filtrar por `days_away == 0` hacía desaparecer los multi-día: Nerdearla
    (22 al 26) daba days_away = -2 el 24 y no entraba ni en hoy ni en lo que viene.
    """
    return days_between(day, event.start) <= 0 and days_between(day, event.end) >= 0


def is_multi_day(event: EventFacts) -> bool:
    """Empieza y termina en días distintos (en la zona del digest).

    Un evento que termina justo a las 00:00 del día siguiente no cuenta: restamos 1 ms.
    """
    end = event.end - timedelta(milliseconds=1)
    return event.start.astimezone(TIMEZONE).date() != end.astimezone(TIMEZONE).date()


def event_time_label(event: EventFacts) -> str:
    """Texto corto para mostrar el horario de un evento, en hora local.

    Los de varios días llevan la fecha: un viaje del 29/09 13:00 al 2/10 14:00 se
    mostraba "13:00–14:00" y parecía una reunión de una hora.
    """
    if event.all_day:
        return "Todo el día"
    start = event.start.astimezone(TIMEZONE)
    end = event.end.astimezone(TIMEZONE)
    if is_multi_day(event):
        return (
            f"{start.day}/{start.month:02d} {start:%H:%M} → {end.day}/{end.month:02d} {end:%H:%M}"
        )
    return f"{start:%H:%M}–{end:%H:%M}"


def long_date_es(date: datetime) -> str:
    """ "jueves 24 de septiembre de 2026".

    Armado a mano en vez de `strftime('%A %B')`, que depende del locale del
    proceso y salía en inglés.
    """
    local = date.astimezone(TIMEZONE)
    # weekday() es 0 = lunes; la tabla arranca en domingo.
    weekday = (local.weekday() + 1) % 7
    return f"{_DIAS[weekday]} {local.day} de {_MESES[local.month - 1]} de {local.year}"
