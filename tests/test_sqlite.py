import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path

from doutrinador.domain import Document, SourceLevel
from doutrinador.infrastructure import SQLiteKnowledgeBase


class SQLiteKnowledgeBaseTests(unittest.TestCase):
    def test_documento_permanece_apos_reabrir_banco(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "acervo.db"
            first = SQLiteKnowledgeBase(path)
            document = Document("Carta de teste", "Autoria", SourceLevel.A, "Texto preservado.")
            first.add(document)

            reopened = SQLiteKnowledgeBase(path)
            documents = reopened.list()
            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0], document)

    def test_busca_respeita_precedencia(self):
        with tempfile.TemporaryDirectory() as directory:
            base = SQLiteKnowledgeBase(Path(directory) / "acervo.db")
            base.add(Document("Auxiliar", "Autor", SourceLevel.D, "A caridade orienta a conduta."))
            base.add(Document("Primária", "Autora", SourceLevel.A, "A caridade orienta a conduta."))
            results = base.search("caridade conduta")
            self.assertEqual(results[0].document.source_level, SourceLevel.A)

    def test_banco_antigo_recebe_observacao_sem_perder_documentos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legado.db"
            with closing(sqlite3.connect(path)) as connection:
                with connection:
                    connection.execute("""
                    CREATE TABLE documents (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL,
                        source_level TEXT NOT NULL, content TEXT NOT NULL, year INTEGER,
                        edition TEXT, origin TEXT, authenticity_status TEXT NOT NULL,
                        rights_status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                    connection.execute("""
                    INSERT INTO documents VALUES
                    ('1','Legado','Autor','C','Conteúdo',NULL,NULL,'Arquivo','pendente','não informado',CURRENT_TIMESTAMP)
                """)
            migrated = SQLiteKnowledgeBase(path)
            self.assertEqual(len(migrated.list()), 1)
            self.assertIsNone(migrated.list()[0].provenance_note)
            migrated.add(Document(
                "Novo", "Autor", SourceLevel.C, "Texto", provenance_note="Acervo familiar"
            ))
            new_document = next(item for item in migrated.list() if item.title == "Novo")
            self.assertEqual(new_document.provenance_note, "Acervo familiar")

    def test_edicao_registra_historico_e_preserva_conteudo(self):
        with tempfile.TemporaryDirectory() as directory:
            base = SQLiteKnowledgeBase(Path(directory) / "auditoria.db")
            original = Document("Obra", "Autor", SourceLevel.C, "Texto original")
            base.add(original)
            updated = base.update_metadata(
                original.id, {"source_level": "B", "origin": "Acervo validado"},
                "Adjunto responsável", "Reconhecimento institucional confirmado",
            )
            self.assertEqual(updated.source_level, SourceLevel.B)
            self.assertEqual(updated.content, "Texto original")
            history = base.history(original.id)
            self.assertEqual(len(history), 2)
            self.assertEqual({item["field"] for item in history}, {"source_level", "origin"})
            self.assertTrue(all(item["responsible"] == "Adjunto responsável" for item in history))


if __name__ == "__main__":
    unittest.main()
