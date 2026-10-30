import pytest
from factories import mail_facts

from inbox_digest.models import Bucket, MailFacts
from inbox_digest.rules import (
    RULES,
    SELF_DIGEST_SUBJECT_PREFIX,
    classify_mail,
    domain_of,
    matches_domain,
    normalize_text,
)


def test_should_extract_domain_when_from_has_display_name() -> None:
    assert domain_of("Recruiting Team <talent@Baldecash.com>") == "baldecash.com"


def test_should_extract_domain_when_address_is_bare() -> None:
    assert domain_of("hola@workana.com") == "workana.com"


def test_should_return_empty_domain_when_there_is_no_address() -> None:
    assert domain_of("sin dirección") == ""


def test_should_strip_accents_and_lowercase_when_normalizing() -> None:
    assert normalize_text("Postulación TÉCNICA") == "postulacion tecnica"


def test_should_send_job_alerts_to_later() -> None:
    result = classify_mail(
        mail_facts(subject="15 nuevos empleos para vos", sender_domain="linkedin.com")
    )
    assert result.bucket == "later"
    assert result.category == "job-alert"


def test_should_send_workana_to_later() -> None:
    result = classify_mail(
        mail_facts(
            sender="Workana <no-reply@workana.com>",
            sender_domain="workana.com",
            subject="Nuevo proyecto",
        )
    )
    assert result.bucket == "later"
    assert result.category == "freelance"


def test_should_keep_account_alerts_in_main() -> None:
    result = classify_mail(mail_facts(subject="Código de verificación"))
    assert result.bucket == "important"
    assert result.category == "account"


def test_should_detect_technical_tests_when_written_without_accents() -> None:
    result = classify_mail(mail_facts(subject="Tu prueba tecnica en HackerRank"))
    assert result.category == "assessment"


def test_should_detect_application_confirmations() -> None:
    result = classify_mail(mail_facts(subject="Recibimos tu postulación para Backend Developer"))
    assert result.category == "application"
    assert result.bucket == "important"


def test_should_keep_mail_in_main_when_no_rule_matches() -> None:
    result = classify_mail(mail_facts(subject="Che, una consulta"))
    assert result.bucket == "important"
    assert result.category == "other"


def test_should_let_security_win_over_promotional_when_both_match() -> None:
    result = classify_mail(
        mail_facts(subject="Security alert", snippet="20% de descuento darse de baja")
    )
    assert result.bucket == "important"


def test_should_match_subdomains_when_domain_ends_with_listed_one() -> None:
    assert matches_domain("webinar.workana.com", ["workana.com"]) is True


def test_should_match_exact_domain() -> None:
    assert matches_domain("workana.com", ["workana.com"]) is True


def test_should_not_match_domain_when_it_only_ends_similarly() -> None:
    assert matches_domain("noworkana.com", ["workana.com"]) is False


# El digest no se archiva a sí mismo. Regresión del bug: el digest va a la misma
# casilla que `classify` filtra, y su cuerpo cita títulos de eventos y asuntos de promos.
def test_should_not_archive_own_digest_when_agenda_has_a_meetup() -> None:
    result = classify_mail(
        mail_facts(
            sender_domain="gmail.com",
            subject=f"{SELF_DIGEST_SUBJECT_PREFIX} 24/09 · 1 evento(s), 5 mail(s)",
            snippet="AGENDA DE HOY 19:00 Meetup de Python en Buenos Aires",
        )
    )
    assert result.bucket == "important"
    assert "propio digest" in result.reason


def test_should_not_archive_own_digest_when_body_quotes_promo_subjects() -> None:
    result = classify_mail(
        mail_facts(
            sender_domain="gmail.com",
            subject=f"{SELF_DIGEST_SUBJECT_PREFIX} 24/09 · 1 evento(s), 5 mail(s)",
            snippet="EL RESTO 14 promocionales: 15%OFF, descuento, unsubscribe",
        )
    )
    assert result.bucket == "important"


