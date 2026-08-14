from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from doutrinador.application.ports import SearchResult
from doutrinador.domain import Document, Passage
from doutrinador.domain.text import normalize, tokens

# A normalização conceitual não injeta conhecimento factual. Ela aproxima
# formulações linguísticas usuais antes do cálculo vetorial local.
CONCEPTS = {
    "livre_arbitrio": {"livre", "arbitrio", "liberdade", "escolha", "escolhas", "decisao", "decisoes"},
    "caridade": {"caridade", "auxilio", "ajuda", "amparo", "assistencia"},
    "humildade": {"humildade", "humilde", "modestia"},
    "responsabilidade": {"responsabilidade", "responsavel", "consequencia", "consequencias"},
    "conduta": {"conduta", "comportamento", "atitude", "atitudes", "pratica"},
}


def hybrid_search(
    question: str,
    items: Sequence[tuple[Document, Passage]],
    limit: int = 5,
    minimum_score: float = 0.2,
) -> list[SearchResult]:
    """Combina BM25 lexical e similaridade semântica vetorial local."""

    query_tokens = tokens(question)
    if not query_tokens or not items:
        return []

    corpus_tokens = [tokens(passage.text) for _, passage in items]
    document_frequency = Counter()
    for words in corpus_tokens:
        document_frequency.update(set(words))
    average_length = sum(map(len, corpus_tokens)) / max(len(corpus_tokens), 1)
    lexical = [
        _bm25(query_tokens, words, document_frequency, len(items), average_length)
        for words in corpus_tokens
    ]
    query_vector = _semantic_vector(question)
    semantic = [_cosine(query_vector, _semantic_vector(passage.text)) for _, passage in items]
    max_lexical = max(lexical, default=0.0)

    ranked: list[SearchResult] = []
    precedence = {"A": 1.0, "B": 0.92, "C": 0.82, "D": 0.68}
    for index, (document, passage) in enumerate(items):
        lexical_score = lexical[index] / max_lexical if max_lexical else 0.0
        semantic_score = semantic[index]
        # A precedência influencia, mas nunca cria relevância sem correspondência.
        relevance = 0.58 * lexical_score + 0.42 * semantic_score
        score = relevance * precedence[document.source_level.value]
        if relevance >= minimum_score and (lexical_score > 0 or semantic_score >= 0.28):
            ranked.append(SearchResult(
                document=document,
                passage=passage,
                score=score,
                lexical_score=lexical_score,
                semantic_score=semantic_score,
            ))

    ranked.sort(key=lambda result: (result.score, result.lexical_score), reverse=True)
    selected: list[SearchResult] = []
    per_document: Counter[str] = Counter()
    for result in ranked:
        if per_document[result.document.id] >= 2:
            continue
        selected.append(result)
        per_document[result.document.id] += 1
        if len(selected) >= limit:
            break
    return selected


def _bm25(
    query: Sequence[str], document: Sequence[str], frequencies: Counter, corpus_size: int,
    average_length: float, k1: float = 1.5, b: float = 0.75,
) -> float:
    counts = Counter(document)
    score = 0.0
    for term in set(query):
        frequency = counts[term]
        if not frequency:
            continue
        inverse_frequency = math.log(1 + (corpus_size - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
        denominator = frequency + k1 * (1 - b + b * len(document) / max(average_length, 1))
        score += inverse_frequency * (frequency * (k1 + 1)) / denominator
    return score


def _semantic_vector(text: str) -> Counter[str]:
    words = tokens(text)
    vector: Counter[str] = Counter()
    for word in words:
        stem = word[:6] if len(word) > 6 else word
        vector[f"term:{stem}"] += 1.0
        for concept, members in CONCEPTS.items():
            if word in members:
                vector[f"concept:{concept}"] += 1.8
    # Trigramas tornam a representação resistente a flexões sem depender de
    # serviço externo; sinais conceituais acima permitem busca por sinônimos.
    for word in set(words):
        padded = f"^{word}$"
        for index in range(len(padded) - 2):
            vector[f"tri:{padded[index:index + 3]}"] += 0.08
    return vector


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(value * right[key] for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0
