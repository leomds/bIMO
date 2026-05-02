"""
server/ollama_client.py
Cliente para o Ollama LLM com suporte a JSON estruturado.
"""

import json
import logging
import re
from typing import Any

import httpx

from server.config import config
from shared.prompts import build_system_prompt
from shared.schemas import LLMResponse, MoodSegment
from server.memory import memory_manager

logger = logging.getLogger(__name__)

_FALLBACK_RESPONSE = LLMResponse(
    type="conversation",
    module="unknown",
    response="Ai... minha cabecinha travou um pouquinho. Pode repetir?",
    action_input={},
    moods=[
        MoodSegment(mood_id=16, text="Ai... minha cabecinha travou um pouquinho."),
        MoodSegment(mood_id=14, text="Pode repetir?"),
    ],
)


def _extract_json(text: str) -> dict:
    """Extrai JSON de uma string que pode conter markdown ou texto extra."""
    # Tenta direto
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tenta extrair bloco ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Tenta encontrar primeiro { } da string
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Não foi possível extrair JSON da resposta LLM: {text[:200]}")


async def chat(transcript: str, user_name: str = "Leo") -> LLMResponse:
    """
    Envia o texto transcrito ao Ollama e retorna a resposta estruturada do BIMO.
    """
    system_prompt = build_system_prompt(user_name=user_name)

    # RAG: Busca memórias passadas relevantes baseadas no que o usuário disse agora
    past_memories = memory_manager.retrieve_relevant(transcript)
    if past_memories:
        logger.info("[LLM] Memórias passadas encontradas e injetadas no contexto!")
        memory_context = f"\n\n[MEMÓRIAS RELEVANTES DE CONVERSAS PASSADAS]\n{past_memories}\nUse essas lembranças para manter o contexto, se for natural na conversa."
        system_prompt += memory_context

    payload = {
        "model": config.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        "stream": False,
        "keep_alive": config.ollama_keep_alive,  # mantém o modelo na VRAM entre requests
        "options": {
            "temperature": 0.9,
            "top_p": 0.9,
        },
        "format": "json",
    }

    url = f"{config.ollama_base_url}/api/chat"
    logger.info(f"[LLM] Enviando para Ollama: model={config.ollama_model} texto='{transcript[:80]}'")

    try:
        async with httpx.AsyncClient(timeout=config.ollama_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw_content = data.get("message", {}).get("content", "")
        logger.debug(f"[LLM] Resposta raw: {raw_content[:300]}")

        parsed = _extract_json(raw_content)
        llm_response = LLMResponse(**parsed)
        logger.info(
            f"[LLM] Intenção: {llm_response.type} | Módulo: {llm_response.module} | "
            f"Moods: {[m.mood_id for m in llm_response.moods]}"
        )
        
        # RAG: Salva a nova interação na memória do BIMO
        memory_manager.add_memory(transcript, llm_response.response)
        
        return llm_response

    except httpx.HTTPStatusError as e:
        logger.error(f"[LLM] Erro HTTP do Ollama: {e.response.status_code} — {e.response.text[:200]}")
        return _FALLBACK_RESPONSE
    except httpx.RequestError as e:
        logger.error(f"[LLM] Erro de conexão com Ollama: {e}")
        return _FALLBACK_RESPONSE
    except (ValueError, Exception) as e:
        logger.error(f"[LLM] Erro ao processar resposta: {e}")
        return _FALLBACK_RESPONSE