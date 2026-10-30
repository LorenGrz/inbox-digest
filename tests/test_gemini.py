import json
from dataclasses import replace

from factories import art, classified, digest, event

from inbox_digest.gemini import (
    MAX_HIGHLIGHTS,
    backoff_ms,
    build_payload,
    parse_ai_summary,
    sanitize_text,
    thinking_config,
)
from inbox_digest.models import AiGroup, AiItem, AiSummary
from inbox_digest.render import groups_with_rest, highlight_indexes, render_digest


def dumps(value: object) -> str:
    return json.dumps(value)


def parsed(value: object, mail_count: int) -> AiSummary:
    out = parse_ai_summary(dumps(value), mail_count)
    assert out is not None
    return out


# parse_ai_summary: la salida del modelo es dato hostil


def test_should_drop_indexes_when_out_of_range() -> None:
    out = parsed(
        {"summary": "ok", "groups": [{"title": "A", "items": [{"index": 9}, {"index": 0}]}]}, 1
    )
    assert [i.index for i in out.groups[0].items] == [0]


def test_should_drop_indexes_when_not_integers() -> None:
    out = parsed(
        {"summary": "ok", "groups": [{"title": "A", "items": [{"index": 1.5}, {"index": "0"}]}]},
        3,
    )
    assert out.groups == []


def test_should_not_let_a_mail_appear_in_two_groups() -> None:
    out = parsed(
        {
            "summary": "ok",
            "groups": [
                {"title": "A", "items": [{"index": 0}]},
                {"title": "B", "items": [{"index": 0}]},
            ],
        },
        1,
    )
    assert len(out.groups) == 1


def test_should_strip_urls_from_notes() -> None:
    out = parsed(
        {
            "summary": "ok",
            "groups": [
                {
                    "title": "A",
                    "items": [{"index": 0, "note": "entrá a https://evil.test/phish ya"}],
                }
            ],
        },
        1,
    )
    note = out.groups[0].items[0].note
    assert "evil.test" not in note
    assert "http" not in note


def test_should_strip_javascript_and_data_schemes() -> None:
    out = parsed({"summary": "mirá javascript:alert(1) y data:text/html,x", "groups": []}, 0)
    assert "javascript:" not in out.summary
    assert "data:" not in out.summary


def test_should_strip_html_tags_from_group_title() -> None:
    out = parsed(
        {
            "summary": "ok",
            "groups": [{"title": "<img src=x onerror=alert(1)>Urgente", "items": [{"index": 0}]}],
        },
        1,
    )
    assert out.groups[0].title == "Urgente"


def test_should_truncate_oversized_text() -> None:
    out = parsed({"summary": "x" * 5000, "groups": []}, 0)
    assert len(out.summary) <= 1200


def test_should_return_none_when_json_is_invalid() -> None:
    assert parse_ai_summary("no soy json", 3) is None


def test_should_return_none_when_summary_is_missing() -> None:
    assert parse_ai_summary(dumps({"groups": []}), 3) is None


def test_should_return_none_when_response_is_not_an_object() -> None:
    assert parse_ai_summary(dumps(["summary"]), 3) is None


def test_should_skip_malformed_groups_instead_of_failing_the_whole_summary() -> None:
    out = parsed(
        {"summary": "ok", "groups": ["basura", 3, {"title": "A", "items": [{"index": 0}]}]}, 1
    )
    assert [g.title for g in out.groups] == ["A"]


# sanitize_text


def test_should_strip_url_glued_to_a_word() -> None:
    # Regresión: con \b antes del esquema, un URL pegado a una palabra sobrevivía.
    assert "evil.test" not in sanitize_text("entrá a clickhttps://evil.test ya", 200)


def test_should_strip_urls_glued_to_digits_and_underscore() -> None:
    assert "evil.test" not in sanitize_text("911https://evil.test", 200)
    assert "evil.test" not in sanitize_text("_https://evil.test", 200)


def test_should_strip_links_without_scheme() -> None:
    assert "evil.test" not in sanitize_text("mirá www.evil.test/x", 200)


