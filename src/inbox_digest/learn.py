"""Lo que el bot aprende de tus clicks en "No es importante" (hoy, la etiqueta
`No importante`). Naive Bayes multinomial sobre remitente, dominio, categoría y
palabras del asunto.

Funciones puras, sin Google: los ejemplos salen del Sheet y el modelo se
reentrena en cada corrida. Con decenas o cientos de ejemplos es instantáneo, y
así no hay un estado derivado que se desincronice del Sheet cuando corregís una
fila a mano.

Orden de decisión: reglas duras (`locked`) → Naive Bayes, solo si está seguro →
lo que haya dicho la regla. Ante la duda, gana el default conservador.
"""

import math
import re
from dataclasses import dataclass, field, replace
from typing import Protocol

from inbox_digest.models import Bucket, Category, Classified
from inbox_digest.rules import domain_of, normalize_text

# Un click explícito pesa 1; un mail mostrado y no apretado, esto.
IMPLICIT_WEIGHT = 0.5

# Cuántos ejemplos de cada clase hacen falta antes de dejarlo decidir.
MIN_EXAMPLES_PER_CLASS = 5

# Por debajo de LOW se archiva; por encima de HIGH se rescata a Principal.
LOW = 0.15
HIGH = 0.85


class HasFeatures(Protocol):
    """Lo que `features` necesita de un mail; lo cumplen `Example` y `Classified`."""

    @property
    def sender(self) -> str: ...
    @property
    def sender_domain(self) -> str: ...
    @property
    def subject(self) -> str: ...
    @property
    def category(self) -> Category: ...


@dataclass(frozen=True)
class Example:
    sender: str
    sender_domain: str
    subject: str
    category: Category
    label: Bucket
    weight: float


@dataclass
class ClassStats:
    # Cantidad de ejemplos (sin ponderar), para el arranque en frío.
    examples: int = 0
    # Suma de pesos: el prior.
    weight: float = 0.0
    # Masa total de features, ponderada.
    mass: float = 0.0
    counts: dict[str, float] = field(default_factory=dict)


@dataclass
class LearnedModel:
    important: ClassStats = field(default_factory=ClassStats)
    later: ClassStats = field(default_factory=ClassStats)
    vocabulary: set[str] = field(default_factory=set)


_STOPWORDS = frozenset(
    [
        # castellano
        "del",
        "las",
        "los",
        "por",
        "para",
        "con",
        "una",
        "que",
        "tus",
        "sus",
        "mas",
        "como",
        "este",
        "esta",
        "hoy",
        "nos",
        "hay",
        "pero",
        "sin",
        "sobre",
        "vos",
        "tenes",
        # inglés
        "the",
        "and",
        "for",
        "you",
        "your",
        "with",
        "from",
        "this",
        "that",
        "are",
        "our",
        "has",
        "new",
        "more",
        "now",
    ]
)


def _address_of(sender: str) -> str:
    match = re.search(r"<?([^<>\s]+@[^<>\s]+?)>?\s*$", sender.strip())
    return (match.group(1) if match else sender).lower()


def features(mail: HasFeatures) -> list[str]:
    """Features de un mail. El asunto se tokeniza normalizado y sin repetir: en un
    asunto, que una palabra aparezca dos veces no la hace más relevante.
    """
    domain = mail.sender_domain or domain_of(mail.sender)
    tokens = [
        t
        for t in re.split(r"[^a-z0-9ñ]+", normalize_text(mail.subject))
        if len(t) >= 3 and t not in _STOPWORDS and not re.fullmatch(r"[0-9]+", t)
    ]
    out = [f"from:{_address_of(mail.sender)}", f"cat:{mail.category}", *(f"w:{t}" for t in tokens)]
    if domain:
        out.append(f"dom:{domain}")
    # dict.fromkeys deduplica conservando el orden, como `new Set` en el original.
    return list(dict.fromkeys(out))


def train(examples: list[Example]) -> LearnedModel:
    model = LearnedModel()
    for example in examples:
        if not example.weight > 0:
            continue
        stats = model.important if example.label == "important" else model.later
        stats.examples += 1
        stats.weight += example.weight
        for feature in features(example):
            stats.counts[feature] = stats.counts.get(feature, 0.0) + example.weight
            stats.mass += example.weight
            model.vocabulary.add(feature)
    return model


def is_ready(model: LearnedModel) -> bool:
    return (
        model.important.examples >= MIN_EXAMPLES_PER_CLASS
        and model.later.examples >= MIN_EXAMPLES_PER_CLASS
    )


def predict(model: LearnedModel, mail: HasFeatures) -> float | None:
    """P(importante | mail), con suavizado de Laplace y en log-odds para no perder
    precisión al multiplicar muchas probabilidades chicas.

    Las features que nunca se vieron se ignoran: sumarlas solo empuja hacia la
    clase con menos masa, sin aportar evidencia. Sin ninguna feature conocida
    devuelve None — no hay nada sobre lo que opinar.
    """
    known = [f for f in features(mail) if f in model.vocabulary]
    if not known:
        return None

    size = len(model.vocabulary)
    yes, no = model.important, model.later
    log_odds = math.log((yes.weight + 1) / (no.weight + 1))
    for feature in known:
        p_yes = (yes.counts.get(feature, 0.0) + 1) / (yes.mass + size)
        p_no = (no.counts.get(feature, 0.0) + 1) / (no.mass + size)
        log_odds += math.log(p_yes / p_no)
    try:
        return 1 / (1 + math.exp(-log_odds))
    except OverflowError:
        # exp() de un número enorme revienta en Python; en JS daba Infinity → 0.
        return 0.0


def apply_learning(mail: Classified, model: LearnedModel | None) -> Classified:
    """Aplica lo aprendido sobre la decisión de las reglas.

    Solo cambia el bucket con mucha confianza (fuera de [LOW, HIGH]); en el medio
    se queda lo que dijo la regla. Las reglas duras nunca se tocan.
    """
    if model is None or mail.locked or not is_ready(model):
        return mail
    score = predict(model, mail)
    if score is None:
        return mail

    # Math.round del original redondea .5 hacia arriba; round() de Python, al par.
    pct = math.floor(score * 100 + 0.5)
    reason = f"aprendido de tus clicks ({pct}% importante)"
    if score < LOW and mail.bucket != "later":
        return replace(mail, bucket="later", score=score, reason=reason)
    if score > HIGH and mail.bucket != "important":
        return replace(mail, bucket="important", score=score, reason=reason)
    return replace(mail, score=score)
