"""
NPC Brain - Tum AI mantigi (STT, LLM, TTS, tool calling).
Turkce konusma destegi + tool call leak bug fix.
"""

import os
import re
import sys
import json
import asyncio
import tempfile
import threading
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from groq import Groq
import edge_tts
import pygame
from dotenv import load_dotenv

from game_state import state, execute_tool, TOOL_DEFINITIONS


# ====================== Config ======================
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY missing in .env")

LLM_MODEL = "llama-3.3-70b-versatile"
# Turkce icin multilingual model gerekli ('.en' degil)
# medium: small'dan belirgin daha dogru, RTX 2060 (6GB) rahat kaldirir
WHISPER_MODEL_SIZE = "medium"       # dogruluk: medium > small > base
WHISPER_LANGUAGE = "tr"             # Turkce
SAMPLE_RATE = 16000
NPCS_FILE = "npcs.json"

try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEVICE = "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"


# ====================== NPC ======================
class NPC:
    def __init__(self, npc_id, data):
        self.id = npc_id
        self.display_name = data["display_name"]
        self.voice = data["voice"]
        self.system_prompt = data["system_prompt"]
        self.clean_history = []
        self.x = data.get("x", 400)
        self.y = data.get("y", 300)
        self.color = tuple(data.get("color", [200, 200, 200]))

    def add_clean(self, role, content):
        self.clean_history.append({"role": role, "content": content})


