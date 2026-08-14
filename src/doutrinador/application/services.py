from __future__ import annotations

import re
from dataclasses import replace

from doutrinador.application.ports import (
    AnswerGenerator,
    DocumentRepository,
    InteractionLogger,
    KnowledgeRetriever,
)
from doutrinador.constitution import DOUTRINADOR_CONSTITUTION
from doutrinador.domain import Answer, Citation, Document, validate_image_url
from doutrinador.domain.text import tokens


INSUFFICIENT_EVIDENCE = (
    "Não encontrei fundamento suficiente nas fontes doutrinárias disponíveis "
    "para responder a essa questão com segurança."
)


class RegisterDocument:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    def execute(self, document: Document) -> Document:
        self._repository.add(document)
        return document


class UpdateDocumentMetadata:
    EDITABLE_FIELDS = {
        "title", "author", "source_level", "year", "edition", "origin",
        "provenance_note", "authenticity_status", "rights_status",
        "image_url", "image_description",
    }

    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    def execute(
        self, document_id: str, changes: dict, responsible: str, justification: str
    ) -> Document:
        if not responsible.strip():
            raise ValueError("O responsável pela alteração é obrigatório.")
        if len(justification.strip()) < 5:
            raise ValueError("Informe uma justificativa com pelo menos cinco caracteres.")
        invalid = set(changes) - self.EDITABLE_FIELDS
        if invalid:
            raise ValueError(f"Metadados não editáveis: {', '.join(sorted(invalid))}.")
        if not changes:
            raise ValueError("Informe ao menos um metadado para alterar.")
        if "image_url" in changes:
            changes["image_url"] = validate_image_url(changes["image_url"])
        return self._repository.update_metadata(
            document_id, changes, responsible.strip(), justification.strip()
        )


class AskDoutrinador:
    def __init__(
        self,
        retriever: KnowledgeRetriever,
        generator: AnswerGenerator | None = None,
        logger: InteractionLogger | None = None,
    ) -> None:
        if generator is None:
            from doutrinador.infrastructure.llm import ExtractiveAnswerGenerator
            generator = ExtractiveAnswerGenerator()
        self._retriever = retriever
        self._generator = generator
        self._logger = logger

    def execute(self, question: str) -> Answer:
        question = question.strip()
        if len(question) < 3:
            raise ValueError("A pergunta deve possuir ao menos três caracteres.")
        results = self._retriever.search(question, limit=5)
        if not results:
            return self._finish(
                question, results,
                Answer(INSUFFICIENT_EVIDENCE, (), False, "Ausência de evidência no acervo atual."),
            )

        citations = tuple(
            Citation(
                passage_id=item.passage.id,
                document_id=item.document.id,
                title=item.document.title,
                author=item.document.author,
                source_level=item.document.source_level,
                excerpt=item.passage.text,
                section=item.passage.section,
                page=item.passage.page,
                source_url=f"/passages/{item.passage.id}",
                image_url=item.document.image_url,
                image_description=item.document.image_description,
            )
            for item in results
        )
        try:
            generated = self._generator.generate(
                question, results, DOUTRINADOR_CONSTITUTION
            ).strip()
            if generated == INSUFFICIENT_EVIDENCE:
                answer = Answer(
                    INSUFFICIENT_EVIDENCE, (), False,
                    "O gerador avaliou que os trechos recuperados não sustentam uma resposta.",
                )
            elif not _has_verified_grounding(generated, results):
                answer = Answer(
                    INSUFFICIENT_EVIDENCE, (), False,
                    "A resposta gerada foi rejeitada pela verificação de citações.",
                )
            else:
                used = {int(value) for value in re.findall(r"\[P(\d+)]", generated)}
                answer = Answer(
                    generated,
                    tuple(citation for index, citation in enumerate(citations, start=1) if index in used),
                    True,
                    "Resposta gerada exclusivamente a partir dos trechos recuperados; citações verificadas.",
                )
        except Exception as exc:
            answer = Answer(
                INSUFFICIENT_EVIDENCE, (), False,
                f"Falha segura na geração: {type(exc).__name__}.",
            )
        return self._finish(question, results, answer)

    def _finish(self, question: str, results: list, answer: Answer) -> Answer:
        if self._logger is None:
            return answer
        interaction_id = self._logger.record_interaction(question, results, answer)
        return replace(answer, interaction_id=interaction_id)


def _has_verified_grounding(generated: str, results: list) -> bool:
    markers = [int(value) for value in re.findall(r"\[P(\d+)]", generated)]
    if not markers or any(value < 1 or value > len(results) for value in markers):
        return False
    paragraphs = [item.strip() for item in generated.split("\n\n") if item.strip()]
    for paragraph in paragraphs:
        cited = [int(value) for value in re.findall(r"\[P(\d+)]", paragraph)]
        if not cited:
            return False
        answer_terms = set(tokens(re.sub(r"\[P\d+]", "", paragraph)))
        source_terms = set().union(*(
            set(tokens(results[index - 1].passage.text)) for index in cited
        ))
        supported = answer_terms & source_terms
        if not supported or len(supported) / max(len(answer_terms), 1) < 0.15:
            return False
    return True
