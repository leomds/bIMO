import asyncio
import logging
from fastapi import FastAPI, HTTPException

from shared.schemas import AudioRequest, BimoResponse
from server.stt import transcribe
from server.tts import synthesize
from server.ollama_client import chat

from server.modules import MODULE_HANDLERS

logger = logging.getLogger(__name__)

app = FastAPI(title="BIMO Server", description="Backend for BIMO Voice Assistant")

@app.post("/api/chat", response_model=BimoResponse)
async def handle_chat(req: AudioRequest):
    try:
        logger.info(f"[HANDLER] Áudio recebido do usuário: {req.user_name}")

        # 1. STT: CPU-intensivo rodado em thread pool para não bloquear o event loop.
        # get_running_loop() é o método correto no Python 3.10+ (get_event_loop() está deprecated).
        loop = asyncio.get_running_loop()
        transcript = await loop.run_in_executor(
            None, transcribe, req.audio_b64, req.sample_rate
        )
        if not transcript:
            transcript = "..."

        # 2. LLM Router / Persona
        llm_resp = await chat(transcript, req.user_name)

        # 3. Action Execution
        action_result = None
        if llm_resp.type == "command" and llm_resp.module in MODULE_HANDLERS:
            logger.info(f"[HANDLER] Encaminhando para módulo: {llm_resp.module}")
            handler_func = MODULE_HANDLERS[llm_resp.module]
            action_result = handler_func(llm_resp.action_input)

        # 4. TTS: também CPU/GPU-intensivo — rodado em executor
        audio_b64 = await loop.run_in_executor(
            None, synthesize, llm_resp.response
        )

        # 5. Montar payload de resposta
        return BimoResponse(
            transcript=transcript,
            intent=llm_resp.type,
            module=llm_resp.module,
            response_text=llm_resp.response,
            audio_b64=audio_b64,
            moods=llm_resp.moods,
            action_result=action_result
        )

    except Exception as e:
        logger.error(f"[HANDLER] Erro fatal no pipeline do BIMO: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="As engrenagens do BIMO travaram! Tente novamente."
        )