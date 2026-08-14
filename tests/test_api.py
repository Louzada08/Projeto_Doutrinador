import os
import tempfile
import unittest
from pathlib import Path

_temp = tempfile.TemporaryDirectory()
os.environ["DOUTRINADOR_DATABASE"] = str(Path(_temp.name) / "api.db")

from fastapi.testclient import TestClient
from doutrinador.presentation.api import app
import doutrinador.presentation.api as api_module


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

    def test_citacao_abre_trecho_exato_e_interacao_e_auditada(self):
        created=self.client.post("/documents",json={
            "title":"Carta localizada","author":"Autoria","source_level":"A",
            "content":"[[PÁGINA: 27]]\n# Responsabilidade\nA responsabilidade acompanha cada escolha consciente."
        }).json()
        answer=self.client.post("/ask",json={"question":"O que acompanha cada escolha consciente?"}).json()
        self.assertTrue(answer["grounded"])
        citation=next(item for item in answer["citations"] if item["document_id"]==created["id"])
        passage=self.client.get(citation["source_url"])
        self.assertEqual(passage.status_code,200)
        self.assertEqual(passage.json()["text"],citation["excerpt"])
        self.assertEqual(passage.json()["section"],"Responsabilidade")
        self.assertEqual(passage.json()["page"],27)
        logs=self.client.get("/interactions").json()
        self.assertEqual(logs[0]["id"],answer["interaction_id"])

    def test_imagem_da_fonte_aparece_na_citacao_e_no_trecho(self):
        image_url="https://acervo.example.org/mesa-evangelica.jpg"
        created=self.client.post("/documents",json={
            "title":"Fonte visual","author":"Autoria","source_level":"A",
            "content":"A indumentária ritual deve respeitar a orientação registrada.",
            "image_url":image_url,
            "image_description":"Fotografia de uma indumentária ritual sobre fundo claro."
        })
        self.assertEqual(created.status_code,201)
        answer=self.client.post("/ask",json={
            "question":"O que a fonte visual diz sobre indumentária ritual?"
        }).json()
        citation=next(item for item in answer["citations"] if item["title"]=="Fonte visual")
        self.assertEqual(citation["image_url"],image_url)
        self.assertIn("Fotografia",citation["image_description"])
        passage=self.client.get(citation["source_url"]).json()
        self.assertEqual(passage["image_url"],image_url)

    def test_endereco_de_imagem_inseguro_e_rejeitado(self):
        response=self.client.post("/documents",json={
            "title":"Imagem inválida","author":"Autoria","source_level":"A",
            "content":"Conteúdo suficiente.","image_url":"javascript:alert(1)"
        })
        self.assertEqual(response.status_code,422)

    def test_interface_expoe_imagem_e_controles_de_voz(self):
        html=self.client.get("/").text
        script=self.client.get("/assets/app.js").text
        self.assertIn('name="image_url"',html)
        self.assertIn('id="voice-question"',html)
        self.assertIn('id="voice-help"',html)
        self.assertIn("SpeechRecognition",script)
        self.assertIn("SpeechSynthesisUtterance",script)
        self.assertIn("MediaRecorder",script)
        self.assertIn("window.isSecureContext",script)

    def test_capacidades_de_voz_informam_endereco_https(self):
        capabilities=self.client.get("/voice/capabilities")
        self.assertEqual(capabilities.status_code,200)
        self.assertEqual(capabilities.json()["https_url"],"https://192.168.10.105:8000")
        self.assertEqual(capabilities.json()["vpn_https_url"],"https://10.66.66.1:8000")
        self.assertEqual(capabilities.json()["language"],"pt-BR")

    def test_audio_pode_ser_transcrito_sem_ser_armazenado(self):
        class FakeTranscriber:
            def __init__(self): self.received=None
            def transcribe(self,filename,data,content_type):
                self.received=(filename,data,content_type)
                return "Qual é a orientação?"
        original=api_module.transcriber; fake=FakeTranscriber(); api_module.transcriber=fake
        try:
            response=self.client.post(
                "/voice/transcribe",content=b"audio-de-teste",
                headers={"Content-Type":"audio/webm;codecs=opus"},
            )
        finally:
            api_module.transcriber=original
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["text"],"Qual é a orientação?")
        self.assertEqual(fake.received,("pergunta.webm",b"audio-de-teste","audio/webm"))

    def test_transcricao_sem_provedor_falha_de_forma_explicita(self):
        original=api_module.transcriber; api_module.transcriber=None
        try:
            response=self.client.post(
                "/voice/transcribe",content=b"audio",
                headers={"Content-Type":"audio/webm"},
            )
        finally:
            api_module.transcriber=original
        self.assertEqual(response.status_code,503)
        self.assertIn("OPENAI_API_KEY",response.json()["detail"])


if __name__ == "__main__": unittest.main()