def test_should_strip_vbscript_and_file_schemes() -> None:
    assert sanitize_text("vbscript:msgbox(1) file:///etc/passwd", 200) == ""


def test_should_leave_normal_text_intact() -> None:
    assert sanitize_text("  Streambe  te   bajó ", 200) == "Streambe te bajó"


def test_should_flatten_line_breaks_by_default() -> None:
    assert sanitize_text("uno\n\ndos", 200) == "uno dos"


def test_should_keep_paragraphs_when_keep_breaks_is_set() -> None:
    assert sanitize_text("uno\n\ndos", 200, keep_breaks=True) == "uno\n\ndos"


def test_should_collapse_three_or_more_breaks_and_clean_spaces_when_keep_breaks() -> None:
    assert sanitize_text("uno\n\n\n\n  dos   tres", 200, keep_breaks=True) == "uno\n\ndos tres"


def test_should_still_strip_urls_when_keep_breaks() -> None:
    assert "evil.test" not in sanitize_text("uno\nvisitá https://evil.test", 200, keep_breaks=True)


def test_should_return_empty_when_value_is_not_a_string() -> None:
    assert sanitize_text(42, 200) == ""


# backoff_ms


def test_should_honor_retry_after_when_present() -> None:
    assert backoff_ms(1, "7") == 7000


def test_should_cap_absurd_retry_after_at_30_seconds() -> None:
    assert backoff_ms(1, "99999") == 30_000


def test_should_ignore_non_numeric_retry_after_and_use_exponential_backoff() -> None:
    wait = backoff_ms(2, "Wed, 21 Oct 2026 07:28:00 GMT")
    assert 2000 <= wait < 2600


def test_should_ignore_infinite_retry_after() -> None:
    assert backoff_ms(1, "inf") < 2000


def test_should_grow_with_the_attempt() -> None:
    assert backoff_ms(3, None) >= 4000


# groups_with_rest: ningún mail se pierde


def test_should_add_mails_the_model_omitted() -> None:
    model = digest(
        important=[classified("uno"), classified("dos"), classified("tres")],
        ai=AiSummary("", [AiGroup("A", [AiItem(1, "")])], []),
    )
    groups = groups_with_rest(model)
    assert sorted(i.index for g in groups for i in g.items) == [0, 1, 2]
    assert groups[1].title == "Lo demás"


def test_should_build_a_single_group_when_there_is_no_ai() -> None:
    groups = groups_with_rest(digest(important=[classified("uno"), classified("dos")]))
    assert len(groups) == 1
    assert len(groups[0].items) == 2


def test_should_not_add_leftover_group_when_model_covered_everything() -> None:
    model = digest(
        important=[classified("uno")],
        ai=AiSummary("", [AiGroup("A", [AiItem(0, "")])], []),
    )
    assert len(groups_with_rest(model)) == 1


# render: escapado en el sink


def test_should_escape_subject_with_html_injection() -> None:
    html = render_digest(digest(important=[classified("<script>alert(1)</script> Oferta")]))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_should_use_the_real_permalink_not_one_from_the_model() -> None:
    html = render_digest(
        digest(
            important=[classified("uno", permalink="https://mail.google.com/real")],
            ai=AiSummary("", [AiGroup("A", [AiItem(0, "nota")])], [0]),
        )
    )
    assert "https://mail.google.com/real" in html
    assert "evil" not in html


def test_should_escape_quotes_in_subject_so_href_is_not_broken() -> None:
    html = render_digest(digest(important=[classified('a" onmouseover="alert(1)')]))
    assert 'onmouseover="alert' not in html


# highlight_indexes: quién decide qué se muestra


def test_should_respect_the_order_given_by_the_model() -> None:
    model = digest(
        important=[classified("a"), classified("b"), classified("c")],
        ai=AiSummary("", [], [2, 0]),
    )
    assert highlight_indexes(model) == [2, 0]


def test_should_fall_back_to_category_order_when_there_is_no_ai() -> None:
    model = digest(
        important=[
            classified("promo", category="marketing"),
            classified("alerta", category="account"),
            classified("postulación", category="application"),
        ]
    )
    # account (0) < application (4) < marketing (9)
    assert highlight_indexes(model) == [1, 2, 0]


