from datetime import datetime

from factories import art, classified, digest, event

from inbox_digest.config import FEEDBACK_LABEL, TIMEZONE
from inbox_digest.render import render_digest, rule_summary
from inbox_digest.types import AiSummary, Classified, Reminder

# El 29/09 del mail real, en ART. CORDOBA es un viaje de varios días, como en el
# calendario real.
TODAY = [
    event("CORDOBA", start=art(2026, 9, 29, 13), end=art(2026, 10, 2, 14)),
    event("ESTADISTICA", start=art(2026, 9, 29, 18), end=art(2026, 9, 29, 22)),
    event("TUTOR ALGORITMOS", start=art(2026, 9, 29, 18), end=art(2026, 9, 29, 19)),
]

BANCO = "Equipo Talento - Banco Ciudad <no-reply@bancociudad.com>"


def banco_mail(subject: str) -> Classified:
    return classified(
        subject,
        sender=BANCO,
        sender_domain="bancociudad.com",
        category="application",
        permalink="https://mail.google.com/real",
    )


def test_should_count_agenda_and_warn_when_two_events_overlap() -> None:
    text = rule_summary(digest(today=TODAY))
    assert "Hoy tenés 3 evento(s)" in text
    assert "CORDOBA (29/09 13:00 → 2/10 14:00)" in text
    assert "ESTADISTICA (18:00–22:00)" in text
    # Un viaje de varios días no "se pisa" con las clases: solo el choque real.
    assert "se pisan ESTADISTICA y TUTOR ALGORITMOS." in text
    assert "CORDOBA y" not in text


def test_should_name_mails_to_look_at_with_subject_and_sender() -> None:
    mail = classified(
        "Recibimos tu postulación",
        sender=BANCO,
        sender_domain="bancociudad.com",
        category="application",
    )
    text = rule_summary(digest(important=[mail]))
    assert "«Recibimos tu postulación» de Equipo Talento - Banco Ciudad" in text


def test_should_say_so_when_there_are_no_events_nor_mails() -> None:
    text = rule_summary(digest())
    assert "Hoy no tenés nada en la agenda." in text
    assert "no hay nada que pida tu atención" in text


def test_should_only_mention_what_is_coming_not_what_is_today() -> None:
    text = rule_summary(
        digest(
            reminders=[
                Reminder("a", "CORDOBA", 0, "a@0"),
                Reminder("b", "Entrevista Ripio", 3, "b@3"),
            ]
        )
    )
    assert "Se viene: Entrevista Ripio en 3 día(s)." in text
    assert "CORDOBA en" not in text


def test_should_show_summary_block_without_ai_and_flag_it_in_the_footer() -> None:
    html = render_digest(digest(today=TODAY))
    assert "Tu día en breve" in html
    assert "resumen sin IA" in html


def test_should_use_the_model_summary_when_ai_is_present() -> None:
    html = render_digest(digest(ai=AiSummary("Resumen de Gemini", [], [])))
    assert "Resumen de Gemini" in html
    assert "resumen sin IA" not in html


def test_should_not_have_the_rest_nor_deadlines_sections() -> None:
    html = render_digest(digest(important=[classified("x")]))
    assert "El resto" not in html
    assert "Deadlines" not in html


def test_should_not_repeat_todays_events_in_coming_section() -> None:
    html = render_digest(digest(reminders=[Reminder("a", "CORDOBA", 0, "a@0")]))
    assert "Se viene" not in html
    assert "Hoy: CORDOBA" not in html


def test_should_have_no_dismiss_button_but_explain_the_feedback_label() -> None:
    # Sin web app no hay botón: el feedback es la etiqueta de Gmail.
    html = render_digest(digest(important=[classified("x")]))
    assert "No es importante" not in html
    assert f"«{FEEDBACK_LABEL}»" in html
    assert "Ponele la etiqueta" in html


def test_should_link_each_card_to_its_permalink() -> None:
    mail = banco_mail("Recibimos tu postulación")
    html = render_digest(digest(important=[mail]))
    assert html.count('href="https://mail.google.com/real"') == 2  # asunto y "Abrir"


def test_should_render_local_time_in_the_footer() -> None:
    html = render_digest(digest(), now=datetime(2026, 9, 29, 9, 30, tzinfo=TIMEZONE))
    assert "generado 09:30" in html
