import time
import json
import queue

def listen_for_wake_word() -> bool:
    """
    Escuta passivamente o microfone aguardando a palavra mágica usando Vosk (Offline/Free).

    O modelo Vosk e o stream de áudio são criados UMA ÚNICA VEZ e reutilizados
    em todas as chamadas subsequentes via estado interno do módulo.
    Isso evita recarregar ~50MB do disco a cada iteração do loop no app.py.
    """
    try:
        import vosk
        import sounddevice as sd
    except ImportError:
        print("[WAKE WORD] Bibliotecas não encontradas. Instale: pip install vosk sounddevice")
        time.sleep(5)
        return False

    # --- Estado persistente do módulo ---
    # Inicializado apenas na primeira chamada; reutilizado nas demais.
    global _vosk_model, _vosk_recognizer, _audio_queue, _stream

    if "_vosk_model" not in globals():
        vosk.SetLogLevel(-1)
        print("[WAKE WORD] Carregando modelo Vosk PT-BR (primeira vez, pode demorar um pouco)...")
        _vosk_model = vosk.Model(lang="pt")
        _vosk_recognizer = vosk.KaldiRecognizer(_vosk_model, 16000)
        _audio_queue = queue.Queue()

        def _audio_callback(indata, frames, time_info, status):
            if status:
                print(f"[WAKE WORD] Status do stream: {status}")
            _audio_queue.put(bytes(indata))

        _stream = sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=_audio_callback,
        )
        _stream.start()
        print("[WAKE WORD] 🟢 Escutando... Diga 'bimo' para ativar!")

    wake_words = ["bimo", "bino"]

    try:
        # Lê um bloco de áudio da fila (bloqueia até ter dados)
        data = _audio_queue.get(timeout=2.0)
        if _vosk_recognizer.AcceptWaveform(data):
            result = json.loads(_vosk_recognizer.Result())
            text = result.get("text", "").lower()
            if any(word in text for word in wake_words):
                print(f"\n[WAKE WORD] ✨ Palavra detectada: '{text}'! Acordando o BIMO...")
                return True
    except queue.Empty:
        pass
    except Exception as e:
        print(f"[WAKE WORD] Erro durante escuta: {e}")
        time.sleep(1)

    return False


def pause_stream():
    """
    Para o stream de áudio do wake word temporariamente.
    Deve ser chamado antes de abrir o microfone para gravação,
    pois dois streams simultâneos no mesmo dispositivo causam erro.
    """
    global _stream
    if "_stream" in globals() and _stream is not None and _stream.active:
        _stream.stop()
        print("[WAKE WORD] Stream pausado para gravação.")


def resume_stream():
    """
    Retoma o stream de áudio do wake word após a gravação terminar.
    Limpa a fila acumulada durante a pausa para evitar falsos positivos.
    """
    global _stream, _audio_queue
    if "_stream" in globals() and _stream is not None and not _stream.active:
        # Descarta áudio acumulado na fila durante a pausa
        if "_audio_queue" in globals():
            while not _audio_queue.empty():
                try:
                    _audio_queue.get_nowait()
                except Exception:
                    break
        _stream.start()
        print("[WAKE WORD] Stream retomado.")
