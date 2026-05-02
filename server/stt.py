"""
server/stt.py
Speech-to-Text modular. Backend configurável via STT_BACKEND env var.
Backends disponíveis: "faster_whisper" | "mock"
"""

import base64
import io
import logging
import os
import tempfile
from typing import Protocol

from server.config import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol (interface)
# ---------------------------------------------------------------------------

class STTBackend(Protocol):
    def transcribe(self, audio_b64: str, sample_rate: int = 16000) -> str:
        ...


# ---------------------------------------------------------------------------
# Mock backend (para testes sem GPU)
# ---------------------------------------------------------------------------

class MockSTT:
    def transcribe(self, audio_b64: str, sample_rate: int = 16000) -> str:
        logger.warning("[STT] Usando backend MOCK — retornando texto fixo.")
        return "liga a luz da sala"


# ---------------------------------------------------------------------------
# Faster-Whisper backend
# ---------------------------------------------------------------------------

class FasterWhisperSTT:
    def __init__(self):
        logger.info(
            f"[STT] Carregando Faster-Whisper model={config.whisper_model} "
            f"device={config.whisper_device} compute={config.whisper_compute_type}"
        )
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                config.whisper_model,
                device=config.whisper_device,
                compute_type=config.whisper_compute_type,
            )
            logger.info("[STT] Faster-Whisper carregado com sucesso.")
        except ImportError:
            raise RuntimeError(
                "faster-whisper não instalado. "
                "Instale com: pip install faster-whisper"
            )

    def transcribe(self, audio_b64: str, sample_rate: int = 16000) -> str:
        audio_bytes = base64.b64decode(audio_b64)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            segments, info = self._model.transcribe(
                tmp_path,
                language="pt",
                beam_size=5,
            )
            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            logger.info(f"[STT] Transcrição: '{transcript}' (lang={info.language})")
            return transcript
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_backend_instance: STTBackend | None = None


def get_stt_backend() -> STTBackend:
    global _backend_instance
    if _backend_instance is None:
        backend_name = config.stt_backend.lower()
        logger.info(f"[STT] Inicializando backend: {backend_name}")

        if backend_name == "faster_whisper":
            _backend_instance = FasterWhisperSTT()
        elif backend_name == "mock":
            _backend_instance = MockSTT()
        else:
            logger.warning(f"[STT] Backend '{backend_name}' desconhecido. Usando mock.")
            _backend_instance = MockSTT()

    return _backend_instance


def transcribe(audio_b64: str, sample_rate: int = 16000) -> str:
    """Ponto de entrada principal para transcrição."""
    return get_stt_backend().transcribe(audio_b64, sample_rate)