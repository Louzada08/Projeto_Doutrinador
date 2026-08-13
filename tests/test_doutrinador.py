import unittest

from doutrinador.application import AskDoutrinador, RegisterDocument
from doutrinador.application.services import INSUFFICIENT_EVIDENCE
from doutrinador.domain import Document, SourceLevel
from doutrinador.infrastructure import InMemoryKnowledgeBase


class DoutrinadorTests(unittest.TestCase):
    def setUp(self):
        self.base = InMemoryKnowledgeBase()
        RegisterDocument(self.base).execute(Document(
            title="Documento de teste", author="Autoria validada", source_level=SourceLevel.A,
            content="O livre-arbítrio exige responsabilidade nas escolhas.\n\nA caridade deve ser praticada com humildade.",
        ))
        self.ask = AskDoutrinador(self.base)

    def test_resposta_fundamentada_inclui_citacao(self):
        result = self.ask.execute("O que a fonte diz sobre livre-arbítrio?")
        self.assertTrue(result.grounded)
        self.assertEqual(result.citations[0].source_level, SourceLevel.A)
        self.assertIn("livre-arbítrio", result.citations[0].excerpt)

    def test_ausencia_de_fonte_nao_inventa_resposta(self):
        result = self.ask.execute("Qual é a orientação sobre astronomia?")
        self.assertFalse(result.grounded)
        self.assertEqual(result.answer, INSUFFICIENT_EVIDENCE)
        self.assertEqual(result.citations, ())

    def test_documento_exige_conteudo(self):
        with self.assertRaises(ValueError):
            Document("Título", "Autor", SourceLevel.B, "  ")


if __name__ == "__main__":
    unittest.main()

