"""Reglas de clasificación. Funciones puras: esto es lo que cubren los tests y lo
que vas a querer editar cuando algo caiga en el bucket equivocado.

El orden importa: la primera regla que matchea gana.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from inbox_digest.types import Bucket, Category, Classified, MailFacts

# Remitentes exactos que siempre quedan en Principal.
ALWAYS_IMPORTANT_SENDERS: list[str] = [
    # "reclutamiento@empresa.com",
]

# Dominios cuyo correo siempre es importante (empresas con las que hablás).
IMPORTANT_DOMAINS: list[str] = [
    # "baldecash.com",
]

# Dominios que siempre van a "Revisar después".
# Se matchean por sufijo, así que `workana.com` cubre `webinar.workana.com`.
LATER_DOMAINS: list[str] = [
    "workana.com",
    "meetup.com",
    "eventbrite.com",
    "newsletter.com",
    # Alertas de empleo y portales freelance: llegan todos los días y nunca piden nada.
    "wellfound.com",
    "freelancer.com",
    # Solo el subdominio de comunicación masiva: el resto de gob.ar (AFIP/ARCA,
    # turnos) puede ser importante.
    "comunicacion.argentina.gob.ar",
]

# Prefijo del asunto del propio digest.
#
# El digest se manda a la misma casilla que `classify` filtra, así que sin esto
# se archiva solo (un título de evento con la palabra "meetup" alcanza) y falla
# en silencio. El comando `digest` arma el asunto con esta constante y la
# primera regla de `RULES` la usa para protegerlo.
SELF_DIGEST_SUBJECT_PREFIX = "Tu día ·"


@dataclass(frozen=True)
class _NormalizedMail:
    from_: str
    domain: str
    subject: str
    snippet: str
    is_promotion: bool
    # subject + snippet, minúsculas y sin acentos.
    haystack: str


@dataclass(frozen=True)
class _Rule:
    category: Category
    bucket: Bucket
    reason: str
    test: Callable[[_NormalizedMail], bool]
    # Regla dura: lo aprendido de tus clicks no la pisa.
    locked: bool = False


def normalize_text(value: str) -> str:
    """Quita acentos y baja a minúsculas para que las keywords matcheen siempre."""
    decomposed = unicodedata.normalize("NFD", value.lower())
    return "".join(c for c in decomposed if not "̀" <= c <= "ͯ")


def domain_of(address: str) -> str:
    match = re.search(r"<?([^<>\s]+@([^<>\s]+))>?\s*$", address.strip())
    return match.group(2).lower() if match else ""


def _has(haystack: str, words: list[str]) -> bool:
    return any(normalize_text(w) in haystack for w in words)


def matches_domain(domain: str, domains: list[str]) -> bool:
    """Match por sufijo: `webinar.workana.com` cuenta como `workana.com`, pero
    `noworkana.com` no. Comparar por igualdad dejaba pasar todos los subdominios.
    """
    return any(domain == d or domain.endswith(f".{d}") for d in domains)


RULES: list[_Rule] = [
    _Rule(
        # PRIMERA a propósito: le tiene que ganar a `event` y `marketing`, porque el
        # cuerpo del digest cita títulos de eventos y asuntos de promos.
        category="other",
        bucket="important",
        reason="es el propio digest — nunca se archiva",
        locked=True,
        test=lambda m: m.subject.startswith(SELF_DIGEST_SUBJECT_PREFIX),
    ),
    _Rule(
        category="other",
        bucket="important",
        reason="remitente en la lista blanca",
        locked=True,
        test=lambda m: any(s.lower() in m.from_ for s in ALWAYS_IMPORTANT_SENDERS),
    ),
    _Rule(
        category="personal-reply",
        bucket="important",
        reason="dominio de una empresa con la que estás hablando",
        locked=True,
        test=lambda m: m.domain in IMPORTANT_DOMAINS,
    ),
    _Rule(
        category="account",
        bucket="important",
        reason="alerta de cuenta o seguridad",
        locked=True,
        test=lambda m: _has(
            m.haystack,
            [
                "inicio de sesion",
                "nuevo dispositivo",
                "verifica tu",
                "codigo de verificacion",
                "restablecer contrasena",
                "security alert",
                "suspicious",
                "two-factor",
                "facturacion",
                "pago rechazado",
                # Binance y Supabase escriben en inglés.
                "verification code",
                "release reminder",
                "alerta de seguridad",
                "llave de acceso",
            ],
        ),
    ),
    _Rule(
        category="assessment",
        bucket="important",
        reason="test técnico o evaluación",
        test=lambda m: _has(
            m.haystack,
            [
                "test tecnico",
                "prueba tecnica",
                "challenge",
                "hackerrank",
                "codility",
                "coderbyte",
                "assessment",
                "evaluacion tecnica",
            ],
        ),
    ),
    _Rule(
        category="meeting",
        bucket="important",
        reason="invitación o cambio de reunión",
        test=lambda m: _has(
            m.haystack,
            [
                "invitacion:",
                "invitation:",
                "actualizado:",
                "updated invitation",
                "cancelado:",
                "google meet",
                "zoom.us",
                "entrevista",
                "reunion agendada",
            ],
        ),
    ),
    _Rule(
        category="application",
        bucket="important",
        reason="confirmación o respuesta a una postulación",
        test=lambda m: _has(
            m.haystack,
            [
                "recibimos tu postulacion",
                "tu postulacion",
                "application received",
                "hemos recibido tu solicitud",
                "teamtailor",
                "gracias por postularte",
                "avanzas a la siguiente",
                "no hemos seleccionado",
                "no avanzaremos",
            ],
        ),
    ),
    _Rule(
        # Gmail manda a Promociones cosas con compromiso real: la confirmación de
        # Expo Empleo (día, hora y dirección asignados) cae ahí. Esta regla corre
        # antes que la señal de Gmail justamente para rescatarlas.
        category="meeting",
        bucket="important",
        reason="confirmación con fecha y horario asignado",
        test=lambda m: _has(
            m.haystack,
            [
                "confirmamos tu",
                "horario asignado",
                "tu turno",
                "turno asignado",
                "reserva confirmada",
                "cita confirmada",
                "te esperamos el",
                "confirmada para el",
            ],
        ),
    ),
    _Rule(
        category="freelance",
        bucket="later",
        reason="portal freelance",
        test=lambda m: matches_domain(m.domain, ["workana.com", "freelancer.com"]),
    ),
    _Rule(
        category="job-alert",
        bucket="later",
        reason="alerta automática de empleo",
        test=lambda m: _has(
            m.haystack,
            [
                "nuevos empleos",
                "empleos para vos",
                "job alert",
                "ofertas que coinciden",
                "nuevas vacantes",
                "jobs you may be interested",
                # Wellfound y Freelancer, verbatim del inbox del 29/09.
                "new jobs",
                "jobs that might interest",
                "might interest you",
                "projects and contests",
                "recommended jobs",
                "empleos recomendados",
            ],
        ),
    ),
    _Rule(
        category="event",
        bucket="later",
        reason="evento masivo o meetup",
        test=lambda m: (
            matches_domain(m.domain, LATER_DOMAINS)
            or _has(
                m.haystack,
                [
                    "webinar",
                    "meetup",
                    "inscribite al evento",
                    "summit",
                    "conferencia online",
                ],
            )
        ),
    ),
    _Rule(
        category="marketing",
        bucket="later",
        reason="promocional",
        test=lambda m: _has(
            m.haystack,
            [
                "descuento",
                "oferta",
                "promocion",
                "black friday",
                "cupon",
                "ultimas horas",
                "newsletter",
                "darse de baja",
                "unsubscribe",
                # Sin espacio: los asuntos reales vienen "15%OFF", no "15 % off".
                "%off",
                "% off",
                "cuotas sin interes",
                "nuevos ingresos",
                "mejor precio",
                "si queres ahorrar",
                "promos",
                # Pie de los envíos masivos (el de Gobierno Nacional, por ejemplo).
                "no soporta mensajes en formato html",
                "ver en el navegador",
                "view in browser",
            ],
        ),
    ),
    _Rule(
        # ÚLTIMA a propósito: Gmail ya clasifica promociones mejor que cualquier
        # lista de keywords, pero la dejamos como red final para que las reglas de
        # arriba sigan definiendo la categoría (un job-alert promocional se reporta
        # como job-alert, no como marketing).
        category="marketing",
        bucket="later",
        reason="Gmail lo puso en Promociones",
        test=lambda m: m.is_promotion,
    ),
]


def _classified(
    mail: MailFacts, bucket: Bucket, category: Category, reason: str, locked: bool = False
) -> Classified:
    return Classified(
        thread_id=mail.thread_id,
        sender=mail.sender,
        sender_domain=mail.sender_domain,
        subject=mail.subject,
        snippet=mail.snippet,
        date=mail.date,
        permalink=mail.permalink,
        is_promotion=mail.is_promotion,
        bucket=bucket,
        category=category,
        reason=reason,
        locked=locked,
    )


def classify_mail(mail: MailFacts) -> Classified:
    """Clasifica un mail. Default conservador: lo que no matchea ninguna regla se
    queda en Principal — preferimos ruido a perder algo importante.
    """
    normalized = _NormalizedMail(
        from_=mail.sender.lower(),
        domain=mail.sender_domain or domain_of(mail.sender),
        subject=mail.subject,
        snippet=mail.snippet,
        is_promotion=mail.is_promotion,
        haystack=normalize_text(f"{mail.subject} {mail.snippet}"),
    )

    for rule in RULES:
        if rule.test(normalized):
            return _classified(mail, rule.bucket, rule.category, rule.reason, rule.locked)

    return _classified(
        mail, "important", "other", "sin regla que aplique — queda en Principal por defecto"
    )


# Orden de prioridad por categoría, para cuando no hay IA.
# Menor número = más arriba. Es el criterio de respaldo, no el principal.
CATEGORY_PRIORITY: dict[Category, int] = {
    "account": 0,
    "meeting": 1,
    "assessment": 2,
    "personal-reply": 3,
    "application": 4,
    "other": 5,
    "job-alert": 6,
    "freelance": 7,
    "event": 8,
    "marketing": 9,
}

# Etiquetas legibles para el resumen de "el resto".
CATEGORY_LABELS: dict[Category, str] = {
    "personal-reply": "respuestas personales",
    "meeting": "reuniones",
    "account": "alertas de cuenta",
    "assessment": "tests técnicos",
    "application": "postulaciones",
    "job-alert": "alertas de empleo",
    "freelance": "freelance",
    "marketing": "promocionales",
    "event": "eventos",
    "other": "otros",
}
