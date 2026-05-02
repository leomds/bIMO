import io
import base64
import pygame

def play_audio_b64(audio_b64: str):
    audio_bytes = base64.b64decode(audio_b64)
    buf = io.BytesIO(audio_bytes)
    
    if not pygame.mixer.get_init():
        pygame.mixer.init()
        
    pygame.mixer.music.load(buf)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)