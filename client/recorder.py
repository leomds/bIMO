import sounddevice as sd
import numpy as np
import wave
import io
import base64
import os
import logging

logger = logging.getLogger(__name__)

# ─── Configurações via .env ────────────────────────────────────────────────
# Tempo máximo de gravação em segundos (segurança contra silêncio não detectado)
MAX_RECORD_SECONDS = int(os.getenv("MAX_RECORD_SECONDS", "15"))

# Quantos segundos de silêncio contínuo encerram a gravação
SILENCE_TIMEOUT = float(os.getenv("SILENCE_TIMEOUT", "1.2"))

# Taxa de amostragem
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))

# Limiar de RMS para considerar "silêncio" (0.0 a 1.0 — ajuste se o mic for muito sensível)
# Valor padrão 0.01 funciona bem para ambientes normais
SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.01"))
# ───────────────────────────────────────────────────────────────────────────


def record_audio_b64(sample_rate: int = SAMPLE_RATE) -> str:
    """
    Grava áudio do microfone e retorna WAV em base64.

    A gravação para automaticamente quando:
      1. Silêncio contínuo >= SILENCE_TIMEOUT segundos é detectado
         (após pelo menos 0.5s de fala para evitar parar cedo demais)
      2. Tempo máximo de MAX_RECORD_SECONDS é atingido (segurança)

    Variáveis de ambiente relevantes (client/.env):
      MAX_RECORD_SECONDS  — tempo máximo (padrão: 15s)
      SILENCE_TIMEOUT     — silêncio para parar (padrão: 1.2s)
      SILENCE_THRESHOLD   — sensibilidade do silêncio (padrão: 0.01)
    """
    frames = []
    silent_frames = 0
    total_frames = 0

    # Tamanho de cada bloco em amostras (~64ms por bloco)
    block_size = 1024

    # Quantos blocos de silêncio precisamos para encerrar
    silence_blocks_needed = int((SILENCE_TIMEOUT * sample_rate) / block_size)

    # Quantos blocos mínimos de fala antes de começar a checar silêncio
    # (evita encerrar imediatamente se o usuário demorar um segundo para falar)
    min_speech_blocks = int((0.5 * sample_rate) / block_size)

    # Limite máximo de blocos
    max_blocks = int((MAX_RECORD_SECONDS * sample_rate) / block_size)

    has_speech = False  # True assim que detectar fala pela primeira vez

    logger.info(
        f"[Recorder] Gravando... (max={MAX_RECORD_SECONDS}s, "
        f"silêncio={SILENCE_TIMEOUT}s, threshold={SILENCE_THRESHOLD})"
    )

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=block_size,
    ) as stream:
        while total_frames < max_blocks:
            block, _ = stream.read(block_size)
            frames.append(block.copy())
            total_frames += 1

            # Calcula RMS do bloco para detectar fala vs silêncio
            rms = float(np.sqrt(np.mean(block ** 2)))

            if rms >= SILENCE_THRESHOLD:
                # Bloco com fala detectada
                has_speech = True
                silent_frames = 0
            else:
                # Bloco silencioso — só encerra após o mínimo de fala detectada
                # Isso evita parar imediatamente se o usuário demorar para começar a falar
                if has_speech and total_frames >= min_speech_blocks:
                    silent_frames += 1
                    if silent_frames >= silence_blocks_needed:
                        logger.info(
                            f"[Recorder] Silêncio detectado após "
                            f"{total_frames * block_size / sample_rate:.1f}s — encerrando."
                        )
                        break

    if not frames:
        logger.warning("[Recorder] Nenhum frame gravado.")
        return ""

    # Converte lista de blocos float32 → int16
    audio_array = np.concatenate(frames, axis=0)
    audio_int16 = (audio_array * 32767).astype(np.int16)

    duration = len(audio_int16) / sample_rate
    logger.info(f"[Recorder] Gravação encerrada: {duration:.1f}s gravados.")

    # Serializa para WAV em memória e converte para base64
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    return base64.b64encode(buf.getvalue()).decode("utf-8")
