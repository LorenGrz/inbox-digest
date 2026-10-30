from dataclasses import replace

from factories import classified

from inbox_digest.learn import (
    HIGH,
    IMPLICIT_WEIGHT,
    LOW,
    MIN_EXAMPLES_PER_CLASS,
    Example,
    apply_learning,
    features,
    is_ready,
    predict,
    train,
)
from inbox_digest.models import Bucket, Category


def example(
    *,
    sender: str = "Alguien <alguien@ejemplo.com>",
    sender_domain: str = "ejemplo.com",
    subject: str = "Hola",
    category: Category = "other",
    label: Bucket = "important",
    weight: float = 1,
) -> Example:
    return Example(sender, sender_domain, subject, category, label, weight)


def history() -> list[Example]:
    """Historia típica: te interesan las postulaciones, no el diario de Wellfound."""
    later = [
        example(
            sender="Wellfound <team@hi.wellfound.com>",
            sender_domain="hi.wellfound.com",
            subject=f"Jobs digest {i}: Data Analyst at Startup",
            label="later",
        )
        for i in range(6)
    ]
    important = [
        example(
            sender=f"Talento <no-reply@empresa{i}.teamtailor-mail.com>",
            sender_domain=f"empresa{i}.teamtailor-mail.com",
            subject="Recibimos tu postulación",
            category="application",
            label="important",
            weight=IMPLICIT_WEIGHT,
        )
        for i in range(6)
    ]
    return [*later, *important]


def test_should_include_sender_domain_category_and_normalized_words_in_features() -> None:
    f = features(example(subject="Recibimos tu Postulación 2026"))
    assert "from:alguien@ejemplo.com" in f
    assert "dom:ejemplo.com" in f
    assert "cat:other" in f
    assert "w:postulacion" in f
    assert "w:recibimos" in f


def test_should_drop_stopwords_short_words_and_numbers_from_features() -> None:
    f = features(example(subject="The jobs for you 2026 en BA"))
    assert "w:jobs" in f
    assert not {"w:the", "w:for", "w:you", "w:2026", "w:en", "w:ba"} & set(f)


def test_should_not_repeat_features() -> None:
    f = features(example(subject="jobs jobs jobs"))
    assert f.count("w:jobs") == 1


def test_should_count_examples_per_class_and_ignore_non_positive_weights() -> None:
    model = train([example(weight=0), example(label="later")])
    assert model.important.examples == 0
    assert model.later.examples == 1


def test_should_not_predict_when_no_feature_is_known() -> None:
    model = train(history())
    unseen = example(
        sender="x@nuevo.io", sender_domain="nuevo.io", subject="zzz", category="freelance"
    )
    assert predict(model, unseen) is None


def test_should_learn_that_a_repeatedly_flagged_sender_is_not_important() -> None:
    p = predict(
        train(history()),
        example(
            sender="Wellfound <team@hi.wellfound.com>",
            sender_domain="hi.wellfound.com",
            subject="Jobs digest: Backend at Acme",
        ),
    )
    assert p is not None
    assert p < LOW


def test_should_learn_that_applications_are_important() -> None:
    p = predict(
        train(history()),
        example(
            sender="Talento <no-reply@otra.teamtailor-mail.com>",
            sender_domain="otra.teamtailor-mail.com",
            subject="Recibimos tu postulación",
            category="application",
        ),
    )
    assert p is not None
    assert p > HIGH


WELLFOUND = classified(
    "Jobs digest: Backend at Acme",
    sender="Wellfound <team@hi.wellfound.com>",
    sender_domain="hi.wellfound.com",
)


def test_should_not_decide_anything_when_model_is_cold() -> None:
    few = [e for e in history() if e.label == "later"][:MIN_EXAMPLES_PER_CLASS]
    model = train(few)
    assert is_ready(model) is False
    assert apply_learning(WELLFOUND, model) == WELLFOUND


def test_should_return_mail_untouched_when_there_is_no_model() -> None:
    assert apply_learning(WELLFOUND, None) is WELLFOUND


def test_should_move_to_later_and_explain_when_evidence_is_strong() -> None:
    out = apply_learning(WELLFOUND, train(history()))
    assert out.bucket == "later"
    assert "aprendido de tus clicks" in out.reason
    assert out.score is not None
    assert out.score < LOW


def test_should_rescue_to_main_when_rule_was_archiving_it() -> None:
    out = apply_learning(
        classified(
            "Recibimos tu postulación",
            sender="Talento <no-reply@otra.teamtailor-mail.com>",
            sender_domain="otra.teamtailor-mail.com",
            category="application",
            bucket="later",
        ),
        train(history()),
    )
    assert out.bucket == "important"


def test_should_never_override_a_hard_rule() -> None:
    locked = replace(WELLFOUND, locked=True)
    assert apply_learning(locked, train(history())) is locked


def test_should_keep_rule_decision_when_evidence_is_in_the_doubt_zone() -> None:
    # Un solo ejemplo de cada lado con el mismo asunto: no hay evidencia fuerte.
    examples = [
        *history(),
        example(sender="a@mix.com", sender_domain="mix.com", subject="Mixto", label="later"),
        example(sender="a@mix.com", sender_domain="mix.com", subject="Mixto", label="important"),
    ]
    out = apply_learning(
        classified("Mixto", sender="a@mix.com", sender_domain="mix.com"), train(examples)
    )
    assert out.bucket == "important"
    assert out.score is not None
    assert LOW <= out.score <= HIGH
