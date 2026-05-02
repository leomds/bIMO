#!/bin/bash
# docker-entrypoint.sh — BIMO Server entrypoint para RunPod Serverless
#
# Fluxo:
#   1. Instala Ollama se não estiver presente (runtime, pois o build não tem internet)
#   2. Detecta se Network Volume está montado em /runpod-volume
#   3. Configura OLLAMA_MODELS para o volume (persistência entre cold starts)
#   4. Sobe o Ollama e aguarda com retry robusto
#   5. Baixa o modelo LLM apenas se necessário (cache no volume)
#   6. Baixa modelo Piper TTS se necessário
#   7. Inicia o handler do RunPod

MODEL=${OLLAMA_MODEL:-"llama3.2:3b"}
VOLUME_DIR=${RUNPOD_VOLUME_PATH:-"/runpod-volume"}
PIPER_VOICE=${PIPER_VOICE:-"pt_BR-faber-medium"}
PIPER_VOICE_DIR="${VOLUME_DIR}/piper"

# ── 1. Instala Ollama se não estiver presente ──────────────────────────────
# O build do RunPod não tem acesso à internet, então instalamos aqui em runtime.
# O binário fica no container efêmero — a próxima vez ele instala de novo (~5s).
if ! command -v ollama &> /dev/null; then
    echo "[Entrypoint] Ollama não encontrado — instalando..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "[Entrypoint] ✅ Ollama instalado."
else
    echo "[Entrypoint] ✅ Ollama já presente."
fi

# ── 2. Network Volume ──────────────────────────────────────────────────────
if [ -d "$VOLUME_DIR" ]; then
    echo "[Entrypoint] ✅ Network Volume detectado em $VOLUME_DIR"
    export OLLAMA_MODELS="${VOLUME_DIR}/ollama"
    mkdir -p "${VOLUME_DIR}/ollama" "${VOLUME_DIR}/memory_db" "$PIPER_VOICE_DIR"
    echo "[Entrypoint] Ollama models path: $OLLAMA_MODELS"
else
    echo "[Entrypoint] ⚠️  Network Volume não encontrado — usando armazenamento efêmero"
    echo "[Entrypoint]    Modelos serão baixados a cada cold start!"
    export OLLAMA_MODELS="/root/.ollama"
    mkdir -p /root/.ollama "$PIPER_VOICE_DIR"
fi

# ── 3. Piper TTS ───────────────────────────────────────────────────────────
PIPER_MODEL_FILE="${PIPER_VOICE_DIR}/${PIPER_VOICE}.onnx"
PIPER_CONFIG_FILE="${PIPER_VOICE_DIR}/${PIPER_VOICE}.onnx.json"

if [ ! -f "$PIPER_MODEL_FILE" ]; then
    echo "[Entrypoint] Baixando modelo Piper TTS: $PIPER_VOICE ..."
    BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR"

    VOICE_TYPE=$(echo "$PIPER_VOICE" | sed 's/pt_BR-\([^-]*\)-.*/\1/')
    QUALITY=$(echo "$PIPER_VOICE" | sed 's/.*-\([^-]*\)$/\1/')
    HF_PATH="${BASE_URL}/${VOICE_TYPE}/${QUALITY}"

    # Não usa set -e aqui: falha no download é não-fatal (TTS vai para mock)
    if wget -q --show-progress -O "$PIPER_MODEL_FILE" "${HF_PATH}/${PIPER_VOICE}.onnx"; then
        wget -q -O "$PIPER_CONFIG_FILE" "${HF_PATH}/${PIPER_VOICE}.onnx.json" || true
        echo "[Entrypoint] ✅ Piper TTS pronto: $PIPER_MODEL_FILE"
    else
        rm -f "$PIPER_MODEL_FILE"
        echo "[Entrypoint] ⚠️  Falha ao baixar Piper — TTS usará mock como fallback."
    fi
else
    echo "[Entrypoint] ✅ Piper TTS já em cache — pulando download."
fi

# Exporta para o Python (config.py lê essas variáveis via os.getenv)
export PIPER_VOICE_DIR="$PIPER_VOICE_DIR"
export PIPER_VOICE="$PIPER_VOICE"

# ── 4. Ollama ─────────────────────────────────────────────────────────────
echo "[Entrypoint] Iniciando Ollama (models em $OLLAMA_MODELS)..."
OLLAMA_MODELS="$OLLAMA_MODELS" ollama serve &
OLLAMA_PID=$!

# Aguarda com retry robusto (até 60s)
echo "[Entrypoint] Aguardando Ollama ficar pronto..."
READY=0
for i in $(seq 1 30); do
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "[Entrypoint] ✅ Ollama pronto após $((i * 2))s."
        READY=1
        break
    fi
    sleep 2
done

if [ $READY -eq 0 ]; then
    echo "[Entrypoint] ❌ Ollama não respondeu em 60s. Abortando."
    exit 1
fi

# ── 5. Modelo LLM ─────────────────────────────────────────────────────────
if OLLAMA_MODELS="$OLLAMA_MODELS" ollama list 2>/dev/null | grep -q "^${MODEL}"; then
    echo "[Entrypoint] ✅ Modelo '$MODEL' já em cache."
else
    echo "[Entrypoint] Baixando modelo '$MODEL' (primeira execução — pode demorar)..."
    OLLAMA_MODELS="$OLLAMA_MODELS" ollama pull "$MODEL"
    echo "[Entrypoint] ✅ Modelo '$MODEL' baixado."
fi

# ── 6. Handler RunPod ─────────────────────────────────────────────────────
echo "[Entrypoint] Iniciando BIMO RunPod handler..."
exec python -m server.runpod_handler