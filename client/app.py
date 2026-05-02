import tkinter as tk
from tkinter import messagebox
import threading
import requests
import time
import os
import logging
from pathlib import Path
from PIL import Image, ImageTk
from dotenv import load_dotenv

# Carrega variáveis do .env do cliente — path absoluto para funcionar
# independente de onde o script for executado
load_dotenv(Path(__file__).parent / ".env")

# Configura logging antes de qualquer import interno.
# Sem basicConfig, todos os logs de INFO/WARNING/ERROR são descartados silenciosamente.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from client.recorder import record_audio_b64
from client.audio_player import play_audio_b64
from client.wake_word import listen_for_wake_word, pause_stream, resume_stream

# Diretório onde este arquivo está — usado para resolver paths de assets
_CLIENT_DIR = Path(__file__).parent

SERVER_URL = os.getenv("BIMO_SERVER_URL", "http://localhost:8000/api/chat")
RUNPOD_API_KEY = os.getenv("BIMO_RUNPOD_API_KEY", "")
USER_NAME = os.getenv("BIMO_USER_NAME", "Leo")

class BimoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BIMO Local Client")
        self.root.geometry("450x600")
        self.root.configure(bg="#2E8B57")
        
        self.face_label = tk.Label(root, bg="#8FBC8F")
        self.face_label.pack(pady=50)
        
        self.faces_cache = {}
        self._load_faces()
        
        self.status_label = tk.Label(root, text="BIMO está dormindo...", bg="#2E8B57", fg="white", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
        self.record_button = tk.Button(
            root, text="🎤 Falar com BIMO", command=self.on_record_click, 
            font=("Arial", 16, "bold"), bg="#FFD700", relief="raised"
        )
        self.record_button.pack(pady=30)
        
        self.set_face(1)

        # Lock que garante que apenas um pipeline rode por vez,
        # evitando race condition entre clique manual e wake word.
        self._interaction_lock = threading.Lock()

        # Inicia a thread que escuta a palavra mágica em segundo plano
        self.wake_thread = threading.Thread(target=self._wake_word_loop, daemon=True)
        self.wake_thread.start()

    def _wake_word_loop(self):
        """Loop infinito aguardando a palavra de ativação."""
        while True:
            detected = listen_for_wake_word()
            if detected:
                # Tenta adquirir o lock — se já estiver processando, ignora a detecção
                if self._interaction_lock.acquire(blocking=False):
                    self._interaction_lock.release()
                    self.root.after(0, self.on_record_click)

    def _load_faces(self):
        # Paths absolutos relativos à localização do app.py — funciona
        # independente do diretório de onde o script for executado.
        search_paths = [
            _CLIENT_DIR / "assets",
            _CLIENT_DIR / "assets" / "bmo_faces",
        ]
        for i in range(1, 23):
            filename = f"Rosto-{i:02d}.png"
            filepath = None
            for path in search_paths:
                temp_path = path / filename
                if temp_path.exists():
                    filepath = str(temp_path)
                    break
            if filepath:
                try:
                    img = Image.open(filepath).resize((350, 250), Image.Resampling.LANCZOS)
                    self.faces_cache[i] = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f"Erro ao processar {filepath}: {e}")

    def set_face(self, mood_id: int):
        if mood_id in self.faces_cache:
            self.face_label.config(image=self.faces_cache[mood_id], text="", width=350, height=250)
        else:
            self.face_label.config(image="", text=f"[Rosto-{mood_id:02d}]", width=20, height=5, font=("Courier", 20))
        # Não chamar root.update() aqui — o Tkinter redesenha automaticamente
        # na idle loop. Forçar update() quando chamado via root.after causa reentrância.

    def on_record_click(self):
        # Tenta adquirir o lock — se já estiver processando, ignora
        if not self._interaction_lock.acquire(blocking=False):
            return
        self.record_button.config(state=tk.DISABLED)
        self.status_label.config(text="BIMO está escutando...")
        self.set_face(2)
        # Pausa o stream do wake word ANTES de iniciar a thread de gravação,
        # para evitar conflito de dois InputStreams no mesmo dispositivo de áudio.
        pause_stream()
        threading.Thread(target=self.process_interaction, daemon=True).start()

    def process_interaction(self):
        # Evento usado para interromper a animação de moods quando o áudio terminar
        stop_animation = threading.Event()

        try:
            audio_b64 = record_audio_b64()
            resume_stream()  # libera o microfone de volta para o wake word
            
            self.root.after(0, lambda: self.status_label.config(text="BIMO está pensando..."))
            self.root.after(0, lambda: self.set_face(4))
            
            payload = {
                "audio_b64": audio_b64,
                "user_name": USER_NAME,
                "sample_rate": 16000
            }
            
            headers = {"Content-Type": "application/json"}
            if "runpod.io" in SERVER_URL or "runpod.ai" in SERVER_URL:
                payload = {"input": payload}
                if RUNPOD_API_KEY:
                    headers["Authorization"] = f"Bearer {RUNPOD_API_KEY}"

            # Timeout de 180s para suportar cold start do RunPod:
            # ollama pull + load do Whisper + load do TTS podem levar 2-3min na primeira chamada
            response = requests.post(SERVER_URL, json=payload, headers=headers, timeout=180)
            response.raise_for_status()
            data = response.json()
            
            if "runpod.io" in SERVER_URL or "runpod.ai" in SERVER_URL:
                data = data.get("output", data)
            
            moods = data.get("moods", [])
            audio_resp_b64 = data.get("audio_b64", "")
            response_text = data.get("response_text", "")
            
            self.root.after(0, lambda: self.status_label.config(text=response_text[:30] + "..."))
            
            # Inicia animação de moods em thread separada, passando o evento de parada
            anim_thread = threading.Thread(
                target=self.animate_moods,
                args=(moods, stop_animation),
                daemon=True
            )
            anim_thread.start()
            
            if audio_resp_b64:
                play_audio_b64(audio_resp_b64)

            # Áudio terminou: sinaliza para a animação parar na próxima janela de tempo
            stop_animation.set()
            # Aguarda a thread de animação terminar antes de liberar o botão
            anim_thread.join(timeout=3.0)

        except Exception as e:
            stop_animation.set()
            resume_stream()  # garante que o mic seja liberado mesmo em erro
            # Captura a mensagem de erro antes do lambda para evitar
            # "free variable referenced before assignment" no closure
            err_msg = str(e)
            self.root.after(0, lambda msg=err_msg: messagebox.showerror("BIMO Bugou!", msg))
        finally:
            self.root.after(0, lambda: self.status_label.config(text="BIMO está dormindo..."))
            self.root.after(0, lambda: self.record_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.set_face(18))
            # Libera o lock para permitir nova interação
            try:
                self._interaction_lock.release()
            except RuntimeError:
                pass  # já foi liberado

    def animate_moods(self, moods, stop_event: threading.Event):
        """
        Anima os moods de forma proporcional ao tamanho do texto de cada segmento.
        Para imediatamente se o stop_event for sinalizado (áudio terminou).
        """
        if not moods:
            return

        # Tempo por segmento proporcional ao número de caracteres (~55ms/char PT-BR)
        MS_PER_CHAR = 55

        for mood in moods:
            if stop_event.is_set():
                break
            mood_id = mood.get("mood_id", 18)
            text = mood.get("text", "")
            duration = max(0.6, len(text) * MS_PER_CHAR / 1000)

            self.root.after(0, lambda m=mood_id: self.set_face(m))
            # Espera em pequenos intervalos para ser responsivo ao stop_event
            elapsed = 0.0
            while elapsed < duration:
                if stop_event.is_set():
                    return
                time.sleep(0.1)
                elapsed += 0.1

if __name__ == "__main__":
    root = tk.Tk()
    app = BimoApp(root)
    root.mainloop()