"""
Ursina 3D NPC Demo - TEST 6 TABANLI (calistigi kanitlanmis)
==========================================================
Test 6 calistigi icin onun yapisina sadik kaliyoruz.
Bacaklar/kollar yok - sade gobek + kafa NPC.
"""

import sys
import os
import math
import threading
from enum import Enum

# DPI awareness (Windows)
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


print("=" * 60)
print("[1/3] AI Brain hazirlaniyor...")
print("=" * 60)
sys.stdout.flush()

from npc_brain import NPCBrain, load_npcs
from game_state import state

brain = NPCBrain()
print("[1/3] AI Brain HAZIR")
sys.stdout.flush()

npcs_dict = load_npcs()
print(f"[2/3] {len(npcs_dict)} NPC yuklendi")
sys.stdout.flush()


print("[3/3] Ursina baslatiliyor...")
sys.stdout.flush()

from panda3d.core import loadPrcFileData, WindowProperties
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen 0')

from ursina import (
    Ursina, Entity, Text, color, camera, mouse, window, application,
)
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()
print("[3/3] Ursina HAZIR\n")
sys.stdout.flush()


# ====================== Config ======================
INTERACT_RADIUS = 5


class DialogState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SPEAKING = "speaking"


# ====================== Mouse helper ======================
def set_cursor_visible(visible):
    try:
        wp = WindowProperties()
        wp.setCursorHidden(not visible)
        wp.setMouseMode(WindowProperties.M_absolute if visible else WindowProperties.M_relative)
        application.base.win.requestProperties(wp)
    except Exception as e:
        print(f"[mouse] error: {e}")


# ====================== WORLD - Test 6 stilinde ======================
# Zemin (yol haci yok - z-fighting sorunu olabiliyor)
ground = Entity(model='cube', color=color.rgb(80, 130, 70),
                scale=(60, 0.1, 60), position=(0, -0.05, 0), collider='box')


def make_building(x, z, c):
    """Test 6'daki basit bina."""
    Entity(model='cube', color=color.rgb(*c),
           scale=(6, 3.5, 6), position=(x, 1.75, z), collider='box')
    Entity(model='cube', color=color.rgb(150, 60, 50),
           scale=(7, 0.5, 7), position=(x, 3.7, z), rotation=(0, 45, 0))
    # Kapi - on tarafa (NPC tarafina)
    Entity(model='cube', color=color.rgb(60, 40, 25),
           scale=(1.2, 2, 0.2), position=(x, 1, z - 3.1))


def npc_world_pos(npc_2d_x, npc_2d_y):
    # NPC'leri daha yakin tut - kameradan gorulebilsin
    x = (npc_2d_x - 500) / 35.0
    z = (npc_2d_y - 350) / 35.0
    return x, z


# ====================== NPC Actor - SADE (Test 6 stilinde) ======================
class NPCActor:
    def __init__(self, npc_data):
        self.data = npc_data
        x, z = npc_world_pos(npc_data.x, npc_data.y)
        c = npc_data.color

        # Bina arkada (NPC'den uzakta)
        building_c = (max(c[0] - 30, 40), max(c[1] - 30, 40), max(c[2] - 30, 40))
        make_building(x, z + 4, building_c)

        # NPC binanin onunde - SADECE govde + kafa + label (Test 6 ile aynisi)
        nx, nz = x, z

        # Govde - NPC rengi
        self.body = Entity(model='cube', color=color.rgb(*c),
                           scale=(1.1, 1.3, 0.7), position=(nx, 1.6, nz),
                           collider='box')

        # Kafa - ten rengi
        Entity(model='sphere', color=color.rgb(230, 190, 160),
               scale=0.6, position=(nx, 2.55, nz))

        # Label - parent=body (Test 6 ile aynisi)
        Text(npc_data.display_name, position=(0, 3.2, 0), parent=self.body,
             scale=20, billboard=True, background=True, color=color.white)


