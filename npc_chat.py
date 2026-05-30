"""
Terminal modu - sadece UI. AI mantigi npc_brain.py'de.
SPACE basili tut + konus + birak.
"""

import sys
import threading
from pynput import keyboard

from npc_brain import NPCBrain, load_npcs
from game_state import state

# ====================== Setup ======================
brain = NPCBrain()
npcs = load_npcs()
print(f"[setup] {len(npcs)} NPC yuklendi")
print(f"[state] {state.summary()}\n")


# ====================== Push-to-talk (pynput tabanli, terminal icin) ======================
class TerminalRecorder:
    def __init__(self, brain):
        self.brain = brain
        self.released = threading.Event()
        self.is_recording = False

    def _on_press(self, key):
        if key == keyboard.Key.space and not self.is_recording:
            self.is_recording = True
            self.brain.start_recording()
            print("[mic] KAYIT... (birak: dur)")

    def _on_release(self, key):
        if key == keyboard.Key.space and self.is_recording:
            self.is_recording = False
            self.released.set()
            return False
        if key == keyboard.Key.esc:
            self.released.set()
            return False

    def record_once(self):
        print("[mic] SPACE basili tut + konus, birakinca dur")
        self.released.clear()
        listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        listener.start()
        self.released.wait()
        listener.stop()
        if not self.is_recording:
            return self.brain.stop_recording()
        return self.brain.stop_recording()


recorder = TerminalRecorder(brain)


# ====================== UI ======================
def choose_npc():
    print("=" * 50)
    print("Konusmak istedigin NPC'yi sec:")
    npc_list = list(npcs.values())
    for i, npc in enumerate(npc_list, 1):
        print(f"  {i}. {npc.display_name}")
    print("=" * 50)
    while True:
        choice = input(f"Numara (1-{len(npc_list)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(npc_list):
            return npc_list[int(choice) - 1]


def action_log_handler(name, args, result):
    msg = result.get("message") or result.get("reason") or str(result)
    print(f"  [ACTION]    {name}({args}) -> {msg}")


def main():
    current_npc = choose_npc()
    print(f"\n[chat] {current_npc.display_name} ile konusuyorsun")
    print("[chat] Sesli komutlar: 'değiştir' / 'çıkış' / 'sıfırla'\n")

    while True:
        try:
            audio = recorder.record_once()
            print("[stt] Yaziya cevriliyor...")
            user_text = brain.transcribe(audio)
            if not user_text:
                print("[!] Hicbir sey duyulamadi\n")
                continue
            print(f"\n  Sen        : {user_text}")

            lowered = user_text.lower().strip(" .,!?")
            if lowered in ("değiştir", "karakter değiştir", "başka"):
                current_npc = choose_npc()
                print(f"\n[chat] {current_npc.display_name} ile konusuyorsun\n")
                continue
            if lowered in ("çıkış", "kapat", "güle güle", "bitir"):
                print("[bye]")
                break
            if lowered in ("sıfırla", "baştan başla"):
                state.reset()
                print(f"[state] Sifirlandi -> {state.summary()}\n")
                continue

            print("[llm] Dusunuyor...")
            reply = brain.chat(current_npc, user_text, action_log=action_log_handler)
            print(f"  {current_npc.display_name:18} : {reply}")
            print(f"  [STATE]    {state.summary()}\n")

            print("[tts] Konusuluyor...")
            brain.speak(reply, current_npc.voice, blocking=True)

        except KeyboardInterrupt:
            print("\n[bye]")
            break
        except Exception as e:
            print(f"[!] Hata: {e}\n")
            continue


if __name__ == "__main__":
    main()
