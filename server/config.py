import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

_SERVER_DIR = Path(__file__).parent


class Config:
    # ── Ollama ────────────────────────────────────────────────────────────
    ollama_base_url  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model     = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    ollama_timeout   = int(os.getenv("OLLAMA_TIMEOUT", "90"))
    # keep_alive mantém o modelo na VRAM entre requests — economiza reload (~3-5s)
    ollama_keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

    # ── STT ───────────────────────────────────────────────────────────────
    stt_backend          = os.getenv("STT_BACKEND", "faster_whisper")
    whisper_model        = os.getenv("WHISPER_MODEL", "base")
    whisper_device       = os.getenv("WHISPER_DEVICE", "cuda")
    whisper_compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

    # ── TTS ───────────────────────────────────────────────────────────────
    tts_backend  = os.getenv("TTS_BACKEND", "piper")
    tts_speed    = float(os.getenv("TTS_SPEED", "1.0"))

    # Piper TTS
    piper_voice     = os.getenv("PIPER_VOICE", "pt_BR-faber-medium")
    piper_voice_dir = os.getenv("PIPER_VOICE_DIR", str(_SERVER_DIR / "assets" / "piper_voices"))

    # Coqui TTS (alternativo, para voz clonada)
    tts_voice_id   = os.getenv("TTS_VOICE_ID", "")
    coqui_model    = os.getenv("COQUI_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    _ref_wav_raw   = os.getenv("TTS_REFERENCE_WAV", "")
    if _ref_wav_raw:
        _ref_wav_path = Path(_ref_wav_raw)
        tts_reference_wav = str(
            _ref_wav_path if _ref_wav_path.is_absolute()
            else (_SERVER_DIR / _ref_wav_path).resolve()
        )
    else:
        tts_reference_wav = ""

    # ── Network Volume ────────────────────────────────────────────────────
    volume_path = os.getenv("RUNPOD_VOLUME_PATH", "")

    # Só usa o volume se a variável estiver definida E o diretório existir.
    # Path('').exists() retorna True em Python, por isso a checagem explícita.
    _volume_exists = bool(volume_path) and Path(volume_path).is_dir()
    memory_db_path = str(
        Path(volume_path) / "memory_db"
        if _volume_exists
        else _SERVER_DIR / "memory_db"
    )


config = Config()