# 4 NPC olustur
actors = [NPCActor(npc) for npc in npcs_dict.values()]
print(f"[world] {len(actors)} NPC olusturuldu")


# ====================== Player ======================
player_ctrl = FirstPersonController(position=(0, 1, 0), speed=8)


# ====================== Dialog Manager ======================
class DialogManager:
    def __init__(self, brain):
        self.brain = brain
        self.current_npc = None
        self.state = DialogState.IDLE
        self.last_user_text = ""
        self.last_npc_reply = ""
        self.last_action = ""
        self.notification = ""
        self.notification_until = 0.0

    def enter(self, npc):
        self.current_npc = npc
        self.state = DialogState.IDLE
        self.last_user_text = ""
        self.last_npc_reply = ""
        self.last_action = ""
        player_ctrl.enabled = False
        set_cursor_visible(True)
        print(f"\n[dialog] {npc.display_name} ile konusuyorsun")

    def exit_dialog(self):
        if self.state in (DialogState.RECORDING, DialogState.PROCESSING, DialogState.SPEAKING):
            return False
        self.current_npc = None
        self.state = DialogState.IDLE
        set_cursor_visible(False)
        player_ctrl.enabled = True
        print("[dialog] cikildi\n")
        return True

    def start_recording(self):
        if self.state != DialogState.IDLE:
            return
        self.state = DialogState.RECORDING
        self.brain.start_recording()

    def stop_recording_and_process(self):
        if self.state != DialogState.RECORDING:
            return
        audio = self.brain.stop_recording()
        self.state = DialogState.PROCESSING
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio):
        try:
            user_text = self.brain.transcribe(audio)
            if not user_text:
                self.last_user_text = "(anlasilmadi)"
                self.state = DialogState.IDLE
                return
            self.last_user_text = user_text
            print(f"  Sen: {user_text}")

            def log_action(name, args, result):
                msg = result.get("message") or result.get("reason") or ""
                self.last_action = f"{name} -> {msg[:60]}"
                print(f"  [AKSIYON] {name}({args}) -> {msg}")
                if result.get("success"):
                    self._set_notification(name, args, result)

            reply = self.brain.chat(self.current_npc, user_text, action_log=log_action)
            self.last_npc_reply = reply
            print(f"  {self.current_npc.display_name}: {reply}")
            print(f"  [DURUM] {state.summary_tr()}")
            self.state = DialogState.SPEAKING
            self.brain.speak(reply, self.current_npc.voice, blocking=True)
        except Exception as e:
            print(f"[!] Dialog error: {e}")
            self.last_npc_reply = "(hata)"
        finally:
            self.state = DialogState.IDLE

    def _set_notification(self, name, args, result):
        import time
        text = None
        if name == "give_item":
            text = f"+ {args.get('quantity', 1)}x {args.get('item_name', '?')}"
            if args.get('price', 0) > 0:
                text += f"  (-{args['price']} altin)"
        elif name == "take_gold":
            text = f"- {args.get('amount', 0)} altin"
        elif name == "give_gold":
            text = f"+ {args.get('amount', 0)} altin"
        elif name == "offer_quest":
            text = f"Yeni gorev: {args.get('title', '?')}"
        elif name == "complete_quest":
            text = "Gorev tamamlandi!"
        if text:
            self.notification = text
            self.notification_until = time.time() + 3.0


dialog = DialogManager(brain)


# ====================== UI ======================
hud_text = Text(text='', position=(-0.86, 0.48), scale=1, color=color.white,
                background=True, origin=(-0.5, 0.5))

notification_text = Text(text='', position=(0.55, 0.45), scale=1.3,
                         color=color.rgb(255, 240, 150), background=True,
                         origin=(-0.5, 0.5), enabled=False)

dialog_name = Text(parent=camera.ui, text='', position=(-0.82, -0.18), scale=1.5,
                   color=color.rgb(220, 180, 100), background=True, enabled=False)
dialog_status = Text(parent=camera.ui, text='', position=(0.45, -0.18), scale=1,
                     color=color.light_gray, background=True, enabled=False)
