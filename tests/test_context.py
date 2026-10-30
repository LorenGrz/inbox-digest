from datetime import UTC, datetime

from factories import art, classified, event

from inbox_digest.context import (
    ApplicationRef,
    classify_event,
    due_reminders,
    parse_application,
    relative_time,
    reminder_offsets,
)
from inbox_digest.timeutil import long_date_es, overlaps_day

SEP_24 = art(2026, 9, 24, 9, 30)


def test_should_include_multi_day_event_when_it_started_before_today() -> None:
    # Nerdearla 22–26
    nerdearla = event(start=art(2026, 9, 22, 9), end=art(2026, 9, 26, 19), days_away=-2)
    assert overlaps_day(nerdearla, SEP_24) is True


def test_should_include_event_when_it_starts_today() -> None:
    assert overlaps_day(event(start=art(2026, 9, 24, 11), end=art(2026, 9, 24, 12)), SEP_24)


def test_should_exclude_event_when_it_already_ended() -> None:
    assert not overlaps_day(event(start=art(2026, 9, 20, 11), end=art(2026, 9, 21, 12)), SEP_24)


def test_should_exclude_event_when_it_has_not_started() -> None:
    assert not overlaps_day(event(start=art(2026, 9, 26, 11), end=art(2026, 9, 26, 12)), SEP_24)


def test_should_recognize_interviews_by_title() -> None:
    assert classify_event("Entrevista con RRHH") == "interview"


def test_should_recognize_defenses() -> None:
    assert classify_event("Defensa de tesis") == "defense"


def test_should_recognize_meetups() -> None:
    assert classify_event("Meetup de Python") == "meetup"


def test_should_treat_event_with_external_guests_as_interview() -> None:
    assert classify_event("Sync", ("baldecash.com",)) == "interview"


def test_should_treat_own_event_without_keywords_as_generic() -> None:
    assert classify_event("Gimnasio", ("gmail.com",)) == "generic"


def test_should_stagger_interviews_at_t7_t3_t1_t0() -> None:
    assert reminder_offsets("interview") == [7, 3, 1, 0]


def test_should_remind_meetups_only_from_t1() -> None:
    assert reminder_offsets("meetup") == [1, 0]


def test_should_fire_reminder_when_offset_matches_exactly() -> None:
    due = due_reminders([event(kind="interview", days_away=7)], set())
    assert len(due) == 1
    assert due[0].key == "e1@7"


def test_should_not_fire_reminder_on_an_intermediate_day() -> None:
    assert due_reminders([event(kind="interview", days_away=5)], set()) == []


def test_should_not_repeat_reminder_when_already_sent() -> None:
    assert due_reminders([event(kind="interview", days_away=7)], {"e1@7"}) == []


def test_should_ignore_past_events_when_computing_reminders() -> None:
    assert due_reminders([event(kind="interview", days_away=-1)], set()) == []


def test_should_extract_company_and_role_from_subject() -> None:
    result = parse_application(
        classified(
            "Recibimos tu postulación para Backend Developer",
            category="application",
            sender_domain="teamtailor.com",
        )
    )
    assert result == ApplicationRef(company="teamtailor", role="Backend Developer")


def test_should_return_none_when_mail_is_not_an_application() -> None:
    assert parse_application(classified(category="marketing")) is None


NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


def test_should_format_minutes_when_less_than_an_hour_ago() -> None:
    assert relative_time(datetime(2026, 9, 25, 11, 35, tzinfo=UTC), NOW) == "hace 25 min"


def test_should_format_hours_when_less_than_a_day_ago() -> None:
    assert relative_time(datetime(2026, 9, 25, 9, 0, tzinfo=UTC), NOW) == "hace 3 h"


def test_should_say_yesterday_when_one_day_ago() -> None:
    assert relative_time(datetime(2026, 9, 24, 9, 0, tzinfo=UTC), NOW) == "ayer"


def test_should_format_days_when_more_than_a_day_ago() -> None:
    assert relative_time(datetime(2026, 9, 22, 9, 0, tzinfo=UTC), NOW) == "hace 3 d"


def test_should_say_just_now_when_under_a_minute_ago() -> None:
    assert relative_time(datetime(2026, 9, 25, 11, 59, 50, tzinfo=UTC), NOW) == "recién"


def test_should_format_long_date_in_spanish_not_english() -> None:
    assert long_date_es(datetime(2026, 9, 24, 12, tzinfo=UTC)) == "jueves 24 de septiembre de 2026"


def test_should_map_sunday_correctly() -> None:
    assert long_date_es(datetime(2026, 9, 27, 12, tzinfo=UTC)) == "domingo 27 de septiembre de 2026"


def test_should_map_monday_correctly() -> None:
    assert long_date_es(datetime(2026, 9, 28, 12, tzinfo=UTC)) == "lunes 28 de septiembre de 2026"


def test_should_map_saturday_correctly() -> None:
    assert long_date_es(datetime(2026, 9, 26, 12, tzinfo=UTC)) == "sábado 26 de septiembre de 2026"


def test_should_use_correct_month_at_year_edges() -> None:
    assert long_date_es(datetime(2026, 1, 1, 12, tzinfo=UTC)) == "jueves 1 de enero de 2026"
    assert long_date_es(datetime(2026, 12, 31, 12, tzinfo=UTC)) == "jueves 31 de diciembre de 2026"


def test_should_use_local_day_when_utc_is_already_next_day() -> None:
    # 01:00 UTC del 25 es todavía el 24 a las 22:00 en ART.
    assert long_date_es(datetime(2026, 9, 25, 1, tzinfo=UTC)) == "jueves 24 de septiembre de 2026"
