import json
import tempfile
import unittest
from pathlib import Path

from doutrinador.application import AskDoutrinador, RegisterDocument
from doutrinador.application.services import INSUFFICIENT_EVIDENCE
from doutrinador.constitution import DOUTRINADOR_CONSTITUTION
from doutrinador.domain import Document, SourceLevel
from doutrinador.infrastructure import (
    InMemoryKnowledgeBase, OpenAIResponsesGenerator, OpenAITranscriber,
    SQLiteKnowledgeBase,
)
from doutrinador.infrastructure.chunking import chunk_document


CORPUS = (
    "[[PÁGINA: 12]]\n# Livre-arbítrio\n"
    "O livre-arbítrio exige responsabilidade nas escolhas.\n\n"
    "[[SEÇÃO: Caridade]]\n"
    "A caridade deve ser praticada com humildade."
)


class RecordingGenerator:
    def __init__(self, response="As escolhas exigem responsabilidade. [P1]"):
        self.response = response
        self.system_instruction = None
        self.passages = None

    def generate(self, question, passages, system_instruction):
        self.system_instruction = system_instruction
        self.passages = passages
        return self.response


class FakeResponses:
    def __init__(self):
        self.arguments = None

    def create(self, **kwargs):
        self.arguments = kwargs
        return type("Response", (), {"output_text": "Escolhas requerem responsabilidade. [P1]"})()


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()


class FakeTranscriptions:
    def __init__(self): self.arguments = None
    def create(self, **kwargs):
        self.arguments = kwargs
        return type("Transcription", (), {"text": "Pergunta transcrita"})()


class FakeAudioClient:
    def __init__(self):
        self.audio = type("Audio", (), {"transcriptions": FakeTranscriptions()})()


class RagTests(unittest.TestCase):
    def test_chunking_preserva_titulo_secao_e_pagina(self):
        document = Document("Carta", "Autoria", SourceLevel.A, CORPUS)
        passages = chunk_document(document, max_chars=80)
        self.assertEqual(passages[0].title, "Carta")
        self.assertEqual(passages[0].section, "Livre-arbítrio")
        self.assertEqual(passages[0].page, 12)
        self.assertEqual(passages[1].section, "Caridade")
        self.assertEqual(passages[1].page, 12)

    def test_busca_hibrida_encontra_sinonimos_sem_correspondencia_lexical(self):
        base = InMemoryKnowledgeBase()
        document = Document(
            "Carta", "Autoria", SourceLevel.A,
            "O livre-arbítrio orienta as escolhas e requer responsabilidade.",
        )
        base.add(document)
        results = base.search("Como a liberdade afeta nossas decisões?")
        self.assertTrue(results)
        self.assertEqual(results[0].document.id, document.id)
        self.assertGreater(results[0].semantic_score, 0)
        self.assertEqual(results[0].lexical_score, 0)

    def test_constituicao_e_injecao_de_contexto_sao_permanentes(self):
        base = InMemoryKnowledgeBase()
        base.add(Document("Carta", "Autoria", SourceLevel.A, CORPUS))
        generator = RecordingGenerator()
        answer = AskDoutrinador(base, generator).execute(
            "Como o livre-arbítrio orienta escolhas?"
        )
        self.assertTrue(answer.grounded)
        self.assertEqual(generator.system_instruction, DOUTRINADOR_CONSTITUTION)
        self.assertTrue(generator.passages)
        self.assertIn("exclusivamente", generator.system_instruction)

    def test_responses_api_recebe_constituicao_no_campo_instructions(self):
        base = InMemoryKnowledgeBase()
        base.add(Document("Carta", "Autoria", SourceLevel.A, CORPUS))
        passages = base.search("Como escolhas exigem responsabilidade?")
        client = FakeOpenAIClient()
        generator = OpenAIResponsesGenerator(model="modelo-de-teste", client=client)
        output = generator.generate(
            "Como escolhas exigem responsabilidade?", passages, DOUTRINADOR_CONSTITUTION
        )
        self.assertIn("[P1]", output)
        self.assertEqual(client.responses.arguments["instructions"], DOUTRINADOR_CONSTITUTION)
        self.assertEqual(client.responses.arguments["model"], "modelo-de-teste")
        self.assertIn(passages[0].passage.text, client.responses.arguments["input"])
        self.assertNotIn("tools", client.responses.arguments)

    def test_transcricao_openai_envia_audio_em_portugues(self):
        client = FakeAudioClient()
        transcriber = OpenAITranscriber(model="modelo-transcricao", client=client)
        text = transcriber.transcribe("pergunta.webm", b"audio", "audio/webm")
        self.assertEqual(text, "Pergunta transcrita")
        arguments = client.audio.transcriptions.arguments
        self.assertEqual(arguments["model"], "modelo-transcricao")
        self.assertEqual(arguments["language"], "pt")
        self.assertEqual(arguments["file"], ("pergunta.webm", b"audio", "audio/webm"))

    def test_citacao_inexistente_produz_abstencao(self):
        base = InMemoryKnowledgeBase()
        base.add(Document("Carta", "Autoria", SourceLevel.A, CORPUS))
        answer = AskDoutrinador(
            base, RecordingGenerator("Uma afirmação sem fonte válida. [P99]")
        ).execute("O que se diz sobre escolhas?")
        self.assertFalse(answer.grounded)
        self.assertEqual(answer.answer, INSUFFICIENT_EVIDENCE)
        self.assertEqual(answer.citations, ())

    def test_log_registra_pergunta_passagens_e_resposta(self):
        with tempfile.TemporaryDirectory() as directory:
            base = SQLiteKnowledgeBase(Path(directory) / "rag.db")
            base.add(Document("Carta", "Autoria", SourceLevel.A, CORPUS))
            answer = AskDoutrinador(base, RecordingGenerator(), base).execute(
                "Como as escolhas se relacionam à responsabilidade?"
            )
            logs = base.list_interactions()
            self.assertEqual(answer.interaction_id, logs[0]["id"])
            self.assertEqual(logs[0]["question"], "Como as escolhas se relacionam à responsabilidade?")
            self.assertTrue(logs[0]["passages"])
            self.assertEqual(logs[0]["response"], answer.answer)

    def test_questoes_doutrinarias_pre_avaliadas(self):
        fixture = Path(__file__).parent / "fixtures" / "doctrinal_questions.json"
        cases = json.loads(fixture.read_text(encoding="utf-8"))
        base = InMemoryKnowledgeBase()
        base.add(Document("Carta", "Autoria validada", SourceLevel.A, CORPUS))
        service = AskDoutrinador(base)
        for case in cases:
            with self.subTest(question=case["question"]):
                answer = service.execute(case["question"])
                self.assertEqual(answer.grounded, case["grounded"])
                for term in case["expected_terms"]:
                    self.assertIn(term, answer.answer.casefold())


if __name__ == "__main__":
    unittest.main()
