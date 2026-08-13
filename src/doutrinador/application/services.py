from doutrinador.application.ports import DocumentRepository, KnowledgeRetriever
from doutrinador.domain import Answer, Citation, Document


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
        return self._repository.update_metadata(
            document_id, changes, responsible.strip(), justification.strip()
        )


class AskDoutrinador:
    def __init__(self, retriever: KnowledgeRetriever) -> None:
        self._retriever = retriever

    def execute(self, question: str) -> Answer:
        if len(question.strip()) < 3:
            raise ValueError("A pergunta deve possuir ao menos três caracteres.")
        results = self._retriever.search(question)
        if not results:
            return Answer(INSUFFICIENT_EVIDENCE, (), False, "Ausência de evidência no acervo atual.")

        citations = tuple(
            Citation(
                document_id=item.document.id,
                title=item.document.title,
                author=item.document.author,
                source_level=item.document.source_level,
                excerpt=item.excerpt,
            )
            for item in results
        )
        excerpts = " ".join(item.excerpt for item in results)
        return Answer(
            answer=(
                "Com base nas fontes recuperadas do acervo: " + excerpts
            ),
            citations=citations,
            grounded=True,
            observation=(
                "Síntese extrativa da versão inicial. O sistema não atribui à fonte "
                "informações que não estejam nos trechos apresentados."
            ),
        )
