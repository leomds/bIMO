# BIMO Assistant 🤖

Um assistente pessoal por voz modular, inteligente e divertido, inspirado no adorável BMO de *Hora de Aventura*. O BIMO não é apenas um chatbot genérico: ele tem personalidade própria, demonstra emoções mudando o rosto sincronizado com a fala, possui memória de longo prazo (RAG) e é capaz de acionar automações residenciais.

## 🏗️ Arquitetura do Projeto

O projeto foi construído com a premissa de **"Cliente Leve na CPU, Servidor Pesado na GPU"**.

1. **Client (Local):** Roda no computador do usuário. Consome pouquíssimos recursos.
   - **Interface:** Tkinter leve com cache de imagens para evitar travamentos.
   - **Wake Word:** Vosk (100% offline e grátis) escutando passivamente a palavra "BIMO".
   - **Áudio:** Captura de microfone nativa e reprodução via `pygame`.

2. **Server (Nuvem / RunPod):** Um container "All-in-One" focado em rodar em Placas de Vídeo (GPUs).
   - **Cérebro (LLM):** Qwen2.5 (14B) rodando via Ollama no próprio container.
   - **Ouvidos (STT):** Faster-Whisper rodando direto na VRAM via CUDA (float16).
   - **Voz (TTS):** Coqui TTS com *Zero-Shot Voice Cloning* (XTTSv2) para imitar a voz original do BMO.
   - **Memória (RAG):** ChromaDB embutido para salvar e resgatar lembranças de conversas passadas.
   - **Módulos:** Roteador de intenções para comandos mockados (Alexa, Home Automation, etc.).

---

## ⚙️ Tecnologias Utilizadas
- **Linguagem:** Python 3.10
- **Modelos de IA:** Qwen 2.5 (14B), Whisper, XTTSv2
- **Infraestrutura:** Docker, RunPod Serverless, FastAPI
- **Bancos de Dados:** ChromaDB (Vetorial local)

---

## 🚀 Como fazer o Deploy do Servidor (RunPod Serverless)

O servidor foi desenhado para ser implantado usando o **RunPod Serverless** e extrair o máximo do hardware. O modelo LLM é baixado e injetado na imagem Docker durante o "build", e aquecido na VRAM assim que o Pod inicia.

### 1. Build da Imagem Docker
No seu computador, abra o terminal na raiz do projeto e rode:
```bash
# Substitua pelo seu usuário do Docker Hub
docker build -t seu_usuario/bimo-serverless:latest .
docker push seu_usuario/bimo-serverless:latest
```
*Aviso: O build vai demorar, pois fará o download do modelo Qwen2.5 (aprox. 8GB) diretamente pro container.*

### 2. Configurando no RunPod
1. Crie um **Serverless Template** usando a sua imagem do Docker Hub.
2. Crie um **Endpoint** a partir desse template. Selecione uma GPU de no mínimo **16GB de VRAM** (ex: RTX A4000) e garanta que o "Container Disk" tenha pelo menos **25GB**.
3. **Variáveis de Ambiente Recomendadas no Endpoint:**
   - `WHISPER_DEVICE=cuda`
   - `WHISPER_COMPUTE_TYPE=float16`
   - `TTS_BACKEND=coqui`
4. **Persistência de Memória:** Para o BIMO não sofrer de amnésia toda vez que o servidor reiniciar, crie um **Network Volume** no RunPod e mapeie para o caminho `/app/server/memory_db` do seu container.

---

## 💻 Como Rodar o Cliente Local (Seu PC)

Depois que o servidor estiver rodando na nuvem (ou se você quiser rodar localmente com `uvicorn` na sua própria placa de vídeo), siga os passos para o Cliente.

### 1. Requisitos do Cliente
Você precisa ter o driver nativo de áudio para o `sounddevice` e `pygame` funcionarem:
* **Linux:** `sudo apt install portaudio19-dev ffmpeg`
* **Windows:** Baixe e instale o pacote oficial do FFmpeg.

### 2. Instalação
Na raiz do projeto, instale os pacotes levinhos do cliente:
```bash
pip install -r requirements-client.txt
```

### 3. Configuração
Crie e configure o seu arquivo `.env`:
```bash
cp .env.example .env
```
Dentro do `.env`, modifique as variáveis de rede para apontar para o seu RunPod:
```dotenv
# Se você usa RunPod, pegue a URL que termina em /runsync
BIMO_SERVER_URL=https://api.runpod.ai/v2/SEU_ID_DO_ENDPOINT/runsync
BIMO_RUNPOD_API_KEY=sua_chave_de_api_gerada_no_runpod
```

### 4. Executando
```bash
python -m client.app
```
O modelo de *wake word* (Vosk) fará um download rápido de 50MB na primeira execução. Após isso, diga **"BIMO"** para acordá-lo e comece a conversar!

---

## 🗂️ Estrutura de Diretórios

```text
bimo-assistant/
├── client/                 # Tudo que roda no PC do usuário (CPU)
│   ├── app.py              # UI com Tkinter e cache de rostos
│   ├── audio_player.py     # Toca a resposta recebida em base64
│   ├── recorder.py         # Captura o microfone do PC
│   └── wake_word.py        # Escuta passivamente a palavra "BIMO" com Vosk
│
├── server/                 # Tudo que roda na nuvem (GPU)
│   ├── handler.py          # FastAPI para testes locais
│   ├── runpod_handler.py   # Handler oficial para a infraestrutura do RunPod (faz o warm-up dos modelos)
│   ├── config.py           # Gestão central de vars do .env
│   ├── memory.py           # Gerenciador de RAG (ChromaDB)
│   ├── ollama_client.py    # Interface HTTP com o Qwen2.5 e injeção de Prompt/Contexto
│   ├── stt.py              # Motor Faster-Whisper
│   ├── tts.py              # Motor CoquiTTS / Pyttsx3
│   └── modules/            # Habilidades de Automação do BIMO (Alexa, Home, etc)
│
├── shared/                 # Comum entre Cliente e Servidor
│   ├── prompts.py          # A Alma do BIMO (Personalidade, moods, comportamentos)
│   └── schemas.py          # Validadores Pydantic garantindo o tráfego em JSON
│
├── assets/                 # Imagens dos rostos e arquivos de áudio (.wav) para clonagem
├── requirements-client.txt # Bibliotecas do Frontend
├── requirements-server.txt # Bibliotecas pesadas do Backend (PyTorch, TTS, etc)
└── Dockerfile              # Receita para nuvem (All-in-one com Llama/Qwen injetado)
```

---

## 🎭 O Sistema de Moods
O diferencial do BIMO é sua interface animada. Durante o processamento no LLM, a resposta não volta apenas como um texto cru, mas como uma lista de segmentos emocionais:

```json
"moods": [
  { "mood_id": 16, "text": "Hmm... isso é grande..." },
  { "mood_id": 13, "text": "hehe..." }
]
```
O frontend lê essa resposta, sincroniza as imagens do rosto (1 a 22) contidas na pasta `assets` de acordo com a emoção associada e reproduz o áudio simultaneamente, criando a ilusão de que o BIMO "sente" o que está falando.