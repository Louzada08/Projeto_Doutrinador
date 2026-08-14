from __future__ import annotations

import os


class OpenAITranscriber:
    """Transcreve áudio em memória sem armazenar a gravação no servidor."""

    def __init__(self, model: str | None = None, client=None) -> None:
        self.model = model or os.getenv(
            "DOUTRINADOR_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
        )
        api_key = (
            os.getenv("DOUTRINADOR_TRANSCRIPTION_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise RuntimeError(
                    "Instale a dependência 'openai' para habilitar a transcrição."
                ) from exc
            if not api_key:
                raise RuntimeError("Configure DOUTRINADOR_TRANSCRIPTION_API_KEY.")
            client = OpenAI(api_key=api_key)
        self._client = client

    def transcribe(self, filename: str, data: bytes, content_type: str) -> str:
        response = self._client.audio.transcriptions.create(
            model=self.model,
            file=(filename, data, content_type),
            language="pt",
        )
        text = getattr(response, "text", "")
        if not text.strip():
            raise RuntimeError("O provedor devolveu uma transcrição vazia.")
        return text.strip()


def configured_transcriber() -> OpenAITranscriber | None:
    configured = os.getenv("DOUTRINADOR_TRANSCRIPTION_API_KEY") or os.getenv("OPENAI_API_KEY")
    return OpenAITranscriber() if configured else None
