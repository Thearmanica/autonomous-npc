"""
Performans Olcum Script'i
=========================
Otonom NPC sisteminin STT (Whisper), LLM (Groq) ve TTS (Edge TTS)
gecikme surelerini olcer ve grafik olarak cikartir.

Tez raporundaki "Sonuclar" bolumunde kullanilacak gercek olcumler.

Kullanim:
    python benchmark.py

Cikti:
    - benchmark_results.json   : ham olcum verileri
    - benchmark_latency.png    : kutudiyagrami + bar chart
    - benchmark_summary.txt    : istatistik ozeti
"""

import os
import sys
import time
import json
import io
import wave
import asyncio
import tempfile
import numpy as np

# matplotlib lazy import - sadece grafikte
print("[bench] Yukleniyor...")
sys.stdout.flush()

# Brain modulu (sistem ayarlarini kullanir)
from npc_brain import NPCBrain, load_npcs
from game_state import state

# ====================== TEST CUMLELERI ======================
# 4 farkli sahne: alışveriş, görev, sohbet, ışınlama
TEST_SCENARIOS = [
    {
        "npc_id": "iksirci",
        "user_text": "Merhaba, bir sağlık iksiri almak istiyorum.",
        "expected": "tool",  # give_item bekleniyor
        "description": "İksir alışverişi",
    },
    {
        "npc_id": "demirci",
        "user_text": "Bana bir kılıç ver, ne kadar?",
        "expected": "tool",  # give_item
        "description": "Kılıç alışverişi",
    },
    {
        "npc_id": "muhafiz",
        "user_text": "Selam, bana bir görev verebilir misin?",
        "expected": "tool",  # offer_quest
        "description": "Görev verme",
    },
    {
        "npc_id": "hanci",
        "user_text": "Köyde son zamanlarda ne oluyor?",
        "expected": "chat",  # sadece sohbet
        "description": "Sohbet (no tool)",
    },
    {
        "npc_id": "isinlayici",
        "user_text": "Beni Buz Krallığı'na ışınlayabilir misin?",
        "expected": "chat",  # nazik ret
        "description": "Işınlama isteği",
    },
    {
        "npc_id": "iksirci",
        "user_text": "Mana iksirin var mı?",
        "expected": "chat",  # konuşma + muhtemel tool
        "description": "Ürün sorgusu",
    },
    {
        "npc_id": "demirci",
        "user_text": "Zırhın ne kadar?",
        "expected": "chat",
        "description": "Fiyat sorgusu",
    },
    {
        "npc_id": "muhafiz",
        "user_text": "Köy güvenli mi?",
        "expected": "chat",
        "description": "Güvenlik sorusu",
    },
]


# ====================== TTS ile referans ses uret ======================
import edge_tts

async def _tts_to_wav(text: str, voice: str = "tr-TR-EmelNeural") -> np.ndarray:
    """Referans bir Turkce sesi mp3 olarak uret, sonra 16kHz mono numpy array'e cevir."""
    import io
    # Edge TTS ile mp3 stream
    communicate = edge_tts.Communicate(text, voice, rate="+25%")
    mp3_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes += chunk["data"]

    # mp3'u wav'a cevir (pydub veya ffmpeg ile)
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
        seg = seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        samples = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
        return samples
    except ImportError:
        print("[bench] HATA: pydub yok. pip install pydub")
        sys.exit(1)


def make_test_audio(text: str) -> np.ndarray:
    """Test cumlesini referans TTS ile sese cevirip Whisper'a sun."""
    return asyncio.run(_tts_to_wav(text))


# ====================== Benchmark ======================
def benchmark_scenario(brain: NPCBrain, npcs: dict, scenario: dict) -> dict:
    npc = npcs[scenario["npc_id"]]
    user_text = scenario["user_text"]
    expected = scenario["expected"]

    print(f"\n--- {scenario['description']} ({npc.display_name}) ---")
    print(f"    Girdi: \"{user_text}\"")
    sys.stdout.flush()

    result = {
        "scenario": scenario["description"],
        "npc": npc.display_name,
        "user_text": user_text,
        "expected": expected,
    }

    # ===== 1. STT timing =====
    print("    [1/3] STT olculuyor (TTS->Whisper)...")
    sys.stdout.flush()
    audio = make_test_audio(user_text)

    t0 = time.perf_counter()
    transcribed = brain.transcribe(audio)
    stt_time = time.perf_counter() - t0
    print(f"        STT: {stt_time*1000:.0f}ms  ->  \"{transcribed}\"")
    sys.stdout.flush()
    result["stt_ms"] = stt_time * 1000
    result["transcribed"] = transcribed

    # STT dogruluk - basit similarity (kelime kesisimi)
    if transcribed:
        orig_words = set(user_text.lower().replace(",", "").replace(".", "").replace("?", "").split())
        new_words = set(transcribed.lower().replace(",", "").replace(".", "").replace("?", "").split())
        if orig_words:
            similarity = len(orig_words & new_words) / len(orig_words)
        else:
            similarity = 0.0
    else:
        similarity = 0.0
    result["stt_accuracy"] = similarity * 100
    print(f"        STT dogruluk: %{similarity*100:.0f}")
    sys.stdout.flush()

    # ===== 2. LLM timing =====
    print("    [2/3] LLM olculuyor (Groq)...")
    sys.stdout.flush()
    tool_called = [False]

    def log_action(name, args, res):
        tool_called[0] = True

    t0 = time.perf_counter()
    reply = brain.chat(npc, transcribed or user_text, action_log=log_action)
    llm_time = time.perf_counter() - t0
    print(f"        LLM: {llm_time*1000:.0f}ms  (tool={tool_called[0]})")
    print(f"        Cevap: \"{reply[:80]}\"")
    sys.stdout.flush()
    result["llm_ms"] = llm_time * 1000
    result["llm_reply"] = reply
    result["tool_called"] = tool_called[0]

    # ===== 3. TTS timing =====
    print("    [3/3] TTS olculuyor (Edge TTS)...")
    sys.stdout.flush()
    # TTS ses dosyasi UReTME suresi (oynatma degil)
    t0 = time.perf_counter()
    asyncio.run(_tts_to_wav(reply, npc.voice))
    tts_time = time.perf_counter() - t0
    print(f"        TTS: {tts_time*1000:.0f}ms")
    sys.stdout.flush()
    result["tts_ms"] = tts_time * 1000

    # Toplam end-to-end
    result["total_ms"] = result["stt_ms"] + result["llm_ms"] + result["tts_ms"]
    print(f"    >> TOPLAM: {result['total_ms']:.0f}ms")
    sys.stdout.flush()

    return result


