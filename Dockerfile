# ─────────────────────────────────────────────────────────────────────────────
# BIMO Server — Dockerfile otimizado para RunPod Serverless
#
# Estratégia de custo:
#   - Imagem base com CUDA 11.8 + PyTorch (fornecida pelo RunPod)
#   - Ollama instalado em RUNTIME pelo entrypoint (o build não tem acesso externo)
#   - Modelo LLM NÃO embutido na imagem (9GB!) — fica no Network Volume
#   - Piper TTS: ~200ms de síntese, sem GPU, sem display — ideal para serverless
#   - Whisper "base": boa qualidade em PT-BR, ocupa ~150MB de VRAM
#
# Network Volume (montar em /runpod-volume no painel do RunPod):
#   /runpod-volume/ollama/   → cache do Ollama (~3-10GB dependendo do modelo)
#   /runpod-volume/memory_db → banco de memória do BIMO (ChromaDB)
#   /runpod-volume/piper/    → modelos de voz do Piper TTS
# ─────────────────────────────────────────────────────────────────────────────

FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

# Dependências do sistema
# - ffmpeg: necessário para faster-whisper processar áudio
# - espeak-ng + libespeak-ng-dev: fallback TTS se Piper não estiver disponível
# - curl: usado pelo entrypoint para instalar Ollama em runtime
# - wget: download de modelos Piper em runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng-dev \
    curl \
    wget \
    zstd \
    libcublas-12-0 \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python — separado do COPY . . para cache de layer
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Código do projeto
COPY . .

# Garante que os módulos são encontrados independente do cwd
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Diz ao Ollama para guardar modelos no Network Volume quando disponível
# (sobrescrito pelo entrypoint se o volume estiver montado)
ENV OLLAMA_MODELS=/runpod-volume/ollama

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Para testar localmente com FastAPI:
# docker run --gpus all -e OLLAMA_MODELS=/root/.ollama -p 8000:8000 bimo-server \
#   uvicorn server.handler:app --host 0.0.0.0 --port 8000

CMD ["/entrypoint.sh"]
