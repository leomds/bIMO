import runpod
import asyncio
import logging
import time
import httpx
from shared.schemas import AudioRequest
from server.handler import handle_chat
from server.stt import get_stt_backend
from server.tts import get_tts_backend
from server.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def async_handler(job):
    """Handler nativo para o RunPod Serverless."""
    try:
        job_input = job.get("input", {})
        req = AudioRequest(**job_input)
        response = await handle_chat(req)
        return response.model_dump()
    except Exception as e:
        logger.error(f"[RUNPOD] Erro fatal: {e}", exc_info=True)
        return {"error": str(e)}


def start_ollama():
    """
    Aguarda o Ollama (já iniciado pelo entrypoint) e faz warm-up dos modelos.
    NÃO tenta subir o Ollama aqui — o entrypoint já fez isso via 'ollama serve &'.
    Tentar subir de novo causaria conflito na porta 11434.
    """
    logger.info("[Ollama] Aguardando daemon (iniciado pelo entrypoint)...")

    for attempt in range(30):
        try:
            resp = httpx.get(config.ollama_base_url, timeout=3.0)
            if resp.status_code == 200:
                logger.info(f"[Ollama] Respondendo após {(attempt + 1) * 2}s ✅")
                break
        except httpx.RequestError:
            pass
        time.sleep(2)
    else:
        logger.warning("[Ollama] Não respondeu em 60s — continuando mesmo assim.")
        return

    # Warm-up: força o modelo para a VRAM antes da primeira request real.
    # Elimina o delay de ~3-5s de load na primeira chamada do usuário.
    logger.info(f"[Ollama] Aquecendo {config.ollama_model} na VRAM...")
    try:
        httpx.post(
            f"{config.ollama_base_url}/api/generate",
            json={
                "model": config.ollama_model,
                "prompt": "",
                "keep_alive": config.ollama_keep_alive,
            },
            timeout=120.0,
        )
        logger.info(f"[Ollama] {config.ollama_model} carregado na VRAM ✅")
    except Exception as e:
        logger.warning(f"[Ollama] Warm-up falhou (não crítico): {e}")

    logger.info("[Warm-up] Carregando Whisper e TTS...")
    try:
        get_stt_backend()
        logger.info("[Warm-up] Whisper OK ✅")
    except Exception as e:
        logger.warning(f"[Warm-up] Whisper falhou: {e}")

    try:
        get_tts_backend()
        logger.info("[Warm-up] TTS OK ✅")
    except Exception as e:
        logger.warning(f"[Warm-up] TTS falhou: {e}")


if __name__ == "__main__":
    start_ollama()
    logger.info("[BIMO] Iniciando RunPod Serverless handler...")
    runpod.serverless.start({"handler": async_handler})