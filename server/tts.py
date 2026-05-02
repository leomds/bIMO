"""
server/tts.py
Text-to-Speech modular. Backend configurável via TTS_BACKEND env var.

Backends disponíveis:
  piper   — RECOMENDADO para RunPod: ~200ms, sem GPU, sem display, PT-BR nativo
  coqui   — Alta qualidade + clonagem de voz (XTTS v2), mas ~3-8s e precisa de GPU
  mock    — WAV silencioso para testes

Roadmap de voz clonada do BMO:
  1. Colete amostras do BMO dublado em PT-BR (pasta server/assets/bmo_audios/)
  2. Configure TTS_BACKEND=coqui + TTS_REFERENCE_WAV apontando para o WAV de referência
  3. O XTTS v2 faz zero-shot voice cloning — sem fine-tuning necessário
"""

import base64
import io
import logging
import os
import tempfile
import wave
from pathlib import Path
from typing import Protocol

from server.config import config

logger = logging.getLogger(__name__)


# ─── Protocol (interface) ─────────────────────────────────────────────────

class TTSBackend(Protocol):
    def synthesize(self, text: str) -> bytes:
        """Retorna bytes de áudio WAV."""
        ...


# ─── Mock ─────────────────────────────────────────────────────────────────

class MockTTS:
    """WAV silencioso para testes sem dependências."""

    def synthesize(self, text: str) -> bytes:
        logger.warning(f"[TTS] MOCK — áudio simulado para: '{text[:50]}'")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(b"\x00\x00" * 11025)  # 0.5s de silêncio
        return buf.getvalue()


# ─── Piper TTS ────────────────────────────────────────────────────────────

class PiperTTS:
    """
    Piper TTS — rápido (~200ms), sem GPU, sem display, PT-BR nativo.
    Usa a API Python do piper-tts (pip install piper-tts).

    Modelos PT-BR disponíveis (baixados automaticamente pelo entrypoint):
      pt_BR-faber-medium  — voz masculina natural (recomendado)
      pt_BR-faber-low     — voz masculina mais leve e rápida
      pt_BR-edresson-low  — voz masculina alternativa
    """

    def __init__(self):
        self._voice_name = config.piper_voice
        self._voice_dir = Path(config.piper_voice_dir)
        self._model_path = self._voice_dir / f"{self._voice_name}.onnx"

        logger.info(f"[TTS] Inicializando Piper: voice={self._voice_name} dir={self._voice_dir}")

        try:
            from piper.voice import PiperVoice
        except ImportError:
            raise RuntimeError("piper-tts não instalado. pip install piper-tts")

        if not self._model_path.exists():
            raise RuntimeError(
                f"Modelo Piper não encontrado: {self._model_path}\n"
                f"Verifique se o entrypoint baixou o modelo corretamente,\n"
                f"ou se PIPER_VOICE_DIR aponta para o diretório correto."
            )

        self._voice = PiperVoice.load(str(self._model_path))
        logger.info(f"[TTS] Piper pronto: {self._model_path}")

    def synthesize(self, text: str) -> bytes:
        logger.info(f"[TTS] Piper sintetizando: '{text[:60]}'")

        # Usa arquivo temporário em vez de BytesIO porque o Piper precisa
        # fazer seek para escrever o header WAV corretamente.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with wave.open(tmp_path, "wb") as wav_file:
                self._voice.synthesize(text, wav_file)

            with open(tmp_path, "rb") as f:
                audio = f.read()

            logger.info(f"[TTS] Piper OK: {len(audio)} bytes")
            return audio
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ─── Coqui XTTS v2 ────────────────────────────────────────────────────────

class CoquiTTS:
    """
    Coqui XTTS v2 — alta qualidade + zero-shot voice cloning.
    Use quando tiver o áudio de referência do BMO.
    Requer GPU com ~3GB VRAM livres.

    Para ativar a voz clonada do BMO:
      TTS_BACKEND=coqui
      TTS_REFERENCE_WAV=server/assets/bmo_audios/complete_output.wav
    """

    def __init__(self):
        logger.info(f"[TTS] Inicializando Coqui XTTS: model={config.coqui_model}")
        try:
            from TTS.api import TTS as CoquiAPI
            import torch
            use_gpu = torch.cuda.is_available()

            if config.tts_voice_id and os.path.exists(config.tts_voice_id):
                self._tts = CoquiAPI(model_path=config.tts_voice_id, progress_bar=False, gpu=use_gpu)
                logger.info(f"[TTS] Modelo customizado: {config.tts_voice_id} (GPU={use_gpu})")
            else:
                self._tts = CoquiAPI(model_name=config.coqui_model, progress_bar=False, gpu=use_gpu)
                logger.info(f"[TTS] Modelo pré-treinado: {config.coqui_model} (GPU={use_gpu})")
        except ImportError:
            raise RuntimeError("TTS não instalado. pip install 'TTS>=0.22.0,<0.23'")

    def synthesize(self, text: str) -> bytes:
        logger.info(f"[TTS] Coqui sintetizando: '{text[:60]}'")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            kwargs = {"text": text, "file_path": tmp_path}

            if config.tts_reference_wav and os.path.exists(config.tts_reference_wav):
                kwargs["speaker_wav"] = config.tts_reference_wav
                if "multilingual" in config.coqui_model or "xtts" in config.coqui_model:
                    kwargs["language"] = "pt"
                logger.info(f"[TTS] Usando referência: {config.tts_reference_wav}")

            self._tts.tts_to_file(**kwargs)

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ─── Factory ──────────────────────────────────────────────────────────────

_backend_instance: TTSBackend | None = None


def get_tts_backend() -> TTSBackend:
    global _backend_instance
    if _backend_instance is None:
        name = config.tts_backend.lower()
        logger.info(f"[TTS] Carregando backend: {name}")

        if name == "piper":
            try:
                _backend_instance = PiperTTS()
            except Exception as e:
                logger.error(f"[TTS] Falha ao carregar Piper: {e} — usando mock")
                _backend_instance = MockTTS()
        elif name == "coqui":
            _backend_instance = CoquiTTS()
        elif name == "mock":
            _backend_instance = MockTTS()
        else:
            logger.warning(f"[TTS] Backend '{name}' desconhecido — usando mock")
            _backend_instance = MockTTS()

    return _backend_instance


def synthesize(text: str) -> str:
    """Sintetiza texto e retorna áudio WAV em base64."""
    audio_bytes = get_tts_backend().synthesize(text)
    return base64.b64encode(audio_bytes).decode("utf-8")