"""
Pygame 2D Dunya - Otonom NPC Demo (Turkce)
F1 = Debug mode toggle (aksiyon log gosterimi)
"""

import sys
import math
import threading
from enum import Enum

import pygame

from npc_brain import NPCBrain, load_npcs
from game_state import state


WIDTH, HEIGHT = 1000, 700
FPS = 60
INTERACT_RADIUS = 80
PLAYER_SPEED = 4

BG = (40, 60, 50)
PATH = (110, 90, 70)
PLAYER_COLOR = (90, 200, 90)
TEXT_COLOR = (240, 240, 240)
DIALOG_BG = (15, 20, 35)
DIALOG_BORDER = (180, 160, 100)


class GameMode(Enum):
    EXPLORING = "exploring"
    IN_DIALOG = "in_dialog"


class DialogState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SPEAKING = "speaking"


pygame.init()
pygame.display.set_caption("Eldermoor - Otonom NPC Demosu")
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

font_small = pygame.font.SysFont("arial", 14)
font_mid = pygame.font.SysFont("arial", 18, bold=True)
font_big = pygame.font.SysFont("arial", 24, bold=True)

print("[game] Pygame baslatildi, AI brain yukleniyor...")
brain = NPCBrain()
npcs = load_npcs()
npc_list = list(npcs.values())
print(f"[game] {len(npc_list)} NPC yuklendi\n")

# DEBUG modu - F1 ile toggle
debug_mode = False


