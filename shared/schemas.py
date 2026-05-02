"""
shared/schemas.py
Modelos Pydantic usados tanto pelo client quanto pelo server.
"""

from __future__ import annotations
from typing import Literal, Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# MOODS
# ---------------------------------------------------------------------------

MOOD_MAP: dict[int, str] = {
    1:  "happy_simple",
    2:  "happy_open",
    3:  "sad",
    4:  "sleepy",
    5:  "shy_happy",
    6:  "surprised",
    7:  "angry_shouting",
    8:  "annoyed",
    9:  "serious",
    10: "angry",
    11: "crying_soft",
    12: "crying_heavy",
    13: "cute_excited",
    14: "silly",
    15: "soft_smile",
    16: "confused",
    17: "disgust",
    18: "default_happy",
    20: "star_eyes",
    21: "love",
    22: "shocked",
}


class MoodSegment(BaseModel):
    """Um segmento de fala com um humor associado."""
    mood_id: int = Field(..., description="ID do humor (1-22, ver MOOD_MAP)")
    text: str = Field(..., description="Trecho de fala correspondente a este humor")

    @property
    def mood_name(self) -> str:
        return MOOD_MAP.get(self.mood_id, "default_happy")

    @property
    def image_filename(self) -> str:
        return f"Rosto-{self.mood_id:02d}.png"


# ---------------------------------------------------------------------------
# REQUEST (client → server)
# ---------------------------------------------------------------------------

class AudioRequest(BaseModel):
    """Payload enviado pelo client para o server."""
    audio_b64: str = Field(..., description="Áudio WAV em base64")
    user_name: str = Field(default="Leo", description="Nome do usuário")
    sample_rate: int = Field(default=16000, description="Taxa de amostragem do áudio")


# ---------------------------------------------------------------------------
# LLM RESPONSE (estrutura interna do LLM)
# ---------------------------------------------------------------------------

IntentType = Literal["conversation", "command"]
ModuleType = Literal["home_automation", "alexa", "calendar", "web_search", "unknown"]


class LLMResponse(BaseModel):
    """Resposta estruturada que o LLM deve retornar em JSON."""
    type: IntentType
    module: ModuleType = "unknown"
    response: str = Field(..., description="Resposta textual completa do BIMO")
    action_input: dict = Field(default_factory=dict)
    moods: List[MoodSegment] = Field(
        default_factory=lambda: [MoodSegment(mood_id=18, text="...")],
        description="Sequência de moods sincronizados com a fala",
    )


# ---------------------------------------------------------------------------
# SERVER RESPONSE (server → client)
# ---------------------------------------------------------------------------

class BimoResponse(BaseModel):
    """Resposta completa enviada do server para o client."""
    transcript: str = Field(..., description="Texto transcrito pelo STT")
    intent: IntentType
    module: ModuleType
    response_text: str = Field(..., description="Resposta textual do BIMO")
    audio_b64: str = Field(..., description="Áudio TTS em base64 (WAV ou MP3)")
    moods: List[MoodSegment]
    action_result: Optional[dict] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# EXEMPLO DE PAYLOAD (para testes e documentação)
# ---------------------------------------------------------------------------

EXAMPLE_REQUEST = {
    "audio_b64": "<base64 do WAV>",
    "user_name": "Leo",
    "sample_rate": 16000,
}

EXAMPLE_RESPONSE = {
    "transcript": "liga a luz da sala",
    "intent": "command",
    "module": "home_automation",
    "response_text": "Ok! Luz acordou! Ela tava dormindo no escuro hehe",
    "audio_b64": "<base64 do áudio TTS>",
    "moods": [
        {"mood_id": 2,  "text": "Ok!"},
        {"mood_id": 13, "text": "Luz acordou!"},
        {"mood_id": 14, "text": "Ela tava dormindo no escuro hehe"},
    ],
    "action_result": {"device": "light", "room": "sala", "state": "on", "success": True},
}