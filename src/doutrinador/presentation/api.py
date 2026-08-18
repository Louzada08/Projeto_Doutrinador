import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from doutrinador import __version__
from doutrinador.application import AskDoutrinador, RegisterDocument, UpdateDocumentMetadata
from doutrinador.domain import Document, SourceLevel, validate_image_url
from doutrinador.infrastructure import (
    SQLiteKnowledgeBase, configured_answer_generator, configured_transcriber,
)


PROJECT = Path(__file__).resolve().parents[3]
WEB = Path(__file__).resolve().parent / "web"
database_path = Path(os.getenv("DOUTRINADOR_DATABASE", str(PROJECT / "data" / "doutrinador.db")))
knowledge_base = SQLiteKnowledgeBase(database_path)
register_document = RegisterDocument(knowledge_base)
answer_generator = configured_answer_generator()
ask_doutrinador = AskDoutrinador(knowledge_base, answer_generator, knowledge_base)
update_document = UpdateDocumentMetadata(knowledge_base)
transcriber = configured_transcriber()
MAX_AUDIO_BYTES = 15 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/mp4", "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm", "audio/x-m4a",
}


class DocumentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(min_length=1, max_length=300)
    source_level: SourceLevel
    content: str = Field(min_length=1, max_length=5_000_000)
    year: int | None = Field(default=None, ge=1800, le=2100)
    edition: str | None = Field(default=None, max_length=300)
    origin: str | None = Field(default=None, max_length=1000)
    provenance_note: str | None = Field(default=None, max_length=5000)
    authenticity_status: Literal["pendente", "validado", "contestado"] = "pendente"
    rights_status: Literal["não informado", "autorizado", "restrito"] = "não informado"
    image_url: str | None = Field(default=None, max_length=2000)
    image_description: str | None = Field(default=None, max_length=1000)

    @field_validator("image_url")
    @classmethod
    def image_must_be_web_url(cls, value: str | None) -> str | None:
        return validate_image_url(value)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class MetadataChanges(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    author: str | None = Field(default=None, min_length=1, max_length=300)
    source_level: SourceLevel | None = None
    year: int | None = Field(default=None, ge=1800, le=2100)
    edition: str | None = Field(default=None, max_length=300)
    origin: str | None = Field(default=None, max_length=1000)
    provenance_note: str | None = Field(default=None, max_length=5000)
    authenticity_status: Literal["pendente", "validado", "contestado"] | None = None
    rights_status: Literal["não informado", "autorizado", "restrito"] | None = None
    image_url: str | None = Field(default=None, max_length=2000)
    image_description: str | None = Field(default=None, max_length=1000)

    @field_validator("image_url")
    @classmethod
    def image_must_be_web_url(cls, value: str | None) -> str | None:
        return validate_image_url(value)


class MetadataUpdate(BaseModel):
    changes: MetadataChanges
    responsible: str = Field(min_length=1, max_length=300)
    justification: str = Field(min_length=5, max_length=2000)


app = FastAPI(
    title="Projeto Doutrinador",
    version=__version__,
    description=(
        "API de apoio ao estudo da Doutrina do Amanhecer. "
        "O Doutrinador pesquisa primeiro e responde com fundamento nas fontes cadastradas."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.mount("/assets", StaticFiles(directory=WEB), name="assets")

# Optional CORS configuration: set DOUTRINADOR_ALLOWED_ORIGINS to a comma-separated
# list of allowed origins (e.g. https://example.com). If set, CORS middleware is added.
allowed = os.getenv("DOUTRINADOR_ALLOWED_ORIGINS", "").strip()
if allowed:
    origins = [o.strip() for o in allowed.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(WEB / "index.html", media_type="text/html")


@app.get("/health", tags=["Sistema"], summary="Verificar o serviço")
def health() -> dict:
    return {
        "status": "ok", "service": "Doutrinador", "version": __version__,
        "framework": "FastAPI", "storage": "sqlite", "documents": len(knowledge_base.list()),
        "answer_mode": type(answer_generator).__name__,
        "server_transcription": transcriber is not None,
    }


@app.get("/documents", tags=["Acervo"], summary="Listar fontes")
def list_documents() -> list[dict]:
    return [asdict(item) for item in knowledge_base.list()]


@app.post("/documents", status_code=201, tags=["Acervo"], summary="Cadastrar uma fonte")
def create_document(payload: DocumentCreate) -> dict:
    try:
        document = Document(**payload.model_dump())
        return asdict(register_document.execute(document))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/documents/{document_id}", tags=["Acervo"], summary="Consultar uma fonte")
def get_document(document_id: str) -> dict:
    document = knowledge_base.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    return asdict(document)


@app.get(
    "/documents/{document_id}/passages",
    tags=["Acervo"],
    summary="Listar trechos indexados de uma fonte",
)
def document_passages(document_id: str) -> list[dict]:
    try:
        return [asdict(item) for item in knowledge_base.passages_for_document(document_id)]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/passages/{passage_id}", tags=["Pesquisa"], summary="Abrir o trecho exato citado")
def get_passage(passage_id: str) -> dict:
    passage = knowledge_base.get_passage(passage_id)
    if passage is None:
        raise HTTPException(status_code=404, detail="Trecho não encontrado.")
    return asdict(passage)


@app.put("/documents/{document_id}", tags=["Governança"], summary="Editar metadados")
def edit_document(document_id: str, payload: MetadataUpdate) -> dict:
    changes = payload.changes.model_dump(exclude_unset=True)
    try:
        updated = update_document.execute(
            document_id, changes, payload.responsible, payload.justification
        )
        return asdict(updated)
    except ValueError as exc:
        status = 404 if str(exc) == "Fonte não encontrada." else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@app.get("/documents/{document_id}/history", tags=["Governança"], summary="Consultar histórico")
def document_history(document_id: str) -> list[dict]:
    try:
        return knowledge_base.history(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/ask", tags=["Pesquisa"], summary="Perguntar ao Doutrinador")
def ask(payload: AskRequest) -> dict:
    try:
        return asdict(ask_doutrinador.execute(payload.question))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/voice/capabilities", tags=["Acessibilidade"], summary="Verificar recursos de voz")
def voice_capabilities() -> dict:
    port = os.getenv("DOUTRINADOR_PORT", "8000")
    lan_ip = os.getenv("DOUTRINADOR_HTTPS_IP", "192.168.10.105")
    vpn_ip = os.getenv("DOUTRINADOR_VPN_IP", "10.66.66.1")
    return {
        "server_transcription": transcriber is not None,
        "max_audio_bytes": MAX_AUDIO_BYTES,
        "language": "pt-BR",
        "https_url": (
            os.getenv("DOUTRINADOR_PUBLIC_URL") or
            f"https://{lan_ip}:{port}"
        ),
        "vpn_https_url": (
            os.getenv("DOUTRINADOR_VPN_PUBLIC_URL") or
            f"https://{vpn_ip}:{port}"
        ),
    }


@app.post("/voice/transcribe", tags=["Acessibilidade"], summary="Transcrever pergunta falada")
async def transcribe_voice(request: Request) -> dict:
    if transcriber is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Transcrição no servidor indisponível. Configure "
                "DOUTRINADOR_TRANSCRIPTION_API_KEY ou OPENAI_API_KEY."
            ),
        )
    content_type = request.headers.get("content-type", "").split(";", 1)[0].casefold()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Formato de áudio não suportado.")
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="A gravação excede 15 MB.")
    data = bytes(buffer)
    if not data:
        raise HTTPException(status_code=400, detail="A gravação está vazia.")
    extensions = {
        "audio/mp4": ".m4a", "audio/mpeg": ".mp3", "audio/ogg": ".ogg",
        "audio/wav": ".wav", "audio/webm": ".webm", "audio/x-m4a": ".m4a",
    }
    filename = f"pergunta{extensions[content_type]}"
    try:
        return {"text": transcriber.transcribe(filename, data, content_type)}
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Não foi possível transcrever a gravação."
        ) from exc


@app.get("/interactions", tags=["Governança"], summary="Consultar auditoria de perguntas")
def interactions(limit: int = 100) -> list[dict]:
    return knowledge_base.list_interactions(limit)


def run() -> None:
    import uvicorn
    uvicorn.run(
        "doutrinador.presentation.api:app",
        host=os.getenv("DOUTRINADOR_HOST", "0.0.0.0"),
        port=int(os.getenv("DOUTRINADOR_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