class Player:
    def __init__(self):
        self.x = WIDTH // 2
        self.y = HEIGHT // 2
        self.radius = 16

    def update(self, keys):
        dx = dy = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        if dx and dy:
            dx *= 0.707; dy *= 0.707
        self.x += dx * PLAYER_SPEED
        self.y += dy * PLAYER_SPEED
        self.x = max(self.radius, min(WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(HEIGHT - self.radius, self.y))

    def draw(self, surf):
        pygame.draw.circle(surf, (20, 20, 20), (int(self.x), int(self.y)), self.radius + 2)
        pygame.draw.circle(surf, PLAYER_COLOR, (int(self.x), int(self.y)), self.radius)
        label = font_small.render("S", True, (0, 0, 0))
        surf.blit(label, label.get_rect(center=(int(self.x), int(self.y))))


player = Player()


class DialogManager:
    def __init__(self, brain):
        self.brain = brain
        self.current_npc = None
        self.state = DialogState.IDLE
        self.last_user_text = ""
        self.last_npc_reply = ""
        self.last_action = ""
        # HUD bildirim (kisa sureli, immersion bozmadan)
        self.notification = ""
        self.notification_until = 0
        self._worker = None

    def enter(self, npc):
        self.current_npc = npc
        self.state = DialogState.IDLE
        self.last_user_text = ""
        self.last_npc_reply = ""
        self.last_action = ""
        print(f"\n[dialog] {npc.display_name} ile konusuyorsun")

    def exit(self):
        if self.state in (DialogState.RECORDING, DialogState.PROCESSING, DialogState.SPEAKING):
            return False
        self.current_npc = None
        self.state = DialogState.IDLE
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
        self._worker = threading.Thread(target=self._process, args=(audio,), daemon=True)
        self._worker.start()

    def _process(self, audio):
        try:
            user_text = self.brain.transcribe(audio)
            if not user_text:
                self.last_user_text = "(anlasilmadi)"
                self.state = DialogState.IDLE
                return
            self.last_user_text = user_text
            print(f"  Sen: {user_text}")

            # Aksiyon logu: hem terminal hem (debug acikken) ekran icin
            def log_action(name, args, result):
                msg = result.get("message") or result.get("reason") or ""
                self.last_action = f"{name} -> {msg[:60]}"
                print(f"  [AKSIYON] {name}({args}) -> {msg}")
                # Immersion-friendly bildirim
                if result.get("success"):
                    self._set_notification_for_action(name, args, result)

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

    def _set_notification_for_action(self, name, args, result):
        """Kisa, immersion-uyumlu bildirim. Sag ust kosede 3 sn gorulur."""
        text = None
        if name == "give_item":
            item = args.get("item_name", "?")
            qty = args.get("quantity", 1)
            price = args.get("price", 0)
            if price > 0:
                text = f"+ {qty}x {item}  (-{price} altin)"
            else:
                text = f"+ {qty}x {item}"
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
            self.notification_until = pygame.time.get_ticks() + 3000


dialog = DialogManager(brain)


def find_nearby_npc():
    for npc in npc_list:
        if math.hypot(player.x - npc.x, player.y - npc.y) < INTERACT_RADIUS:
            return npc
    return None


def draw_npc(npc, is_near):
    pygame.draw.circle(screen, (10, 10, 10), (npc.x + 2, npc.y + 2), 18)
    pygame.draw.circle(screen, npc.color, (npc.x, npc.y), 18)
    border_col = (255, 255, 100) if is_near else (0, 0, 0)
    pygame.draw.circle(screen, border_col, (npc.x, npc.y), 18, 2)
    label = font_mid.render(npc.display_name, True, TEXT_COLOR)
    rect = label.get_rect(center=(npc.x, npc.y - 35))
    pygame.draw.rect(screen, (0, 0, 0), rect.inflate(8, 4))
    screen.blit(label, rect)
    if is_near:
        hint = font_small.render("[E] konus", True, (255, 255, 100))
        screen.blit(hint, hint.get_rect(center=(npc.x, npc.y + 35)))


def draw_world():
    screen.fill(BG)
    pygame.draw.rect(screen, PATH, (WIDTH // 2 - 30, 0, 60, HEIGHT))
    pygame.draw.rect(screen, PATH, (0, HEIGHT // 2 - 30, WIDTH, 60))
    for npc in npc_list:
        pygame.draw.rect(screen, (70, 50, 40), (npc.x - 50, npc.y - 50, 100, 100), border_radius=8)
    nearby = find_nearby_npc()
    for npc in npc_list:
        draw_npc(npc, is_near=(npc is nearby))
    player.draw(screen)
    return nearby


def draw_hud():
    lines = [
        f"Altin: {state.gold}",
        f"Envanter: " + (", ".join(f"{k} x{v}" for k, v in state.inventory.items()) or "(bos)"),
        f"Gorevler: " + (", ".join(q["title"] for q in state.active_quests) or "(yok)"),
    ]
    y = 10
    for line in lines:
        surf = font_small.render(line, True, TEXT_COLOR)
        bg = pygame.Surface((surf.get_width() + 12, surf.get_height() + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        screen.blit(bg, (8, y - 2))
        screen.blit(surf, (14, y))
        y += 22

    # Debug mode gostergesi
    if debug_mode:
        s = font_small.render("[DEBUG MODE - F1]", True, (255, 200, 100))
        screen.blit(s, (8, y + 4))


def draw_notification():
    """Sag ust kosede 3 sn gorulen kisa bildirim."""
    if pygame.time.get_ticks() > dialog.notification_until:
        return
    if not dialog.notification:
        return
    surf = font_mid.render(dialog.notification, True, (255, 240, 150))
    bg_rect = pygame.Rect(0, 0, surf.get_width() + 20, surf.get_height() + 10)
    bg_rect.topright = (WIDTH - 12, 10)
    bg = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
    bg.fill((30, 30, 20, 220))
    pygame.draw.rect(bg, (180, 160, 100), bg.get_rect(), 2)
    screen.blit(bg, bg_rect.topleft)
    screen.blit(surf, (bg_rect.x + 10, bg_rect.y + 5))


def draw_controls_hint(mode, nearby):
    hints = []
    if mode == GameMode.EXPLORING:
        hints.append("WASD = hareket")
        if nearby:
            hints.append("E = konus")
        hints.append("F1 = debug")
        hints.append("Q = cikis")
    else:
        if dialog.state == DialogState.IDLE:
            hints.append("SPACE basili tut = konus")
            hints.append("ESC = cikis")
        elif dialog.state == DialogState.RECORDING:
            hints.append("SPACE birak = gonder")
        else:
            hints.append("...")
    y = HEIGHT - 10 - len(hints) * 18
    for h in hints:
        surf = font_small.render(h, True, (200, 200, 200))
        screen.blit(surf, (WIDTH - surf.get_width() - 12, y))
        y += 18


def wrap_and_draw(text, x, y, max_w, color):
    words = text.split(" ")
    line = ""
    line_h = font_mid.get_linesize()
    for w in words:
        test = (line + " " + w).strip()
        if font_mid.size(test)[0] > max_w:
            screen.blit(font_mid.render(line, True, color), (x, y))
            y += line_h
            line = w
        else:
            line = test
    if line:
        screen.blit(font_mid.render(line, True, color), (x, y))


def draw_dialog_overlay():
    npc = dialog.current_npc
    if not npc:
        return
    box_h = 220 if debug_mode else 200
    box = pygame.Rect(20, HEIGHT - box_h - 20, WIDTH - 40, box_h)
    pygame.draw.rect(screen, DIALOG_BG, box, border_radius=10)
    pygame.draw.rect(screen, DIALOG_BORDER, box, 3, border_radius=10)
    name_surf = font_big.render(npc.display_name, True, DIALOG_BORDER)
    screen.blit(name_surf, (box.x + 20, box.y + 12))

    status_text = {
        DialogState.IDLE: "SPACE basili tut + konus + birak",
        DialogState.RECORDING: "DINLENIYOR... (birak: gonder)",
        DialogState.PROCESSING: "Dusunuyor...",
        DialogState.SPEAKING: "Konusuyor...",
    }[dialog.state]
    status_col = {
        DialogState.IDLE: (180, 180, 180),
        DialogState.RECORDING: (255, 100, 100),
        DialogState.PROCESSING: (255, 220, 80),
        DialogState.SPEAKING: (100, 220, 255),
    }[dialog.state]
    s_surf = font_mid.render(status_text, True, status_col)
    screen.blit(s_surf, (box.right - s_surf.get_width() - 20, box.y + 18))

    if dialog.last_user_text:
        wrap_and_draw(f"Sen: {dialog.last_user_text}", box.x + 20, box.y + 55, box.width - 40, (200, 200, 220))
    if dialog.last_npc_reply:
        wrap_and_draw(f"{npc.display_name}: {dialog.last_npc_reply}",
                      box.x + 20, box.y + 110, box.width - 40, (255, 240, 200))
    # Aksiyon yazisi SADECE debug acikken
    if debug_mode and dialog.last_action:
        a_surf = font_small.render(f"[Aksiyon] {dialog.last_action}", True, (130, 200, 130))
        screen.blit(a_surf, (box.x + 20, box.y + 185))

    if dialog.state == DialogState.RECORDING:
        pulse = int(127 + 128 * abs(math.sin(pygame.time.get_ticks() * 0.005)))
        pygame.draw.circle(screen, (pulse, 30, 30), (box.right - 30, box.y + 50), 10)


def main():
    global debug_mode
    mode = GameMode.EXPLORING
    space_held = False
    print("[game] Hazir. WASD = hareket, E = konus, F1 = debug, Q = cikis\n")
    running = True
    while running:
        keys = pygame.key.get_pressed()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                if event.key == pygame.K_F1:
                    debug_mode = not debug_mode
                    print(f"[debug] {'ACIK' if debug_mode else 'KAPALI'}")
                if mode == GameMode.EXPLORING:
                    if event.key == pygame.K_e:
                        nearby = find_nearby_npc()
                        if nearby:
                            dialog.enter(nearby)
                            mode = GameMode.IN_DIALOG
                elif mode == GameMode.IN_DIALOG:
                    if event.key == pygame.K_ESCAPE:
                        if dialog.exit():
                            mode = GameMode.EXPLORING
                    elif event.key == pygame.K_SPACE and dialog.state == DialogState.IDLE:
                        dialog.start_recording()
                        space_held = True
            elif event.type == pygame.KEYUP:
                if mode == GameMode.IN_DIALOG and event.key == pygame.K_SPACE:
                    if space_held and dialog.state == DialogState.RECORDING:
                        dialog.stop_recording_and_process()
                    space_held = False
        if mode == GameMode.EXPLORING:
            player.update(keys)
        nearby = draw_world()
        draw_hud()
        draw_notification()
        draw_controls_hint(mode, nearby)
        if mode == GameMode.IN_DIALOG:
            draw_dialog_overlay()
        pygame.display.flip()
        clock.tick(FPS)
    print("[bye]")
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