def test_should_not_archive_own_digest_when_gmail_marks_it_as_promotion() -> None:
    result = classify_mail(
        mail_facts(
            sender_domain="gmail.com",
            subject=f"{SELF_DIGEST_SUBJECT_PREFIX} 24/09 · 1 evento(s), 5 mail(s)",
            snippet="webinar meetup descuento",
            is_promotion=True,
        )
    )
    assert result.bucket == "important"


def test_should_archive_mail_when_gmail_marks_it_as_promotion() -> None:
    result = classify_mail(mail_facts(subject="Novedades", is_promotion=True))
    assert result.bucket == "later"
    assert "Gmail" in result.reason


def test_should_not_archive_security_alert_when_gmail_miscategorizes_it() -> None:
    result = classify_mail(
        mail_facts(subject="Alerta de seguridad en tu cuenta", is_promotion=True)
    )
    assert result.bucket == "important"
    assert result.category == "account"


def test_should_prefer_specific_rule_over_gmail_category() -> None:
    result = classify_mail(
        mail_facts(
            subject="15 nuevos empleos para vos", is_promotion=True, sender_domain="linkedin.com"
        )
    )
    assert result.category == "job-alert"


# Fixtures verbatim del inbox del 23/09/2026: los casos que el clasificador dejaba pasar.
_CASOS_23_09: list[tuple[str, dict[str, str | bool], Bucket]] = [
    (
        "promo de Día",
        {
            "sender_domain": "news.supermercadosdia.com.ar",
            "subject": "Especial primavera con 𝗣𝗥𝗢𝗠𝗢𝗦 𝗕𝗢𝗠𝗕𝗔 + 15%OFF 🌸🛒",
            "snippet": "¡Abrí si queres ahorrar!",
        },
        "later",
    ),
    (
        "promo de Compra Gamer",
        {
            "sender_domain": "compragamer.com",
            "subject": "¡Nuevos ingresos Samsung en Compra Gamer!",
            "snippet": "Descubrilos al mejor precio y aprovechá hasta 12 cuotas sin interés.",
        },
        "later",
    ),
    (
        "webinar de Workana (subdominio)",
        {
            "sender_domain": "webinar.workana.com",
            "subject": "Todavía estás a tiempo… ¿te lo vas a perder? 👀",
            "snippet": "El replay de nuestra clase especial aún está disponible.",
        },
        "later",
    ),
    (
        "bienvenida de meetup.com",
        {
            "sender_domain": "meetup.com",
            "subject": "Bienvenido a React Buenos Aires",
            "snippet": "Bienvenido! Si estás interesado en contarnos algo.",
        },
        "later",
    ),
    (
        # Gmail lo pone en category:promotions. Si le creyéramos, se archivaría
        # una cita con día, hora y dirección asignados.
        "Expo Empleo, que Gmail marca como promoción",
        {
            "sender_domain": "vicentelopez.gov.ar",
            "subject": "Confirmamos tu vacante - 4° Edición de Expo Empleo 2026",
            "snippet": (
                "Confirmamos tu vacante para la 4° Edición de Expo Empleo 2026 Jueves 24 de "
                "Septiembre Horario asignado: 11:00 hs. Villate 4480, Munro"
            ),
            "is_promotion": True,
        },
        "important",
    ),
    (
        "código de Binance en inglés",
        {
            "sender_domain": "ses.binance.com",
            "subject": "[Binance] Release P2P Payment - 2026-09-23 15:12:17 (UTC)",
            "snippet": "Hello, Your verification code:252369.",
        },
        "important",
    ),
    (
        "alerta de Mercado Pago",
        {
            "sender_domain": "mercadopago.com",
            "subject": "Alerta de llave de acceso creada",
            "snippet": "Una llave de acceso fue creada para usarse como método de verificación.",
        },
        "important",
    ),
    (
        "postulación a Ripio",
        {
            "sender_domain": "ripio.teamtailor-mail.com",
            "subject": "Gracias por contactarte con nosotros! 🚀",
            "snippet": (
                "Te confirmamos que recibimos tu postulación para la posición de "
                "AI Automation Engineer."
            ),
        },
        "important",
    ),
]