def test_should_not_show_more_than_max_highlights_when_there_is_no_ai() -> None:
    model = digest(important=[classified(f"m{i}", category="account") for i in range(10)])
    assert len(highlight_indexes(model)) == MAX_HIGHLIGHTS


def test_should_fall_back_to_rules_when_model_highlights_nothing() -> None:
    model = digest(important=[classified("a", category="account")], ai=AiSummary("x", [], []))
    assert highlight_indexes(model) == [0]


def test_should_prefer_learned_score_over_category_when_there_is_no_ai() -> None:
    model = digest(
        important=[
            classified("cuenta", category="account", score=0.2),
            classified("promo", category="marketing", score=0.9),
        ]
    )
    assert highlight_indexes(model) == [1, 0]


# parse_ai_summary: highlights


def test_should_drop_out_of_range_highlights() -> None:
    out = parsed({"summary": "ok", "groups": [], "highlights": [0, 99, -1]}, 2)
    assert out.highlights == [0]


def test_should_not_repeat_highlights() -> None:
    out = parsed({"summary": "ok", "groups": [], "highlights": [1, 1, 0]}, 2)
    assert out.highlights == [1, 0]


def test_should_cut_highlights_at_max_highlights() -> None:
    out = parsed({"summary": "ok", "groups": [], "highlights": [0, 1, 2, 3, 4, 5]}, 10)
    assert len(out.highlights) == MAX_HIGHLIGHTS


def test_should_drop_non_integer_highlights() -> None:
    out = parsed({"summary": "ok", "groups": [], "highlights": [True, "1", 1.5, 0]}, 3)
    assert out.highlights == [0]


# el mail muestra pocas tarjetas y cuenta el resto


def test_should_not_render_mails_that_are_not_highlighted() -> None:
    model = digest(
        important=[classified("destacado"), classified("escondido")],
        ai=AiSummary("x", [], [0]),
    )
    html = render_digest(model)
    assert "destacado" in html
    assert "escondido" not in html


def test_should_say_how_many_mails_were_left_out() -> None:
    model = digest(
        important=[classified("uno"), classified("dos", category="marketing"), classified("tres")],
        ai=AiSummary("x", [], [0]),
    )
    assert "2 mail(s) importantes más" in render_digest(model)


# thinking_config


def test_should_nest_thinking_level_inside_thinking_config_for_3x_models() -> None:
    assert thinking_config("gemini-3.5-flash") == {"thinkingConfig": {"thinkingLevel": "low"}}


def test_should_not_send_thinking_config_to_2_5_models() -> None:
    assert thinking_config("gemini-2.5-flash") == {}


# build_payload: horarios para el modelo


MEETUP = event(
    "OWASP Meetup",
    id="e1",
    start=art(2026, 10, 29, 18, 30),
    end=art(2026, 10, 29, 21, 30),
    location="Honduras 5296",
    kind="meetup",
    days_away=0,
)


def test_should_send_formatted_local_time_and_never_the_utc_iso() -> None:
    payload = build_payload(digest(today=[MEETUP], upcoming=[replace(MEETUP, days_away=1)]))
    assert '"horario":"18:30–21:30"' in payload
    assert '"lugar":"Honduras 5296"' in payload
    # Ni el ISO local ni su equivalente en UTC (21:30Z para un evento de 18:30).
    assert MEETUP.start.isoformat() not in payload
    assert MEETUP.end.isoformat() not in payload
    assert "21:30:00" not in payload
    assert "T18:30" not in payload


def test_should_send_only_domain_and_short_snippet_never_permalink() -> None:
    long_snippet = "y" * 500
    payload = build_payload(
        digest(
            important=[
                classified(
                    "Asunto",
                    sender="Alguien <alguien@ejemplo.com>",
                    snippet=long_snippet,
                    permalink="https://mail.google.com/secreto",
                )
            ]
        )
    )
    assert '"de":"ejemplo.com"' in payload
    assert "y" * 200 in payload
    assert "y" * 201 not in payload
    assert "alguien@ejemplo.com" not in payload
    assert "secreto" not in payload