def load_npcs():
    with open(NPCS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {npc_id: NPC(npc_id, d) for npc_id, d in data.items()}


# ====================== Bug fix: inline tool call parser ======================
# Llama bazen tool call'u text icine yaziyor. 3 farkli format gozlemlendi:
#   1. <function=name>{"args": ...}</function>            (klasik)
#   2. <function=name {"args": ...}</function>             (yarim)
#   3. <name='deger'> veya <name="deger">                  (cok kisa, JSON yok)
# Hepsini yakalayalim.
INLINE_FUNCTION_PATTERN = re.compile(
    r'<function=([\w_]+)>\s*(\{.*?\})\s*</function>', re.DOTALL
)
INLINE_FUNCTION_PATTERN_2 = re.compile(
    r'<function=([\w_]+)\s*(\{.*?\})\s*</function>', re.DOTALL
)
# 3. format: <name='X'> veya <name="X"> - basit etiket gibi
INLINE_SHORT_TAG_PATTERN = re.compile(
    r"<(\w+)=['\"]([^'\"]*)['\"]>", re.DOTALL
)
# Bilinen tool isimleri - kisa tag bunlardan biriyle eslesmeli
KNOWN_TOOLS = {"give_item", "take_gold", "give_gold", "offer_quest",
               "complete_quest", "check_inventory"}


def extract_inline_tool_calls(text: str):
    """Returns (cleaned_text, [(tool_name, args_dict), ...])"""
    tool_calls = []

    # Format 1 + 2 (klasik JSON'lu)
    for pat in (INLINE_FUNCTION_PATTERN, INLINE_FUNCTION_PATTERN_2):
        for name, args_str in pat.findall(text):
            try:
                args = json.loads(args_str)
                tool_calls.append((name, args))
            except json.JSONDecodeError:
                pass
        text = pat.sub('', text)

    # Format 3 (kisa tag, sadece bilinen tool isimleri icin)
    for name, value in INLINE_SHORT_TAG_PATTERN.findall(text):
        if name in KNOWN_TOOLS:
            # Tek deger - varsayilan parametre adina koy
            args = _guess_args_from_value(name, value)
            tool_calls.append((name, args))
    text = INLINE_SHORT_TAG_PATTERN.sub('', text)

    # Format 4: tool_name(arg='deger', arg2='deger') - Python fonksiyon cagrisi gibi
    func_call_pattern = re.compile(
        r'\b(' + '|'.join(KNOWN_TOOLS) + r')\s*\([^)]*\)',
        re.DOTALL
    )
    text = func_call_pattern.sub('', text)

    # Format 5: <herhangi bir XML benzeri tag> - cok agresif son temizleme
    text = re.sub(r'<[^>]{1,80}>', '', text)

    # Format 6: yalin parametre listesi gibi gorunen seyler ("price=40", "quantity='2'")
    # Bu cevabin ortasinda olmaz, sadece JSON kalintilari
    text = re.sub(r"\b(?:item_name|quantity|price|amount|quest_id|reward_gold|giver|title|description|reason)\s*=\s*['\"]?[\w_\-]+['\"]?", "", text)

    # Tool isimlerinin yalin gecislerinin ardindaki sayilari da temizle
    # Orn: "give_item 40" -> "" (bu durumda yalin tool ismi kalmis demektir)
    text = re.sub(r'\b(' + '|'.join(KNOWN_TOOLS) + r')\b\s*[:=]?\s*[\d\'\"]*', '', text)

    # JSON kalintisi suslu parantezler ortada kalmis olabilir
    text = re.sub(r'\{[^{}]{0,200}\}', '', text)

    # Cumle isaretlerini ve fazladan bosluklari temizle
    cleaned = re.sub(r'\s+([.!?,])', r'\1', text).strip()
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    # Cift noktalama temizle (".." -> ".", "!!" -> "!", "??" -> "?")
    cleaned = re.sub(r'([.!?,])\1+', r'\1', cleaned)
    return cleaned, tool_calls


def _guess_args_from_value(tool_name: str, value: str) -> dict:
    """Kisa tag formatinda sadece 1 deger var, parametre adini tahmin et."""
    # Sayisalsa price/amount/quantity olabilir
    is_num = value.replace("-", "").isdigit()
    if tool_name == "give_item":
        # <give_item='40'> -> price 40 olabilir
        if is_num:
            return {"item_name": "bilinmiyor", "price": value, "quantity": "1"}
        return {"item_name": value, "quantity": "1", "price": "0"}
    if tool_name in ("take_gold", "give_gold"):
        return {"amount": value if is_num else "0"}
    if tool_name == "complete_quest":
        return {"quest_id": value}
    return {}


# ====================== Brain ======================
class NPCBrain:
    def __init__(self):
        print(f"[brain] Whisper yukleniyor ({WHISPER_MODEL_SIZE}, {DEVICE}, dil={WHISPER_LANGUAGE})...")
        self.whisper = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("[brain] Whisper hazir")

        self.groq = Groq(api_key=GROQ_API_KEY)
        print("[brain] Groq hazir")

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.recorder = AudioRecorder()

    def start_recording(self):
        self.recorder.start()

    def stop_recording(self) -> np.ndarray:
        return self.recorder.stop()

    def transcribe(self, audio: np.ndarray) -> str:
        # Cok kisa ses = bos
        if len(audio) < SAMPLE_RATE * 0.4:
            return ""

        # Oyun baglami - Whisper'a beklenen kelimeleri ogret (Turkce halusinasyon azaltir)
        game_context = (
            "Bu bir fantastik rol yapma oyunu. Oyuncu saticilarla konusuyor. "
            "Sik kullanilan kelimeler: iksir, kilic, zirh, saglik iksiri, mana iksiri, "
            "altin, gorev, satin almak, almak, kac para, fiyat, merhaba, tesekkurler, "
            "ekipman, ısınlanmak, buyucu, han, muhafiz."
        )

        segments, info = self.whisper.transcribe(
            audio,
            language=WHISPER_LANGUAGE,
            initial_prompt=game_context,     # baglam ver
            beam_size=5,                      # daha genis arama (1 yerine 5) = daha dogru
            best_of=5,                        # 5 aday uret, en iyisini sec
            temperature=0.0,                  # deterministik (halusinasyon az)
            condition_on_previous_text=False, # onceki halusinasyonlari tasima
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=300,  # 300ms sessizlik = kelime sonu (cok agresif kesmesin)
                speech_pad_ms=200,            # konusmanin bas/sonuna 200ms ekle (kelime kesilmesin)
            ),
        )
        text = " ".join(seg.text for seg in segments).strip()
        # Whisper bazen tekrar eden halusinasyon uretir ("...iksir iksir iksir")
        text = self._clean_transcript(text)
        return text

    @staticmethod
    def _clean_transcript(text: str) -> str:
        """STT ciktisindaki yaygin halusinasyonlari temizle."""
        if not text:
            return ""
        # Ayni kelimenin 3+ kez ust uste tekrarini teke indir
        words = text.split()
        cleaned_words = []
        for w in words:
            # Son 2 kelime ile ayniysa atla (tekrar halusinasyonu)
            if len(cleaned_words) >= 2 and cleaned_words[-1] == w and cleaned_words[-2] == w:
                continue
            cleaned_words.append(w)
        result = " ".join(cleaned_words).strip()
        # Whisper'in tipik bos halusinasyonlari
        garbage = ["altyazı", "altyazi", "izlediğiniz için teşekkürler",
                   "abone olmayı unutmayın", "teşekkür ederim.", "."]
        low = result.lower().strip()
        if low in garbage or len(low) < 2:
            return ""
        return result

    def chat(self, npc: NPC, user_text: str, action_log: Optional[Callable] = None) -> str:
        """Tool calling akisi + inline tool leak yakalama + dayaniklilik."""
        # ----- Bos/cok kisa girdi korumasi -----
        cleaned_input = (user_text or "").strip()
        if len(cleaned_input) < 2:
            fallback = "Pardon, tam duyamadım. Tekrar eder misin?"
            npc.add_clean("user", user_text or "(bos)")
            npc.add_clean("assistant", fallback)
            return fallback

        try:
            return self._chat_inner(npc, cleaned_input, action_log)
        except Exception as e:
            print(f"[chat] HATA yakalandi, karakterde kalan fallback: {e}")
            # Tool/LLM patlasa bile NPC karakterde kalip cevap versin
            fallback = self._safe_fallback_reply(npc, cleaned_input)
            npc.add_clean("user", cleaned_input)
            npc.add_clean("assistant", fallback)
            return fallback

    def _safe_fallback_reply(self, npc: NPC, user_text: str) -> str:
        """Tool/LLM hatasinda - tool'suz, basit bir LLM cagrisi ile karakterde cevap."""
        try:
            resp = self.groq.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": npc.system_prompt},
                    {"role": "system", "content": "Kisa, karakterde, 1 cumlelik bir cevap ver. Fonksiyon/arac KULLANMA, sadece sohbet et."},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=80,
                temperature=0.7,
            )
            txt = (resp.choices[0].message.content or "").strip()
            txt, _ = extract_inline_tool_calls(txt)
            return txt or "Hımm, bir terslik oldu. Tekrar sorar mısın?"
        except Exception:
            return "Kafam biraz karıştı, tekrar sorabilir misin?"

    def _chat_inner(self, npc: NPC, user_text: str, action_log: Optional[Callable] = None) -> str:
        """Asil tool calling akisi."""
        temp_messages = [{"role": "system", "content": npc.system_prompt}]
        temp_messages.append({"role": "system", "content": f"OYUNCU DURUMU: {state.summary_tr()}"})
        temp_messages.append({"role": "system", "content":
            "KRITIK KURALLAR:\n"
            "1) Eger oyuncu sat-al/ver/gorev/envanter gibi BIR EYLEM istiyorsa, MUTLAKA "
            "uygun araci (tool) cagir. Sadece konusma metniyle 'yaptim' deme - o zaman "
            "gercek aksiyon olmaz, oyuncu eshasini almaz, altini eksilmez. Sistem ancak "
            "tool cagrildiginda durumu gunceller.\n"
            "2) Selamlama, sohbet, dedikodu gibi durumlarda tool cagirma, sadece konus.\n"
            "3) Cevabin 1-2 KISA cumle olsun, dogal Turkce, fonksiyon syntax'i YAZMA.\n"
            "4) Oyuncuyu tam anlamadiysan kibarca tekrar isteyebilirsin, uydurma."})
        temp_messages.extend(npc.clean_history[-10:])
        temp_messages.append({"role": "user", "content": user_text})

        response = self.groq.chat.completions.create(
            model=LLM_MODEL,
            messages=temp_messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            max_tokens=300,
            temperature=0.6,
        )
        msg = response.choices[0].message
        structured_tool_calls = msg.tool_calls or []
        content_text = msg.content or ""

        # Inline tool call leak'i yakala
        cleaned_text, inline_calls = extract_inline_tool_calls(content_text)

        if structured_tool_calls or inline_calls:
            # Structured ones via official path
            if structured_tool_calls:
                temp_messages.append({
                    "role": "assistant",
                    "content": cleaned_text or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in structured_tool_calls
                    ],
                })

                for tc in structured_tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    result = execute_tool(tc.function.name, args)
                    if action_log:
                        action_log(tc.function.name, args, result)
                    temp_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            # Inline ones - LLM leak, manual execution
            if inline_calls:
                temp_messages.append({
                    "role": "assistant",
                    "content": cleaned_text or "(fonksiyon cagrildi)",
                })
                for name, args in inline_calls:
                    result = execute_tool(name, args)
                    if action_log:
                        action_log(name + " (inline)", args, result)
                    temp_messages.append({
                        "role": "user",
                        "content": f"[Sistem notu] '{name}' calistirildi: {json.dumps(result, ensure_ascii=False)}. Lutfen kisa rolun-cevabini ver, fonksiyon syntax'i YAZMA."
                    })

            # 2. cagri - tool YAZMASIN
            final_response = self.groq.chat.completions.create(
                model=LLM_MODEL,
                messages=temp_messages,
                max_tokens=100,
                temperature=0.6,
            )
            reply = (final_response.choices[0].message.content or "").strip()
            reply, _ = extract_inline_tool_calls(reply)
            if not reply:
                reply = "Tamamdır."
        else:
            reply = cleaned_text if cleaned_text else "Pardon, tam anlamadım. Tekrar eder misin?"

        npc.add_clean("user", user_text)
        npc.add_clean("assistant", reply)
        return reply

    def speak(self, text: str, voice: str, blocking: bool = True):
        if blocking:
            asyncio.run(self._speak_async(text, voice))
        else:
            t = threading.Thread(target=lambda: asyncio.run(self._speak_async(text, voice)), daemon=True)
            t.start()
            return t

    async def _speak_async(self, text: str, voice: str):
        if not text.strip():
            return
        # Text'in UTF-8 normalize oldugundan emin ol
        text = str(text).strip()
        # Bazi sistemlerde latin-1 fallback Turkce karakterleri bozar - manuel normalize
        try:
            text = text.encode('utf-8').decode('utf-8')
        except Exception:
            pass

        print(f"[tts] voice={voice}, rate=+25%, text='{text[:60]}'")
        import sys as _sys
        _sys.stdout.flush()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            path = f.name
        try:
            await edge_tts.Communicate(text, voice, rate="+25%").save(path)
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


# ====================== Audio Recorder ======================
class AudioRecorder:
    def __init__(self):
        self.chunks = []
        self.recording = False
        self.stream = None
        self._lock = threading.Lock()

    def _cb(self, indata, frames, time_info, status):
        with self._lock:
            if self.recording:
                self.chunks.append(indata.copy())

    def start(self):
        with self._lock:
            self.chunks = []
            self.recording = True
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1,
            dtype='float32', callback=self._cb,
        )
        self.stream.start()

    def stop(self) -> np.ndarray:
        with self._lock:
            self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if not self.chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(self.chunks, axis=0).flatten()