# De los cuatro que salieron como "lo más importante" el 29/09, solo Banco Ciudad lo era.
_CASOS_29_09: list[tuple[str, dict[str, str | bool], Bucket]] = [
    (
        "postulación a Banco Ciudad",
        {
            "sender": "Equipo Talento - Banco Ciudad <no-reply@bancociudad.na.teamtailor-mail.com>",
            "sender_domain": "bancociudad.na.teamtailor-mail.com",
            "subject": "Recibimos tu postulación 💙",
            "snippet": (
                "¡Hola, Lorenzo! Gracias por postularte en Banco Ciudad. Ya recibimos tu perfil :)"
            ),
        },
        "important",
    ),
    (
        "alerta de Wellfound",
        {
            "sender_domain": "hi.wellfound.com",
            "subject": "New jobs: Lead Product Data Analyst at LawnStarter and 3 more jobs",
            "snippet": "Hi Lorenzo! I've found 4 new jobs that might interest you!",
        },
        "later",
    ),
    (
        "proyectos de Freelancer",
        {
            "sender_domain": "notifications.freelancer.com",
            "subject": (
                "Lorenzo, these Web Development, API Integration, and PHP projects and "
                "contests might interest you"
            ),
            "snippet": (
                "Hi Lorenzo, Here are the latest projects and contests matching your skills."
            ),
        },
        "later",
    ),
    (
        "newsletter de Gobierno Nacional",
        {
            "sender_domain": "comunicacion.argentina.gob.ar",
            "subject": "¿Sabés cómo prepararte ante El Niño?",
            "snippet": "Su Cliente de Mail NO soporta mensajes en formato HTML.",
        },
        "later",
    ),
    (
        # Solo el subdominio de comunicación masiva: un turno de otro gob.ar no se toca.
        "otro mail de gob.ar",
        {
            "sender_domain": "turnos.argentina.gob.ar",
            "subject": "Tu turno para el DNI",
            "snippet": "Te esperamos el lunes 5 a las 10:00.",
        },
        "important",
    ),
]


def _facts(fields: dict[str, str | bool]) -> MailFacts:
    return mail_facts(
        sender=str(fields.get("sender", "Alguien <alguien@ejemplo.com>")),
        sender_domain=str(fields.get("sender_domain", "ejemplo.com")),
        subject=str(fields.get("subject", "")),
        snippet=str(fields.get("snippet", "")),
        is_promotion=bool(fields.get("is_promotion", False)),
    )


@pytest.mark.parametrize(
    ("nombre", "fields", "expected"),
    _CASOS_23_09,
    ids=[c[0] for c in _CASOS_23_09],
)
def test_should_classify_real_mail_of_23_09_as_expected(
    nombre: str, fields: dict[str, str | bool], expected: Bucket
) -> None:
    assert classify_mail(_facts(fields)).bucket == expected


@pytest.mark.parametrize(
    ("nombre", "fields", "expected"),
    _CASOS_29_09,
    ids=[c[0] for c in _CASOS_29_09],
)
def test_should_classify_real_mail_of_29_09_as_expected(
    nombre: str, fields: dict[str, str | bool], expected: Bucket
) -> None:
    assert classify_mail(_facts(fields)).bucket == expected


def test_should_mark_hard_rules_as_locked() -> None:
    alerta = classify_mail(mail_facts(subject="Alerta de seguridad", snippet=""))
    assert alerta.locked is True
    newsletter = classify_mail(mail_facts(subject="Newsletter de octubre"))
    assert newsletter.locked is False


def test_should_keep_rules_order_when_checking_first_and_last() -> None:
    # El orden de RULES es semántico: la primera protege al digest, la última es
    # la red final de Gmail y va después de todas las `important`.
    assert RULES[0].reason == "es el propio digest — nunca se archiva"
    assert RULES[-1].reason == "Gmail lo puso en Promociones"
    last_important = max(i for i, r in enumerate(RULES) if r.bucket == "important")
    assert last_important < len(RULES) - 1