dialog_user = Text(parent=camera.ui, text='', position=(-0.82, -0.27), scale=0.9,
                   color=color.rgb(200, 200, 220), background=True, enabled=False)
dialog_npc = Text(parent=camera.ui, text='', position=(-0.82, -0.36), scale=0.9,
                  color=color.rgb(255, 240, 200), background=True, enabled=False)

near_hint = Text(parent=camera.ui, text='', position=(0, -0.05), scale=1.4,
                 color=color.yellow, background=True, enabled=False, origin=(0, 0))


def find_nearby_actor():
    px, _, pz = player_ctrl.position
    nearest = None
    nearest_dist = INTERACT_RADIUS
    for a in actors:
        bx, _, bz = a.body.position
        dist = math.hypot(px - bx, pz - bz)
        if dist < nearest_dist:
            nearest = a
            nearest_dist = dist
    return nearest


_last_hud_text = [""]


def update_hud():
    inv = ", ".join(f"{k} x{v}" for k, v in state.inventory.items()) or "(bos)"
    quests = ", ".join(q["title"] for q in state.active_quests) or "(yok)"
    new_text = f"Altin: {state.gold}\nEnvanter: {inv[:40]}\nGorevler: {quests[:40]}"
    if _last_hud_text[0] != new_text:
        hud_text.text = new_text
        _last_hud_text[0] = new_text


def update_notification():
    import time
    if dialog.notification and time.time() < dialog.notification_until:
        notification_text.text = dialog.notification
        notification_text.enabled = True
    else:
        notification_text.enabled = False


def update_dialog_ui():
    show = dialog.current_npc is not None
    for e in [dialog_name, dialog_status, dialog_user, dialog_npc]:
        e.enabled = show
    if not show:
        return
    dialog_name.text = dialog.current_npc.display_name
    status_map = {
        DialogState.IDLE: ("SPACE basili tut + konus + birak", color.light_gray),
        DialogState.RECORDING: ("DINLENIYOR...", color.red),
        DialogState.PROCESSING: ("Dusunuyor...", color.yellow),
        DialogState.SPEAKING: ("Konusuyor...", color.cyan),
    }
    t, c = status_map[dialog.state]
    dialog_status.text = t
    dialog_status.color = c
    dialog_user.text = f"Sen: {dialog.last_user_text}" if dialog.last_user_text else ""
    dialog_npc.text = (f"{dialog.current_npc.display_name}: {dialog.last_npc_reply}"
                       if dialog.last_npc_reply else "")


space_held = [False]
_last_near_hint_text = [""]   # son text - sadece degistiginde update


def update():
    update_hud()
    update_notification()
    update_dialog_ui()
    if dialog.current_npc is None:
        nearby = find_nearby_actor()
        if nearby:
            new_text = f"[E] {nearby.data.display_name} ile konus"
            if _last_near_hint_text[0] != new_text:
                near_hint.text = new_text
                _last_near_hint_text[0] = new_text
            near_hint.enabled = True
        else:
            if near_hint.enabled:
                near_hint.enabled = False
                _last_near_hint_text[0] = ""
    else:
        if near_hint.enabled:
            near_hint.enabled = False


def input(key):
    if key == 'q':
        application.quit()
    if dialog.current_npc is None:
        if key == 'e':
            nearby = find_nearby_actor()
            if nearby:
                dialog.enter(nearby.data)
    else:
        if key == 'escape':
            dialog.exit_dialog()
        elif key == 'space' and dialog.state == DialogState.IDLE:
            dialog.start_recording()
            space_held[0] = True
        elif key == 'space up' and space_held[0]:
            if dialog.state == DialogState.RECORDING:
                dialog.stop_recording_and_process()
            space_held[0] = False


print("[ready] Oyun calisiyor. WASD = hareket, E = konus, ESC = diyalogdan cik, Q = cikis\n")
sys.stdout.flush()
app.run()
