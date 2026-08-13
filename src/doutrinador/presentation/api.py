import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from doutrinador import __version__
from doutrinador.application import AskDoutrinador, RegisterDocument, UpdateDocumentMetadata
from doutrinador.domain import Document, SourceLevel
from doutrinador.infrastructure import SQLiteKnowledgeBase


PROJECT = Path(__file__).resolve().parents[3]
WEB = Path(__file__).resolve().parent / "web"
database_path = Path(os.getenv("DOUTRINADOR_DATABASE", str(PROJECT / "data" / "doutrinador.db")))
knowledge_base = SQLiteKnowledgeBase(database_path)
register_document = RegisterDocument(knowledge_base)
ask_doutrinador = AskDoutrinador(knowledge_base)
update_document = UpdateDocumentMetadata(knowledge_base)


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


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(WEB / "index.html", media_type="text/html")


@app.get("/health", tags=["Sistema"], summary="Verificar o serviço")
def health() -> dict:
    return {
        "status": "ok", "service": "Doutrinador", "version": __version__,
        "framework": "FastAPI", "storage": "sqlite", "documents": len(knowledge_base.list()),
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


def run() -> None:
    import uvicorn
    uvicorn.run(
        "doutrinador.presentation.api:app",
        host=os.getenv("DOUTRINADOR_HOST", "127.0.0.1"),
        port=int(os.getenv("DOUTRINADOR_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