def print_summary(results: list, fp=sys.stdout):
    """Istatistik ozeti yazdir."""
    stt = [r["stt_ms"] for r in results]
    llm = [r["llm_ms"] for r in results]
    tts = [r["tts_ms"] for r in results]
    total = [r["total_ms"] for r in results]
    acc = [r["stt_accuracy"] for r in results]
    tool_count = sum(1 for r in results if r["tool_called"])

    def stats(arr, name, unit="ms"):
        a = np.array(arr)
        return (f"  {name:18s} "
                f"ort={a.mean():.0f}{unit:3s} "
                f"med={np.median(a):.0f}{unit:3s} "
                f"min={a.min():.0f}{unit:3s} "
                f"max={a.max():.0f}{unit:3s} "
                f"std={a.std():.0f}{unit:3s}")

    print("\n" + "=" * 70, file=fp)
    print(f"PERFORMANS OZETI - {len(results)} senaryo", file=fp)
    print("=" * 70, file=fp)
    print(stats(stt, "STT (Whisper)"), file=fp)
    print(stats(llm, "LLM (Groq)"), file=fp)
    print(stats(tts, "TTS (Edge)"), file=fp)
    print(stats(total, "TOPLAM"), file=fp)
    print(stats(acc, "STT dogruluk", "%"), file=fp)
    print(f"  Tool call basari: {tool_count}/{len(results)}", file=fp)
    print("=" * 70, file=fp)


def make_chart(results: list, out_path: str):
    """matplotlib ile grafik uret."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt
    except ImportError:
        print("[bench] UYARI: matplotlib yok, grafik atlandi. pip install matplotlib")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # === Sol: senaryo bazinda yığılmış bar chart ===
    labels = [r["scenario"] for r in results]
    stt_vals = [r["stt_ms"] for r in results]
    llm_vals = [r["llm_ms"] for r in results]
    tts_vals = [r["tts_ms"] for r in results]
    x = np.arange(len(labels))

    ax1.bar(x, stt_vals, label="STT (Whisper)", color="#3b82f6")
    ax1.bar(x, llm_vals, bottom=stt_vals, label="LLM (Groq)", color="#10b981")
    ax1.bar(x, tts_vals, bottom=[s + l for s, l in zip(stt_vals, llm_vals)],
            label="TTS (Edge)", color="#f59e0b")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax1.set_ylabel("Süre (ms)")
    ax1.set_title("Senaryo Bazında End-to-End Gecikme")
    ax1.legend()
    ax1.grid(axis="y", linestyle="--", alpha=0.4)

    # === Sag: kutudiyagrami (her bilesen) ===
    data = [stt_vals, llm_vals, tts_vals]
    bp = ax2.boxplot(data, labels=["STT", "LLM", "TTS"], patch_artist=True)
    colors = ["#3b82f6", "#10b981", "#f59e0b"]
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)
    ax2.set_ylabel("Süre (ms)")
    ax2.set_title("Bileşen Gecikme Dağılımı")
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    print(f"[bench] Grafik kaydedildi: {out_path}")


def main():
    print("=" * 70)
    print("Otonom NPC Sistemi - Performans Olcum")
    print("=" * 70)

    # AI brain yukle
    brain = NPCBrain()
    npcs = load_npcs()

    # Sonuclar
    results = []
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n[{i}/{len(TEST_SCENARIOS)}]", end="")
        try:
            r = benchmark_scenario(brain, npcs, scenario)
            results.append(r)
        except Exception as e:
            print(f"    HATA: {type(e).__name__}: {e}")
            sys.stdout.flush()

    # JSON kaydet
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\n[bench] JSON kaydedildi: benchmark_results.json")

    # Ozet
    print_summary(results)
    with open("benchmark_summary.txt", "w", encoding="utf-8") as f:
        print_summary(results, fp=f)
    print("[bench] Ozet kaydedildi: benchmark_summary.txt")

    # Grafik
    make_chart(results, "benchmark_latency.png")

    print("\nBenchmark tamamlandi.")


if __name__ == "__main__":
    main()
