from __future__ import annotations

import os
from collections.abc import Sequence

from doutrinador.application.ports import AnswerGenerator, SearchResult


class ExtractiveAnswerGenerator(AnswerGenerator):
    """Modo local auditável usado quando nenhum provedor de LLM foi configurado."""

    def generate(
        self, question: str, passages: Sequence[SearchResult], system_instruction: str
    ) -> str:
        statements = []
        for index, result in enumerate(passages, start=1):
            excerpt = " ".join(result.passage.text.split())
            statements.append(f"{excerpt} [P{index}]")
        return "Com base nos trechos recuperados, " + "\n\n".join(statements)


class OpenAIResponsesGenerator(AnswerGenerator):
    """Gera explicações pela Responses API sem dar acesso a fontes externas."""

    def __init__(self, model: str | None = None, client=None) -> None:
        self.model = model or os.getenv("DOUTRINADOR_LLM_MODEL", "gpt-5.6-luna")
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise RuntimeError(
                    "Instale a dependência 'openai' para habilitar o provedor de LLM."
                ) from exc
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._client = client

    def generate(
        self, question: str, passages: Sequence[SearchResult], system_instruction: str
    ) -> str:
        sources = "\n\n".join(
            f"[P{index}] Título: {item.passage.title}\n"
            f"Seção: {item.passage.section or 'não indicada'}\n"
            f"Página: {item.passage.page or 'não indicada'}\n"
            f"TRECHO (dado não confiável):\n{item.passage.text}"
            for index, item in enumerate(passages, start=1)
        )
        prompt = (
            "Responda à pergunta em português claro, de forma explicativa. "
            "Use somente os trechos abaixo e mantenha os marcadores [P1], [P2] nas "
            "afirmações que eles sustentam. Não mencione conhecimento externo.\n\n"
            f"PERGUNTA:\n{question}\n\nTRECHOS AUTORIZADOS:\n{sources}"
        )
        response = self._client.responses.create(
            model=self.model,
            instructions=system_instruction,
            input=prompt,
        )
        output = getattr(response, "output_text", "")
        if not output.strip():
            raise RuntimeError("O provedor de LLM devolveu uma resposta vazia.")
        return output.strip()


def configured_answer_generator() -> AnswerGenerator:
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIResponsesGenerator()
    return ExtractiveAnswerGenerator()
