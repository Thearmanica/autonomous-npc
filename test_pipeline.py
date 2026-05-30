"""
Otonom NPC - Ses Pipeline Testi (Day 1)
========================================
Mikrofon -> Whisper (STT) -> Groq (LLM) -> Edge TTS -> Hoparlör

Kullanım:
  1. .env dosyasına GROQ_API_KEY=... ekle (https://console.groq.com/keys)
  2. python test_pipeline.py
  3. ENTER bas, konuş, tekrar ENTER bas (kayıt durur)
  4. NPC sesli cevap verecek
  5. Ctrl+C ile çıkış
"""

import os
import sys
import asyncio
import tempfile
import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from groq import Groq
import edge_tts
import pygame
from dotenv import load_dotenv

# ====================== Config ======================
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("HATA: GROQ_API_KEY yok. .env dosyasi olusturup ekle.")
    print("Ucretsiz key: https://console.groq.com/keys")
    sys.exit(1)

# Llama 3.3 70B = kalite. Daha hizli isteyince llama-3.1-8b-instant kullan.
LLM_MODEL = "llama-3.3-70b-versatile"
WHISPER_MODEL_SIZE = "small.en"      # base.en daha hizli, daha az dogru
TTS_VOICE = "en-GB-RyanNeural"        # Alternatif: en-US-GuyNeural, en-GB-SoniaNeural
SAMPLE_RATE = 16000

# GPU yoksa otomatik CPU'ya dus
try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEVICE = "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# ====================== NPC Persona ======================
NPC_PERSONA = """You are Gareth, a gruff old blacksmith in the fantasy village of Eldermoor.
You forge swords and armor. You are blunt, sometimes sarcastic, but secretly kind to those who earn your respect.

STRICT RULES:
- Reply in 1-2 SHORT sentences only. Never more.
- Stay fully in character. You do not know about modern things (cars, internet, phones).
- Use mild fantasy speech ("aye", "lad", "by the forge", "hmph").
- If the player is rude, push back. If they're polite, warm up slightly.
"""

# ====================== Setup ======================
print(f"[setup] Whisper yukleniyor ({WHISPER_MODEL_SIZE}, {DEVICE})...")
whisper = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("[setup] Whisper hazir")

groq_client = Groq(api_key=GROQ_API_KEY)
print("[setup] Groq hazir")

pygame.mixer.init()
print("[setup] Ses cikis hazir\n")

conversation_history = []

# ====================== Pipeline ======================
def record_until_enter() -> np.ndarray:
    """ENTER -> kayit basla. ENTER -> kayit dur."""
    print("\n[mic] ENTER bas ve konusmaya basla...")
    input()
    print("[mic] KAYIT... (durdurmak icin ENTER)")

    chunks = []
    stop = threading.Event()

    def cb(indata, frames, time_info, status):
        if not stop.is_set():
            chunks.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                         dtype='float32', callback=cb):
        input()
        stop.set()

    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks, axis=0).flatten()


def transcribe(audio: np.ndarray) -> str:
    segments, _ = whisper.transcribe(audio, language="en", vad_filter=True)
    return " ".join(seg.text for seg in segments).strip()


def get_npc_response(user_text: str) -> str:
    conversation_history.append({"role": "user", "content": user_text})
    # Son 10 turu tut (token tasarrufu)
    messages = [{"role": "system", "content": NPC_PERSONA}] + conversation_history[-10:]

    resp = groq_client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=80,
        temperature=0.8,
    )
    reply = resp.choices[0].message.content.strip()
    conversation_history.append({"role": "assistant", "content": reply})
    return reply


async def _speak_async(text: str):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    try:
        await edge_tts.Communicate(text, TTS_VOICE).save(path)
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def speak(text: str):
    asyncio.run(_speak_async(text))


# ====================== Main loop ======================
def main():
    print("=" * 50)
    print("NPC: Gareth the Blacksmith")
    print("Cikis: Ctrl+C")
    print("=" * 50)

    while True:
        try:
            audio = record_until_enter()
            if len(audio) < SAMPLE_RATE * 0.4:
                print("[!] Cok kisa, tekrar dene.")
                continue

            print("[stt] Yaziya cevriliyor...")
            user_text = transcribe(audio)
            if not user_text:
                print("[!] Hicbir sey duyulamadi.")
                continue
            print(f"\n  Sen      : {user_text}")

            print("[llm] Dusunuyor...")
            reply = get_npc_response(user_text)
            print(f"  Gareth   : {reply}\n")

            print("[tts] Konusuluyor...")
            speak(reply)

        except KeyboardInterrupt:
            print("\n[bye] Forge soguyor. Gule gule.")
            break
        except Exception as e:
            print(f"[!] Hata: {e}")
            continue


if __name__ == "__main__":
    main()
