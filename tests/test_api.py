import os
import tempfile
import unittest
from pathlib import Path

_temp = tempfile.TemporaryDirectory()
os.environ["DOUTRINADOR_DATABASE"] = str(Path(_temp.name) / "api.db")

from fastapi.testclient import TestClient
from doutrinador.presentation.api import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close(); _temp.cleanup()

    def test_pagina_e_documentacao_fastapi(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/health").json()["framework"], "FastAPI")
        schema = self.client.get("/openapi.json")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("/documents/{document_id}", schema.json()["paths"])

    def test_fluxo_completo_e_historico(self):
        created = self.client.post("/documents", json={
            "title":"Fonte HTTP","author":"Autoria validada","source_level":"A",
            "content":"A humildade orienta o estudo responsável."
        })
        self.assertEqual(created.status_code, 201); document=created.json()
        answer=self.client.post("/ask",json={"question":"O que orienta a humildade?"})
        self.assertTrue(answer.json()["grounded"])
        updated=self.client.put(f"/documents/{document['id']}",json={
            "changes":{"source_level":"B"},"responsible":"Revisor autorizado",
            "justification":"Classificação institucional confirmada"})
        self.assertEqual(updated.status_code,200)
        self.assertEqual(updated.json()["content"],document["content"])
        history=self.client.get(f"/documents/{document['id']}/history").json()
        self.assertEqual((history[0]["old_value"],history[0]["new_value"]),("A","B"))

    def test_validacao_e_protecao_do_conteudo(self):
        self.assertEqual(self.client.post("/documents",json={"title":"Sem campos"}).status_code,422)
        self.assertEqual(self.client.post("/documents",json={"title":"Fonte","author":"Autor","source_level":"Z","content":"Texto"}).status_code,422)
        created=self.client.post("/documents",json={"title":"Protegida","author":"Autor","source_level":"C","content":"Original"}).json()
        forbidden=self.client.put(f"/documents/{created['id']}",json={"changes":{"content":"Outro"},"responsible":"Pessoa","justification":"Tentativa inválida"})
        self.assertEqual(forbidden.status_code,422)


if __name__ == "__main__": unittest.main()
