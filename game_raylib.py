"""
Raylib 3D Otonom NPC Demo - DAY 2 (Tam Entegrasyon)
====================================================
- 4 NPC (Gareth, Mira, Roderick, Elara)
- AI brain (Whisper + Groq + Edge TTS)
- Function calling (give_item, offer_quest, vb)
- Tam diyalog UI
- Turkce destek

Kontroller:
  WASD / Mouse  : Hareket + bakis
  E             : Yakindaki NPC ile konus
  SPACE basili tut : Mikrofon kaydi (diyalog modunda)
  ESC           : Diyalogdan cik
  F1            : Debug mode toggle
  Q             : Cikis
"""

import sys
import math
import time
import random
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

print("[3/3] Raylib baslatiliyor...")
sys.stdout.flush()
import pyray as rl
from pyray import Vector3, Vector2, Color

# ====================== Config ======================
WIDTH, HEIGHT = 1280, 720
INTERACT_RADIUS = 5.0
PLAYER_SPEED = 8.0
MOUSE_SENS = 0.003

debug_mode = False


class DialogState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SPEAKING = "speaking"


# ====================== Pencere init ======================
rl.set_config_flags(rl.ConfigFlags.FLAG_MSAA_4X_HINT | rl.ConfigFlags.FLAG_WINDOW_HIGHDPI)
rl.init_window(WIDTH, HEIGHT, "Eldermoor 3D - Otonom NPC Demosu (Raylib)")
rl.set_target_fps(60)
rl.disable_cursor()


# ====================== Turkce destekli FONT yukleme ======================
# Raylib default fontu sadece ASCII. Turkce karakterler icin TTF font yukleyip
# tum gerekli codepoints'leri (ASCII + Latin-1 ekstra + Turkce ozel) acikca veriyoruz.

import os

def _build_codepoint_set():
    """ASCII + Latin-1 Supplement + Turkce ozel karakterler."""
    points = []
    # ASCII yazdirilabilir (32-126)
    points.extend(range(32, 127))
    # Latin-1 Supplement (160-255) - cogu Avrupa dili karakteri burada
    points.extend(range(160, 256))
    # Turkce ozel - bazilari Latin-1'de zaten var ama emin olalim
    extra = "ÇçĞğİıÖöŞşÜüÂâÎîÛû"
    for ch in extra:
        points.append(ord(ch))
    # Tekrar etmesin
    return sorted(set(points))


_CODEPOINTS = _build_codepoint_set()

# Font dosyasini bul - 3 sirayla dene
_font_candidates = [
    os.path.join("assets", "font.ttf"),
    os.path.join("assets", "DejaVuSans.ttf"),
    # Windows sistem fontu - Turkce destekli, kesin var
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
]

TR_FONT = None
TR_FONT_SIZE_BASE = 32


def _try_load_font_ex_method1(font_path, codepoints):
    """Yontem 1: ffi.new ile dogrudan int[N] array."""
    n = len(codepoints)
    cp_array = rl.ffi.new(f"int[{n}]", codepoints)
    return rl.load_font_ex(font_path, TR_FONT_SIZE_BASE, cp_array, n)


def _try_load_font_ex_method2(font_path, codepoints):
    """Yontem 2: ffi.new("int[]", [...]) ile boyut otomatik."""
    cp_array = rl.ffi.new("int[]", codepoints)
    return rl.load_font_ex(font_path, TR_FONT_SIZE_BASE, cp_array, len(codepoints))


def _try_load_font_ex_method3(font_path, codepoints):
    """Yontem 3: liste dogrudan (bazi pyray surumleri auto-convert eder)."""
    return rl.load_font_ex(font_path, TR_FONT_SIZE_BASE, codepoints, len(codepoints))


def _try_load_font_ex_method4(font_path, codepoints):
    """Yontem 4: bytearray ile."""
    import struct
    raw = b''.join(struct.pack('<i', c) for c in codepoints)
    cp_array = rl.ffi.cast("int*", rl.ffi.from_buffer(raw))
    return rl.load_font_ex(font_path, TR_FONT_SIZE_BASE, cp_array, len(codepoints))


_methods = [
    ("yontem1: int[N]", _try_load_font_ex_method1),
    ("yontem2: int[]", _try_load_font_ex_method2),
    ("yontem3: dogrudan list", _try_load_font_ex_method3),
    ("yontem4: bytearray", _try_load_font_ex_method4),
]

for font_path in _font_candidates:
    if not os.path.isfile(font_path):
        continue
    print(f"[font] Deneme: {font_path}")
    for method_name, method_fn in _methods:
        try:
            font = method_fn(font_path, _CODEPOINTS)
            # glyph_count alani sururumler arasinda degisiyor, kontrol etmeden
            # sadece texture'in yuklendigini kontrol et
            if font and font.texture.id != 0:
                TR_FONT = font
                print(f"[font] OK ({method_name}): {font_path}")
                rl.set_texture_filter(TR_FONT.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
                break
        except Exception as e:
            print(f"[font] {method_name} hata: {type(e).__name__}: {str(e)[:80]}")
    if TR_FONT:
        break

# Son fallback - sade load_font
if TR_FONT is None:
    for font_path in _font_candidates:
        if not os.path.isfile(font_path):
            continue
        try:
            TR_FONT = rl.load_font(font_path)
            if TR_FONT.texture.id != 0:
                print(f"[font] Sade yukleme: {font_path} (TR karakter olmayabilir)")
                rl.set_texture_filter(TR_FONT.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
                break
            else:
                TR_FONT = None
        except Exception:
            TR_FONT = None

if TR_FONT is None:
    print("[font] UYARI: Hicbir font yuklenemedi.")


def tr_text(text: str, x: int, y: int, size: int, col):
    """Turkce destekli metin ciz."""
    if TR_FONT:
        rl.draw_text_ex(TR_FONT, text, Vector2(float(x), float(y)),
                        float(size), 1.0, col)
    else:
        # Fallback: built-in default font (TR karakter ? cikar ama crash etmez)
        rl.draw_text(text.encode('ascii', 'replace').decode('ascii'),
                     x, y, size, col)


def tr_measure(text: str, size: int) -> int:
    """Turkce destekli metin genisligi olc."""
    if TR_FONT:
        v = rl.measure_text_ex(TR_FONT, text, float(size), 1.0)
        return int(v.x)
    return rl.measure_text(text.encode('ascii', 'replace').decode('ascii'), size)


print("[3/3] Raylib HAZIR\n")


# ====================== Collision sistemi ======================
# Her engel: (x, z, radius). Oyuncu bu dairelerin icine giremez.
COLLIDERS = []
PLAYER_RADIUS = 0.6


def _collides(x, z):
    """Verilen (x,z) noktasi bir engelle cakisiyor mu?"""
    for cx, cz, cr in COLLIDERS:
        dx = x - cx
        dz = z - cz
        if dx * dx + dz * dz < (cr + PLAYER_RADIUS) ** 2:
            return True
    return False


# ====================== Player (first-person) ======================
class Player:
    def __init__(self):
        self.position = Vector3(0, 1.7, -10)
        self.yaw = 0.0    # sag/sol
        self.pitch = 0.0  # yukari/asagi

    def get_forward(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        return Vector3(sy * cp, sp, cy * cp)

    def get_right(self):
        # forward'in 90 derece sag tarafi (y=0 dolayisi xz duzleminde)
        # Sag el kurali: right = forward x up
        # forward'in xz iz dusumu: (sy, 0, cy)
        # right = (cy, 0, -sy)  -> ama A/D ters olduguna gore yon yanlistir
        # Dogrusu: (cy, 0, sy)'nin negatifi = (-cy, 0, -sy) yanlis
        # Aslinda right = cross(up, forward), up=(0,1,0)
        # up x fwd = (1*fwd.z - 0, 0, 0 - 1*fwd.x) = (fwd.z, 0, -fwd.x)
        # fwd.x = sy*cp, fwd.z = cy*cp
        # right = (cy*cp, 0, -sy*cp), y=0 icin pitch yok say:
        # right = (cy, 0, -sy)  -- bu mevcut, A/D ters demek mevcut yanlis
        # O zaman tersini al:
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        return Vector3(-cy, 0, sy)

    def update(self, dt, mouse_active):
        # Mouse bakis (sadece mouse_active ise)
        if mouse_active:
            md = rl.get_mouse_delta()
            self.yaw -= md.x * MOUSE_SENS
            self.pitch -= md.y * MOUSE_SENS
            # Pitch'i sinirla
            self.pitch = max(-1.5, min(1.5, self.pitch))

        # WASD hareketi (sadece mouse_active iken)
        if mouse_active:
            fwd = self.get_forward()
            right = self.get_right()
            speed = PLAYER_SPEED * dt
            mx = mz = 0.0
            if rl.is_key_down(rl.KeyboardKey.KEY_W):
                mx += fwd.x * speed
                mz += fwd.z * speed
            if rl.is_key_down(rl.KeyboardKey.KEY_S):
                mx -= fwd.x * speed
                mz -= fwd.z * speed
            if rl.is_key_down(rl.KeyboardKey.KEY_A):
                mx -= right.x * speed
                mz -= right.z * speed
            if rl.is_key_down(rl.KeyboardKey.KEY_D):
                mx += right.x * speed
                mz += right.z * speed

            # Collision-aware hareket: X ve Z'yi AYRI dene (duvar boyunca kayma)
            new_x = self.position.x + mx
            if not _collides(new_x, self.position.z):
                self.position.x = new_x
            new_z = self.position.z + mz
            if not _collides(self.position.x, new_z):
                self.position.z = new_z

        # Harita sinirlari
        self.position.x = max(-30, min(30, self.position.x))
        self.position.z = max(-30, min(30, self.position.z))

    def get_camera(self):
        cam = rl.Camera3D()
        cam.position = self.position
        fwd = self.get_forward()
        cam.target = Vector3(
            self.position.x + fwd.x,
            self.position.y + fwd.y,
            self.position.z + fwd.z,
        )
        cam.up = Vector3(0, 1, 0)
        cam.fovy = 75.0
        cam.projection = rl.CameraProjection.CAMERA_PERSPECTIVE
        return cam


player = Player()


# ====================== NPC ======================
# Renk yardimcisi
def C(r, g, b, a=255):
    return Color(int(r), int(g), int(b), int(a))


class NPCActor:
    def __init__(self, npc_data):
        self.data = npc_data
        # 2D pozisyonunu 3D'ye cevir - /22 ile daha genis yayilim
        self.x = (npc_data.x - 500) / 22.0
        self.z = (npc_data.y - 350) / 22.0
        self.color = C(*npc_data.color)
        c = npc_data.color
        self.building_color = C(max(c[0] - 30, 40), max(c[1] - 30, 40), max(c[2] - 30, 40))

    def _draw_building(self):
        """Arkadaki bina + tabela + kapi onu fenerli."""
        bx, bz = self.x, self.z + 7   # bina NPC'den 7 birim uzakta (dip dibe degil)
        # Temel govde
        rl.draw_cube(Vector3(bx, 1.75, bz), 6.0, 3.5, 6.0, self.building_color)
        rl.draw_cube_wires(Vector3(bx, 1.75, bz), 6.0, 3.5, 6.0, rl.BLACK)
        # Catinin altinda koyu bant (mimari detay)
        rl.draw_cube(Vector3(bx, 3.45, bz), 6.2, 0.2, 6.2, C(70, 50, 35))
        # Cati - kirmizi kiremit
        rl.draw_cube(Vector3(bx, 3.7, bz), 6.8, 0.4, 6.8, C(150, 60, 50))
        # Catinin tepesi - sivri (ust kup, daha kucuk)
        rl.draw_cube(Vector3(bx, 4.1, bz), 5.5, 0.4, 5.5, C(130, 50, 40))
        rl.draw_cube(Vector3(bx, 4.4, bz), 4.0, 0.3, 4.0, C(110, 40, 30))
        # Kapi - cift kanatli
        rl.draw_cube(Vector3(bx - 0.35, 1.0, bz - 3.05), 0.6, 2.0, 0.15, C(75, 50, 25))
        rl.draw_cube(Vector3(bx + 0.35, 1.0, bz - 3.05), 0.6, 2.0, 0.15, C(75, 50, 25))
        # Kapi tokmaklari
        rl.draw_sphere(Vector3(bx - 0.05, 1.0, bz - 3.13), 0.06, C(200, 170, 80))
        rl.draw_sphere(Vector3(bx + 0.05, 1.0, bz - 3.13), 0.06, C(200, 170, 80))
        # Pencereler - cerceveli
        for px in (-1.8, 1.8):
            rl.draw_cube(Vector3(bx + px, 2.2, bz - 3.0), 1.0, 1.0, 0.08, C(80, 60, 40))
            rl.draw_cube(Vector3(bx + px, 2.2, bz - 3.02), 0.8, 0.8, 0.06, C(160, 200, 230))
            # Pencere ust capragi
            rl.draw_cube(Vector3(bx + px, 2.2, bz - 3.03), 0.85, 0.06, 0.03, C(50, 40, 30))
            rl.draw_cube(Vector3(bx + px, 2.2, bz - 3.03), 0.06, 0.85, 0.03, C(50, 40, 30))
        # Tabela - kapinin ustunde
        rl.draw_cube(Vector3(bx, 2.85, bz - 3.05), 2.5, 0.6, 0.12, C(120, 85, 55))
        rl.draw_cube_wires(Vector3(bx, 2.85, bz - 3.05), 2.5, 0.6, 0.12, rl.BLACK)
        # Tabela asma zinciri
        rl.draw_cube(Vector3(bx, 3.2, bz - 3.05), 0.05, 0.3, 0.05, C(60, 60, 60))
        # 2 fener kapinin yanlarinda
        for px in (-1.0, 1.0):
            rl.draw_cube(Vector3(bx + px, 1.5, bz - 3.0), 0.15, 0.4, 0.15, C(60, 50, 40))   # direk
            rl.draw_sphere(Vector3(bx + px, 1.75, bz - 3.0), 0.18, C(255, 220, 120))         # alev/cam

    def _draw_npc_body(self):
        """NPC golgesi (gund govdesi) - ortak."""
        nx, nz = self.x, self.z

        # Yer golgesi (kucuk daire)
        rl.draw_circle_3d(Vector3(nx, 0.02, nz), 0.7,
                          Vector3(1, 0, 0), 90, C(0, 0, 0, 90))

        # Bacaklar (koyu kahve, pantolon)
        leg_c = C(60, 40, 30)
        rl.draw_cube(Vector3(nx - 0.22, 0.5, nz), 0.35, 1.0, 0.35, leg_c)
        rl.draw_cube(Vector3(nx + 0.22, 0.5, nz), 0.35, 1.0, 0.35, leg_c)
        # Ayakkabilar
        boot = C(35, 25, 20)
        rl.draw_cube(Vector3(nx - 0.22, 0.07, nz + 0.06), 0.4, 0.15, 0.5, boot)
        rl.draw_cube(Vector3(nx + 0.22, 0.07, nz + 0.06), 0.4, 0.15, 0.5, boot)
        # Kemer
        rl.draw_cube(Vector3(nx, 1.05, nz), 1.2, 0.15, 0.75, C(50, 35, 25))
        rl.draw_cube(Vector3(nx, 1.05, nz - 0.4), 0.25, 0.2, 0.05, C(200, 170, 80))  # toka

        # Govde (NPC rengi - tunik/onluk)
        rl.draw_cube(Vector3(nx, 1.6, nz), 1.1, 1.3, 0.7, self.color)
        rl.draw_cube_wires(Vector3(nx, 1.6, nz), 1.1, 1.3, 0.7, rl.BLACK)

        # Kollar
        rl.draw_cube(Vector3(nx - 0.7, 1.6, nz), 0.3, 1.1, 0.3, self.color)
        rl.draw_cube(Vector3(nx + 0.7, 1.6, nz), 0.3, 1.1, 0.3, self.color)
        # Eller (ten rengi top)
        skin = C(230, 190, 160)
        rl.draw_sphere(Vector3(nx - 0.7, 1.05, nz), 0.13, skin)
        rl.draw_sphere(Vector3(nx + 0.7, 1.05, nz), 0.13, skin)

        # Boyun
        rl.draw_cube(Vector3(nx, 2.25, nz), 0.3, 0.2, 0.3, skin)
        # Kafa
        rl.draw_sphere(Vector3(nx, 2.55, nz), 0.38, skin)
        # Gozler (siyah noktalar)
        rl.draw_sphere(Vector3(nx - 0.13, 2.6, nz - 0.32), 0.04, rl.BLACK)
        rl.draw_sphere(Vector3(nx + 0.13, 2.6, nz - 0.32), 0.04, rl.BLACK)

    def _draw_npc_body(self):
        """NPC govdesi - S olcek faktoru ile kucultuldu."""
        nx, nz = self.x, self.z
        S = 0.65  # boyut olcegi (1.0 cok buyuktu)
        skin = C(230, 190, 160)

        # Yer golgesi
        rl.draw_circle_3d(Vector3(nx, 0.02, nz), 0.5 * S,
                          Vector3(1, 0, 0), 90, C(0, 0, 0, 90))

        # Bacaklar
        leg_c = C(60, 40, 30)
        rl.draw_cube(Vector3(nx - 0.22 * S, 0.5 * S, nz), 0.35 * S, 1.0 * S, 0.35 * S, leg_c)
        rl.draw_cube(Vector3(nx + 0.22 * S, 0.5 * S, nz), 0.35 * S, 1.0 * S, 0.35 * S, leg_c)
        # Ayakkabilar
        boot = C(35, 25, 20)
        rl.draw_cube(Vector3(nx - 0.22 * S, 0.07 * S, nz + 0.06 * S), 0.4 * S, 0.15 * S, 0.5 * S, boot)
        rl.draw_cube(Vector3(nx + 0.22 * S, 0.07 * S, nz + 0.06 * S), 0.4 * S, 0.15 * S, 0.5 * S, boot)
        # Kemer
        rl.draw_cube(Vector3(nx, 1.05 * S, nz), 1.2 * S, 0.15 * S, 0.75 * S, C(50, 35, 25))

        # Govde
        rl.draw_cube(Vector3(nx, 1.6 * S, nz), 1.1 * S, 1.3 * S, 0.7 * S, self.color)
        rl.draw_cube_wires(Vector3(nx, 1.6 * S, nz), 1.1 * S, 1.3 * S, 0.7 * S, rl.BLACK)

        # Kollar
        rl.draw_cube(Vector3(nx - 0.7 * S, 1.6 * S, nz), 0.3 * S, 1.1 * S, 0.3 * S, self.color)
        rl.draw_cube(Vector3(nx + 0.7 * S, 1.6 * S, nz), 0.3 * S, 1.1 * S, 0.3 * S, self.color)
        # Eller
        rl.draw_sphere(Vector3(nx - 0.7 * S, 1.05 * S, nz), 0.13 * S, skin)
        rl.draw_sphere(Vector3(nx + 0.7 * S, 1.05 * S, nz), 0.13 * S, skin)

        # Boyun + Kafa
        rl.draw_cube(Vector3(nx, 2.25 * S, nz), 0.3 * S, 0.2 * S, 0.3 * S, skin)
        rl.draw_sphere(Vector3(nx, 2.55 * S, nz), 0.38 * S, skin)
        # Gozler
        rl.draw_sphere(Vector3(nx - 0.13 * S, 2.6 * S, nz - 0.32 * S), 0.04 * S, rl.BLACK)
        rl.draw_sphere(Vector3(nx + 0.13 * S, 2.6 * S, nz - 0.32 * S), 0.04 * S, rl.BLACK)

    def _draw_npc_accessory(self):
        """NPC'nin meslegine ozgu aksesuar/silah. S olcekli."""
        nx, nz = self.x, self.z
        npc_id = self.data.id
        S = 0.65

        if npc_id == "demirci":
            # Ekipman saticisi: deri onluk + gri sakal + cekic
            rl.draw_cube(Vector3(nx, 1.55 * S, nz - 0.36 * S), 1.0 * S, 1.1 * S, 0.05 * S, C(70, 45, 25))
            rl.draw_sphere(Vector3(nx, 2.28 * S, nz - 0.32 * S), 0.15 * S, C(180, 180, 180))  # sakal
            rl.draw_cube(Vector3(nx, 2.78 * S, nz), 0.78 * S, 0.18 * S, 0.78 * S, C(160, 160, 160))  # sac
            # Cekic
            ham_x = nx + 0.62 * S
            rl.draw_cube(Vector3(ham_x, 0.9 * S, nz), 0.06 * S, 1.3 * S, 0.06 * S, C(80, 60, 40))
            rl.draw_cube(Vector3(ham_x, 1.55 * S, nz), 0.25 * S, 0.25 * S, 0.45 * S, C(90, 90, 100))

        elif npc_id == "iksirci":
            # Iksir saticisi: pelerin + sac + kese + kupe
            rl.draw_cube(Vector3(nx, 1.6 * S, nz + 0.4 * S), 1.2 * S, 1.4 * S, 0.1 * S, C(150, 50, 100))
            rl.draw_cube(Vector3(nx, 2.78 * S, nz), 0.85 * S, 0.2 * S, 0.85 * S, C(80, 50, 30))
            rl.draw_cube(Vector3(nx - 0.32 * S, 2.4 * S, nz), 0.15 * S, 0.7 * S, 0.4 * S, C(80, 50, 30))
            rl.draw_cube(Vector3(nx + 0.32 * S, 2.4 * S, nz), 0.15 * S, 0.7 * S, 0.4 * S, C(80, 50, 30))
            rl.draw_sphere(Vector3(nx + 0.5 * S, 1.0 * S, nz - 0.3 * S), 0.15 * S, C(120, 90, 50))  # kese
            rl.draw_sphere(Vector3(nx - 0.32 * S, 2.5 * S, nz - 0.1 * S), 0.04 * S, C(255, 220, 80))  # kupe

        elif npc_id == "muhafiz":
            # Muhafiz: migfer + zirh + kilic + pelerin
            rl.draw_sphere(Vector3(nx, 2.7 * S, nz), 0.43 * S, C(180, 180, 200))  # migfer
            rl.draw_cube(Vector3(nx, 2.85 * S, nz), 0.5 * S, 0.1 * S, 0.95 * S, C(150, 150, 170))  # cret
            rl.draw_sphere(Vector3(nx - 0.65 * S, 2.0 * S, nz), 0.25 * S, C(150, 150, 170))  # omuz
            rl.draw_sphere(Vector3(nx + 0.65 * S, 2.0 * S, nz), 0.25 * S, C(150, 150, 170))
            rl.draw_cube(Vector3(nx, 1.7 * S, nz - 0.36 * S), 0.9 * S, 0.9 * S, 0.05 * S, C(170, 170, 190))  # gogus
            rl.draw_cube(Vector3(nx, 1.6 * S, nz + 0.4 * S), 1.3 * S, 1.5 * S, 0.1 * S, C(40, 60, 130))  # pelerin
            rl.draw_cube(Vector3(nx + 0.65 * S, 1.0 * S, nz), 0.1 * S, 1.0 * S, 0.1 * S, C(200, 200, 210))  # kilic
            rl.draw_cube(Vector3(nx + 0.65 * S, 1.5 * S, nz), 0.3 * S, 0.1 * S, 0.1 * S, C(120, 80, 40))  # kabza

        elif npc_id == "hanci":
            # Han sahibi: beyaz onluk + bonet + tepsi
            rl.draw_cube(Vector3(nx, 1.55 * S, nz - 0.36 * S), 0.95 * S, 1.0 * S, 0.05 * S, C(240, 235, 220))
            rl.draw_cube(Vector3(nx, 2.78 * S, nz), 0.85 * S, 0.2 * S, 0.85 * S, C(180, 150, 110))
            rl.draw_cube(Vector3(nx - 0.32 * S, 2.5 * S, nz), 0.1 * S, 0.3 * S, 0.3 * S, C(180, 130, 90))
            rl.draw_cube(Vector3(nx + 0.32 * S, 2.5 * S, nz), 0.1 * S, 0.3 * S, 0.3 * S, C(180, 130, 90))
            rl.draw_cube(Vector3(nx + 0.62 * S, 1.2 * S, nz - 0.2 * S), 0.7 * S, 0.05 * S, 0.5 * S, C(150, 110, 70))  # tepsi
            rl.draw_sphere(Vector3(nx + 0.58 * S, 1.3 * S, nz - 0.25 * S), 0.12 * S, C(210, 170, 110))  # ekmek

        elif npc_id == "isinlayici":
            # Gezgin buyucu: kukuleta + uzun sakal + asa
            # Kukuleta (mor baslik)
            rl.draw_sphere(Vector3(nx, 2.62 * S, nz), 0.42 * S, C(90, 50, 150))
            rl.draw_cube(Vector3(nx, 2.9 * S, nz), 0.3 * S, 0.4 * S, 0.3 * S, C(90, 50, 150))  # sivri uc
            # Uzun beyaz sakal
            rl.draw_cube(Vector3(nx, 2.2 * S, nz - 0.3 * S), 0.3 * S, 0.6 * S, 0.15 * S, C(220, 220, 230))
            # Cuppe (mor pelerin)
            rl.draw_cube(Vector3(nx, 1.6 * S, nz + 0.4 * S), 1.3 * S, 1.5 * S, 0.12 * S, C(80, 40, 140))
            # Buyucu asasi (sag el)
            staff_x = nx + 0.7 * S
            rl.draw_cube(Vector3(staff_x, 1.3 * S, nz), 0.07 * S, 2.6 * S, 0.07 * S, C(90, 60, 40))  # sap
            # Asanin tepesinde parlayan kure
            glow = C(150, 220, 255)
            rl.draw_sphere(Vector3(staff_x, 2.65 * S, nz), 0.2 * S, glow)
            rl.draw_sphere(Vector3(staff_x, 2.65 * S, nz), 0.28 * S, C(150, 220, 255, 90))  # hale

    def draw(self):
        # Isinlayici binasi yok, onun yerine portal cizilir
        if self.data.id == "isinlayici":
            self._draw_portal()
        else:
            self._draw_building()
        self._draw_npc_body()
        self._draw_npc_accessory()

    def _draw_portal(self):
        """Isinlayicinin arkasinda buyulu portal (haritanin otesine acilan)."""
        import math as _m
        px, pz = self.x, self.z + 4
        t = time.time()
        # Portal cercevesi - tas kemerler
        for ang in range(0, 360, 30):
            rad = _m.radians(ang)
            ox = _m.cos(rad) * 2.0
            oy = _m.sin(rad) * 2.5 + 2.5
            if oy > 0.3:  # zeminin altina cizme
                rl.draw_sphere(Vector3(px + ox, oy, pz), 0.3, C(90, 80, 110))
        # Portal ici - parlayan mor/mavi (animasyonlu renk)
        pulse = int(150 + 80 * abs(_m.sin(t * 1.5)))
        rl.draw_cube(Vector3(px, 2.5, pz), 3.0, 4.5, 0.2, C(100, 60, pulse, 180))
        rl.draw_cube(Vector3(px, 2.5, pz), 2.4, 3.9, 0.25, C(140, 100, 230, 140))
        # Merkez parlak
        rl.draw_sphere(Vector3(px, 2.5, pz - 0.1), 0.5, C(180, 160, 255, 120))


# ====================== Dekor objeleri ======================
def draw_tree(x, z, scale=1.0):
    """Govde + 3 katli yapraklik."""
    h = 2.0 * scale
    # Govde
    rl.draw_cube(Vector3(x, h / 2, z), 0.5 * scale, h, 0.5 * scale, C(80, 50, 30))
    rl.draw_cube_wires(Vector3(x, h / 2, z), 0.5 * scale, h, 0.5 * scale, rl.BLACK)
    # Yapraklik (3 katli kup pyramid)
    s = 2.5 * scale
    rl.draw_cube(Vector3(x, h + 0.5 * scale, z), s, 1.5 * scale, s, C(40, 110, 50))
    s2 = 1.8 * scale
    rl.draw_cube(Vector3(x, h + 1.5 * scale, z), s2, 1.2 * scale, s2, C(50, 130, 60))
    s3 = 1.0 * scale
    rl.draw_cube(Vector3(x, h + 2.3 * scale, z), s3, 0.8 * scale, s3, C(60, 145, 70))


def draw_rock(x, z, scale=1.0):
    """Bir grup gri kup taşı."""
    rl.draw_sphere(Vector3(x, 0.4 * scale, z), 0.7 * scale, C(130, 130, 135))
    rl.draw_sphere(Vector3(x - 0.5 * scale, 0.25 * scale, z + 0.3 * scale),
                   0.4 * scale, C(110, 110, 115))
    rl.draw_sphere(Vector3(x + 0.4 * scale, 0.3 * scale, z - 0.3 * scale),
                   0.5 * scale, C(140, 140, 145))


def draw_barrel(x, z):
    """Ahsap fici."""
    # Govde
    rl.draw_cylinder(Vector3(x, 0, z), 0.45, 0.45, 1.0, 12, C(110, 75, 40))
    rl.draw_cylinder_wires(Vector3(x, 0, z), 0.45, 0.45, 1.0, 12, rl.BLACK)
    # 3 metal halka
    for y in (0.15, 0.5, 0.85):
        rl.draw_cylinder(Vector3(x, y, z), 0.48, 0.48, 0.04, 12, C(90, 90, 100))


def draw_well(x, z):
    """Kuyu - tas duvar + ahsap cati."""
    # Daire taban
    rl.draw_cylinder(Vector3(x, 0, z), 1.2, 1.2, 0.15, 12, C(140, 130, 120))
    # Tas kasası
    rl.draw_cylinder(Vector3(x, 0.15, z), 1.0, 1.0, 1.0, 12, C(140, 140, 145))
    rl.draw_cylinder_wires(Vector3(x, 0.15, z), 1.0, 1.0, 1.0, 12, rl.BLACK)
    # Ic kismi (su, koyu)
    rl.draw_cylinder(Vector3(x, 1.0, z), 0.85, 0.85, 0.05, 12, C(20, 50, 80))
    # 2 direk
    rl.draw_cube(Vector3(x - 0.9, 2.0, z), 0.15, 2.0, 0.15, C(90, 60, 40))
    rl.draw_cube(Vector3(x + 0.9, 2.0, z), 0.15, 2.0, 0.15, C(90, 60, 40))
    # Cati
    rl.draw_cube(Vector3(x, 3.1, z), 2.6, 0.2, 1.0, C(110, 50, 40))


def draw_chest(x, z):
    """Sandik."""
    rl.draw_cube(Vector3(x, 0.35, z), 1.2, 0.7, 0.8, C(100, 65, 35))
    rl.draw_cube_wires(Vector3(x, 0.35, z), 1.2, 0.7, 0.8, rl.BLACK)
    # Metal kilit
    rl.draw_cube(Vector3(x, 0.5, z - 0.42), 0.2, 0.2, 0.05, C(180, 150, 80))
    # Metal bantlari
    rl.draw_cube(Vector3(x - 0.45, 0.35, z), 0.05, 0.72, 0.82, C(80, 60, 30))
    rl.draw_cube(Vector3(x + 0.45, 0.35, z), 0.05, 0.72, 0.82, C(80, 60, 30))


def draw_fence_post(x, z):
    """Kucuk cit direkleri."""
    rl.draw_cube(Vector3(x, 0.6, z), 0.15, 1.2, 0.15, C(110, 80, 50))
    rl.draw_sphere(Vector3(x, 1.25, z), 0.12, C(90, 65, 40))


def draw_flowers(x, z):
    """Bir grup kucuk renkli kure (cicek)."""
    colors = [C(220, 80, 80), C(220, 220, 80), C(200, 100, 200)]
    import random
    rnd = random.Random(int(x * 100 + z))  # deterministik
    for _ in range(5):
        ox = rnd.uniform(-0.4, 0.4)
        oz = rnd.uniform(-0.4, 0.4)
        col = rnd.choice(colors)
        rl.draw_sphere(Vector3(x + ox, 0.1, z + oz), 0.08, col)
        # Sap (yesil)
        rl.draw_cube(Vector3(x + ox, 0.06, z + oz), 0.02, 0.12, 0.02, C(50, 130, 60))


# ====================== Dekor yerlestir ======================
def setup_decorations():
    """Sahneye sabit dekorasyonlar ekle - draw_decorations icin liste hazirla."""
    decorations = []
    import random
    rnd = random.Random(42)  # deterministik

    # Agaclar - harita kenarlari
    tree_spots = [
        (-22, -22), (-22, 0), (-22, 22),
        (22, -22), (22, 0), (22, 22),
        (-12, -22), (12, -22),
        (-12, 22), (12, 22),
        (-25, -10), (-25, 10), (25, -10), (25, 10),
    ]
    for tx, tz in tree_spots:
        s = rnd.uniform(0.8, 1.4)
        decorations.append(("tree", tx + rnd.uniform(-1, 1), tz + rnd.uniform(-1, 1), s))

    # Kayalar
    rock_spots = [(-18, -8), (-8, -18), (18, 8), (8, 18), (-16, 16), (16, -16)]
    for rx, rz in rock_spots:
        s = rnd.uniform(0.7, 1.3)
        decorations.append(("rock", rx, rz, s))

    # Koy meydani objeleri
    decorations.append(("well", 0, 0, 1.0))      # merkezi kuyu

    # NPC'lerin yaninda meslege ozgu
    # Gareth'in onunde fici (demirci)
    decorations.append(("barrel", -12, -8, 1.0))
    decorations.append(("barrel", -11, -8.5, 1.0))
    # Mira'nin yaninda sandik
    decorations.append(("chest", 6, -8, 1.0))
    # Elara'nin onunde varil (bira)
    decorations.append(("barrel", 6, 8, 1.0))
    # Roderick'in onunde sandik
    decorations.append(("chest", -11, 8, 1.0))

    # Cicekler dagmik
    flower_spots = [(-4, -4), (4, -4), (-4, 4), (4, 4), (-8, 2), (8, -2)]
    for fx, fz in flower_spots:
        decorations.append(("flowers", fx, fz, 1.0))

    # Cit direkleri harita kenarlarinda dizili
    for i in range(-28, 30, 4):
        decorations.append(("fence", i, 28, 1.0))
        decorations.append(("fence", i, -28, 1.0))
        decorations.append(("fence", 28, i, 1.0))
        decorations.append(("fence", -28, i, 1.0))

    return decorations


DECORATIONS = setup_decorations()
print(f"[world] {len(DECORATIONS)} dekor objesi yerlestirildi")


def draw_decorations():
    for kind, x, z, scale in DECORATIONS:
        if kind == "tree":
            draw_tree(x, z, scale)
        elif kind == "rock":
            draw_rock(x, z, scale)
        elif kind == "barrel":
            draw_barrel(x, z)
        elif kind == "well":
            draw_well(x, z)
        elif kind == "chest":
            draw_chest(x, z)
        elif kind == "fence":
            draw_fence_post(x, z)
        elif kind == "flowers":
            draw_flowers(x, z)


actors = [NPCActor(npc) for npc in npcs_dict.values()]
print(f"[world] {len(actors)} NPC olusturuldu\n")


# ====================== COLLIDERS doldur ======================
def build_colliders():
    cols = []
    # NPC'ler (govde) - kucuk yaricap
    for a in actors:
        cols.append((a.x, a.z, 0.7))
        # NPC'nin binasi (varsa) - buyuk blok
        if a.data.id != "isinlayici":
            bx, bz = a.x, a.z + 7
            cols.append((bx, bz, 3.2))   # 6x6 bina -> ~3.2 yaricap
        else:
            # Isinlayicinin portali
            cols.append((a.x, a.z + 4, 1.8))
    # Dekorasyonlar
    for kind, x, z, scale in DECORATIONS:
        if kind == "tree":
            cols.append((x, z, 0.6 * scale))
        elif kind == "rock":
            cols.append((x, z, 0.8 * scale))
        elif kind == "barrel":
            cols.append((x, z, 0.5))
        elif kind == "well":
            cols.append((x, z, 1.3))
        elif kind == "chest":
            cols.append((x, z, 0.7))
        elif kind == "fence":
            cols.append((x, z, 0.25))
        # cicekler collider almaz (uzerinden gecilebilir)
    return cols


COLLIDERS = build_colliders()
print(f"[world] {len(COLLIDERS)} collider olusturuldu")


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

    def is_mouse_locked(self):
        """Mouse kilitli olmali mi? (oyuncu kontrol icin)"""
        return self.current_npc is None

    def enter(self, npc):
        print(f"[dialog] enter() basliyor: {npc.display_name}")
        sys.stdout.flush()
        self.current_npc = npc
        self.state = DialogState.IDLE
        self.last_user_text = ""
        self.last_npc_reply = ""
        self.last_action = ""
        try:
            rl.enable_cursor()
            print("[dialog] cursor enabled")
            sys.stdout.flush()
        except Exception as e:
            print(f"[dialog] cursor enable error: {e}")
            sys.stdout.flush()
        print(f"[dialog] {npc.display_name} ile konusuyorsun")
        sys.stdout.flush()

    def exit_dialog(self):
        print("[dialog] exit_dialog() basliyor")
        sys.stdout.flush()
        if self.state in (DialogState.RECORDING, DialogState.PROCESSING, DialogState.SPEAKING):
            print(f"[dialog] meshgul ({self.state}), cikis engellendi")
            sys.stdout.flush()
            return False
        self.current_npc = None
        self.state = DialogState.IDLE
        try:
            rl.disable_cursor()
        except Exception as e:
            print(f"[dialog] cursor disable error: {e}")
            sys.stdout.flush()
        print("[dialog] cikildi\n")
        sys.stdout.flush()
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
        import traceback
        import random
        try:
            print("[process] basliyor...")
            sys.stdout.flush()

            # 1. STT
            print(f"[process] STT (audio len={len(audio)})...")
            sys.stdout.flush()
            user_text = self.brain.transcribe(audio)
            if not user_text:
                # ===== STT bos dondu - NPC karakterde "anlamadim" desin =====
                print("[process] STT bos dondu - karakterde anlamadim cevabi veriliyor")
                sys.stdout.flush()
                self.last_user_text = "(anlasilmadi)"
                # NPC'nin agzindan rastgele "anlamadim" varyasyonu
                npc_name = self.current_npc.display_name
                fallbacks = [
                    "Pardon, tam duyamadım. Tekrar eder misin?",
                    "Hımm, ne dedin? Biraz daha yüksek sesle söyle.",
                    "Anlamadım seni. Tekrar söyler misin?",
                    "Pardon, gürültüde kaçırdım. Bir daha?",
                    "Affedersin, ne demiştin? Tekrarlayabilir misin?",
                ]
                reply = random.choice(fallbacks)
                self.last_npc_reply = reply
                print(f"  {npc_name}: {reply}")
                sys.stdout.flush()
                # TTS ile soylet
                self.state = DialogState.SPEAKING
                try:
                    self.brain.speak(reply, self.current_npc.voice, blocking=True)
                except Exception as e:
                    print(f"[process] TTS hata: {e}")
                    sys.stdout.flush()
                self.state = DialogState.IDLE
                return
            self.last_user_text = user_text
            print(f"  Sen: {user_text}")
            sys.stdout.flush()

            def log_action(name, args, result):
                msg = result.get("message") or result.get("reason") or ""
                self.last_action = f"{name} -> {msg[:60]}"
                print(f"  [AKSIYON] {name}({args}) -> {msg}  | success={result.get('success')}")
                sys.stdout.flush()
                # Bildirim her tool icin (basarili veya degil) - _set_notification kontrol ediyor
                self._set_notification(name, args, result)

            # 2. LLM
            print("[process] LLM cagriliyor...")
            sys.stdout.flush()
            reply = self.brain.chat(self.current_npc, user_text, action_log=log_action)
            self.last_npc_reply = reply
            print(f"  {self.current_npc.display_name}: {reply}")
            print(f"  [DURUM] {state.summary_tr()}")
            sys.stdout.flush()

            # 3. TTS
            if reply:
                print(f"[process] TTS cagriliyor (voice={self.current_npc.voice})...")
                sys.stdout.flush()
                self.state = DialogState.SPEAKING
                self.brain.speak(reply, self.current_npc.voice, blocking=True)
                print("[process] TTS bitti")
                sys.stdout.flush()
            else:
                print("[process] reply bos, TTS atlandi")
                sys.stdout.flush()
        except Exception as e:
            print(f"[!] Dialog HATA: {type(e).__name__}: {e}")
            print("[!] Full traceback:")
            traceback.print_exc()
            sys.stdout.flush()
            self.last_npc_reply = f"(hata: {e})"
        finally:
            self.state = DialogState.IDLE
            print("[process] bitti, state=IDLE")
            sys.stdout.flush()

    def _set_notification(self, name, args, result):
        # name "give_item" veya "give_item (inline)" olabilir - inline'i kaldir
        clean_name = name.replace(" (inline)", "").strip()

        def to_int(v, default=0):
            try:
                return int(v)
            except (ValueError, TypeError):
                return default

        # Turkce gosterim isimleri
        item_tr = {
            "saglik_iksiri": "Saglik Iksiri",
            "mana_iksiri": "Mana Iksiri",
            "kilic": "Kilic",
            "zirh": "Zirh",
        }

        text = None
        if clean_name == "give_item":
            qty = to_int(args.get("quantity", 1), 1)
            item_name = args.get("item_name", "?")
            item_disp = item_tr.get(item_name, item_name.replace("_", " ").title())
            price = to_int(args.get("price", 0), 0)
            text = f"+ {qty}x {item_disp}"
            if price > 0:
                text += f"  (-{price} altin)"
        elif clean_name == "take_gold":
            amt = to_int(args.get("amount", 0), 0)
            text = f"- {amt} altin"
        elif clean_name == "give_gold":
            amt = to_int(args.get("amount", 0), 0)
            text = f"+ {amt} altin"
        elif clean_name == "offer_quest":
            text = f"Yeni gorev: {args.get('title', '?')}"
        elif clean_name == "complete_quest":
            text = "Gorev tamamlandi!"

        if text:
            self.notification = text
            self.notification_until = time.time() + 4.0
            print(f"[notify] '{text}' set edildi (4sn)")
            sys.stdout.flush()


dialog = DialogManager(brain)


# ====================== Helper ======================
def find_nearby_actor():
    nearest, best = None, INTERACT_RADIUS
    for a in actors:
        d = math.hypot(player.position.x - a.x, player.position.z - a.z)
        if d < best:
            nearest, best = a, d
    return nearest


def world_to_screen(pos: Vector3, camera) -> tuple:
    """3D pozisyonu 2D ekrana cevir (NPC etiketleri icin)."""
    screen = rl.get_world_to_screen(pos, camera)
    return int(screen.x), int(screen.y)


# ====================== UI cizim fonksiyonlari ======================
def draw_text_box(text, x, y, size, text_color, bg_alpha=200, padding=8):
    """Arkasinda yari saydam siyah arka plan olan metin."""
    text_w = tr_measure(text, size)
    bg = Color(0, 0, 0, bg_alpha)
    rl.draw_rectangle(x - padding, y - padding // 2,
                      text_w + padding * 2, size + padding, bg)
    tr_text(text, x, y, size, text_color)


def draw_hud():
    # Sol ust - SADECE gorevler
    quests = state.active_quests
    if quests:
        quest_text = "Görevler: " + (", ".join(q["title"] for q in quests))[:60]
    else:
        quest_text = "Görevler: (yok)"
    draw_text_box(quest_text, 15, 15, 18, rl.WHITE, bg_alpha=160)

    # Sag altta envanter ipucu
    hint = "[I] Envanter"
    hw = tr_measure(hint, 16)
    draw_text_box(hint, WIDTH - hw - 30, HEIGHT - 35, 16, Color(220, 220, 180, 255), bg_alpha=140)

    if debug_mode:
        draw_text_box("[DEBUG - F1]", 15, 50, 14, Color(255, 200, 100, 255), bg_alpha=160)


# Item gorunur isimleri (snake_case -> Turkce gosterim)
ITEM_DISPLAY = {
    "saglik_iksiri": "Sağlık İksiri",
    "mana_iksiri": "Mana İksiri",
    "kilic": "Kılıç",
    "zirh": "Zırh",
    "haydut_kulagi": "Haydut Kulağı",
    "kurt_postu": "Kurt Postu",
}


def item_display_name(key):
    return ITEM_DISPLAY.get(key, key.replace("_", " ").title())


def draw_inventory_panel():
    """I tusuyla acilan envanter paneli - ortada buyuk panel."""
    pw, ph = 500, 420
    px = (WIDTH - pw) // 2
    py = (HEIGHT - ph) // 2

    # Arka karartma
    rl.draw_rectangle(0, 0, WIDTH, HEIGHT, Color(0, 0, 0, 120))
    # Panel
    rl.draw_rectangle(px, py, pw, ph, Color(25, 28, 40, 245))
    rl.draw_rectangle_lines(px, py, pw, ph, Color(180, 160, 100, 255))
    # Ust kalin cizgi
    rl.draw_rectangle(px, py, pw, 50, Color(180, 160, 100, 255))
    tr_text("ENVANTER", px + 20, py + 12, 28, Color(25, 28, 40, 255))

    # Altin (sag ust)
    gold_text = f"Altın: {state.gold}"
    gw = tr_measure(gold_text, 22)
    tr_text(gold_text, px + pw - gw - 20, py + 15, 22, Color(60, 45, 20, 255))

    # Item listesi
    y = py + 75
    if not state.inventory:
        tr_text("Envanterin boş. Satıcılardan eşya al!", px + 20, y, 18, Color(180, 180, 180, 255))
    else:
        tr_text("Eşyalar:", px + 20, y, 20, Color(220, 200, 150, 255))
        y += 35
        for key, qty in state.inventory.items():
            name = item_display_name(key)
            # Item satiri - ikon kutusu + isim + adet
            rl.draw_rectangle(px + 25, y, 36, 36, Color(60, 65, 85, 255))
            rl.draw_rectangle_lines(px + 25, y, 36, 36, Color(120, 120, 140, 255))
            # Basit renk ikonu (item turune gore)
            icon_col = {
                "saglik_iksiri": Color(220, 60, 60, 255),
                "mana_iksiri": Color(60, 100, 220, 255),
                "kilic": Color(200, 200, 210, 255),
                "zirh": Color(150, 150, 170, 255),
            }.get(key, Color(150, 130, 90, 255))
            rl.draw_rectangle(px + 33, y + 8, 20, 20, icon_col)

            tr_text(f"{name}", px + 75, y + 8, 20, rl.WHITE)
            qty_text = f"x{qty}"
            qw = tr_measure(qty_text, 20)
            tr_text(qty_text, px + pw - qw - 30, y + 8, 20, Color(220, 200, 150, 255))
            y += 46

    # Alt bilgi
    tr_text("Kapatmak için [I]", px + 20, py + ph - 35, 16,
            Color(150, 150, 150, 255))


def draw_notification():
    if time.time() >= dialog.notification_until or not dialog.notification:
        return
    text = dialog.notification
    size = 22
    w = tr_measure(text, size)
    x = WIDTH - w - 30
    y = 30
    rl.draw_rectangle(x - 15, y - 8, w + 30, size + 16, Color(30, 30, 20, 230))
    rl.draw_rectangle_lines(x - 15, y - 8, w + 30, size + 16, Color(180, 160, 100, 255))
    tr_text(text, x, y, size, Color(255, 240, 150, 255))


LABEL_VISIBLE_DIST = 12.0   # bu mesafeden uzakta isim gozukmez


def draw_npc_label(actor, camera):
    """NPC kafasinin uzerinde isim - sadece yakinda VE kameranin onunde."""
    # Mesafe kontrolu
    dist = math.hypot(player.position.x - actor.x, player.position.z - actor.z)
    if dist > LABEL_VISIBLE_DIST:
        return

    # KAMERA ONUNDE MI? - dot product ile kontrol
    # Oyuncudan NPC'ye olan yon vektoru
    to_npc_x = actor.x - player.position.x
    to_npc_z = actor.z - player.position.z
    # Oyuncunun bakis yonu (xz duzlemi)
    fwd = player.get_forward()
    dot = to_npc_x * fwd.x + to_npc_z * fwd.z
    if dot <= 0:
        return  # NPC kameranin ARKASINDA, etiketi cizme

    head_pos = Vector3(actor.x, 2.3, actor.z)
    sx, sy = world_to_screen(head_pos, camera)
    # Ekran disindaysa cizme
    if sx < 0 or sx > WIDTH or sy < 0 or sy > HEIGHT:
        return

    # Mesafeye gore saydamlik
    alpha = int(255 * max(0.0, min(1.0, (LABEL_VISIBLE_DIST - dist) / 4.0)))
    alpha = max(60, alpha)

    text = actor.data.display_name
    size = 16
    w = tr_measure(text, size)
    rl.draw_rectangle(sx - w // 2 - 6, sy - 6, w + 12, size + 8, Color(0, 0, 0, min(180, alpha)))
    tr_text(text, sx - w // 2, sy - 2, size, Color(255, 255, 255, alpha))


def draw_dialog_overlay():
    npc = dialog.current_npc
    if not npc:
        return
    # Alt panel
    box_h = 200
    box_y = HEIGHT - box_h - 20
    rl.draw_rectangle(20, box_y, WIDTH - 40, box_h, Color(15, 20, 35, 230))
    rl.draw_rectangle_lines(20, box_y, WIDTH - 40, box_h, Color(180, 160, 100, 255))

    # NPC ismi
    tr_text(npc.display_name, 40, box_y + 12, 26, Color(220, 180, 100, 255))

    # Durum
    status_text, status_col = {
        DialogState.IDLE: ("SPACE basılı tut + konuş + bırak", Color(180, 180, 180, 255)),
        DialogState.RECORDING: ("DİNLENİYOR...", Color(255, 100, 100, 255)),
        DialogState.PROCESSING: ("Düşünüyor...", Color(255, 220, 80, 255)),
        DialogState.SPEAKING: ("Konuşuyor...", Color(100, 220, 255, 255)),
    }[dialog.state]
    sw = tr_measure(status_text, 18)
    tr_text(status_text, WIDTH - 60 - sw, box_y + 18, 18, status_col)

    # User text
    if dialog.last_user_text:
        tr_text(f"Sen: {dialog.last_user_text[:90]}",
                     40, box_y + 60, 18, Color(200, 200, 220, 255))
    # NPC text (wrap if long)
    if dialog.last_npc_reply:
        reply_text = f"{npc.display_name}: {dialog.last_npc_reply}"
        # Basit wrap
        max_chars = 110
        lines_to_draw = []
        words = reply_text.split()
        current = ""
        for w in words:
            test = (current + " " + w).strip()
            if len(test) > max_chars:
                lines_to_draw.append(current)
                current = w
            else:
                current = test
        if current:
            lines_to_draw.append(current)
        for i, ln in enumerate(lines_to_draw[:3]):
            tr_text(ln, 40, box_y + 100 + i * 24, 18, Color(255, 240, 200, 255))

    if debug_mode and dialog.last_action:
        tr_text(f"[Aksiyon] {dialog.last_action}",
                     40, box_y + 175, 14, Color(130, 200, 130, 255))

    # Kayit gostergesi (kirmizi yanip sonen nokta)
    if dialog.state == DialogState.RECORDING:
        pulse = int(127 + 128 * abs(math.sin(time.time() * 5)))
        rl.draw_circle(WIDTH - 80, box_y + 30, 10, Color(pulse, 30, 30, 255))


def draw_near_hint(nearby):
    if not nearby:
        return
    text = f"[E] {nearby.data.display_name} ile konuş"
    size = 22
    w = tr_measure(text, size)
    x = (WIDTH - w) // 2
    y = HEIGHT // 2 + 40
    rl.draw_rectangle(x - 14, y - 6, w + 28, size + 12, Color(0, 0, 0, 200))
    tr_text(text, x, y, size, Color(255, 240, 100, 255))


def draw_crosshair():
    # Ekran ortasinda kucuk + isareti
    cx, cy = WIDTH // 2, HEIGHT // 2
    rl.draw_rectangle(cx - 5, cy - 1, 10, 2, rl.WHITE)
    rl.draw_rectangle(cx - 1, cy - 5, 2, 10, rl.WHITE)


# Pause menu buton dikdortgenleri (global, click kontrolu icin)
_btn_devam = None
_btn_cikis = None


def draw_pause_menu():
    """ESC menusu - Devam Et / Cikis butonlari. Mouse hover + click."""
    global _btn_devam, _btn_cikis

    # Arka karartma
    rl.draw_rectangle(0, 0, WIDTH, HEIGHT, Color(0, 0, 0, 160))

    # Baslik
    title = "DURAKLATILDI"
    tw = tr_measure(title, 40)
    tr_text(title, (WIDTH - tw) // 2, HEIGHT // 2 - 140, 40, Color(220, 200, 150, 255))

    mx, my = int(rl.get_mouse_x()), int(rl.get_mouse_y())

    # Buton boyutlari
    bw, bh = 280, 60
    bx = (WIDTH - bw) // 2

    # Devam Et butonu
    dy1 = HEIGHT // 2 - 40
    _btn_devam = (bx, dy1, bw, bh)
    hover1 = bx <= mx <= bx + bw and dy1 <= my <= dy1 + bh
    col1 = Color(90, 130, 90, 255) if hover1 else Color(60, 90, 60, 255)
    rl.draw_rectangle(bx, dy1, bw, bh, col1)
    rl.draw_rectangle_lines(bx, dy1, bw, bh, Color(150, 200, 150, 255))
    t1 = "Devam Et"
    t1w = tr_measure(t1, 26)
    tr_text(t1, bx + (bw - t1w) // 2, dy1 + 16, 26, rl.WHITE)

    # Cikis butonu
    dy2 = HEIGHT // 2 + 40
    _btn_cikis = (bx, dy2, bw, bh)
    hover2 = bx <= mx <= bx + bw and dy2 <= my <= dy2 + bh
    col2 = Color(150, 70, 70, 255) if hover2 else Color(110, 50, 50, 255)
    rl.draw_rectangle(bx, dy2, bw, bh, col2)
    rl.draw_rectangle_lines(bx, dy2, bw, bh, Color(200, 150, 150, 255))
    t2 = "Çıkış"
    t2w = tr_measure(t2, 26)
    tr_text(t2, bx + (bw - t2w) // 2, dy2 + 16, 26, rl.WHITE)

    # Alt ipucu
    hint = "ESC ile devam et"
    hw = tr_measure(hint, 16)
    tr_text(hint, (WIDTH - hw) // 2, HEIGHT // 2 + 130, 16, Color(160, 160, 160, 255))


def pause_menu_click():
    """Pause menude tiklama kontrolu. 'devam', 'cikis' veya None doner."""
    if not rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return None
    mx, my = int(rl.get_mouse_x()), int(rl.get_mouse_y())
    if _btn_devam:
        bx, by, bw, bh = _btn_devam
        if bx <= mx <= bx + bw and by <= my <= by + bh:
            return "devam"
    if _btn_cikis:
        bx, by, bw, bh = _btn_cikis
        if bx <= mx <= bx + bw and by <= my <= by + bh:
            return "cikis"
    return None


# ====================== Ana dongu ======================
# ESC'in pencereyi kapatmasini ENGELLE (biz pause menu icin kullanacagiz)
rl.set_exit_key(rl.KeyboardKey.KEY_NULL)

space_was_down = False
inventory_open = False
paused = False
print("[ready] Oyun calisiyor. WASD = hareket, E = konus, I = envanter, ESC = menu\n")

while not rl.window_should_close():
    dt = rl.get_frame_time()
    # Mouse serbest olmali mi: diyalog/envanter/pause acik ise
    mouse_active = (dialog.is_mouse_locked() and not inventory_open and not paused)

    # ----- INPUT -----
    if rl.is_key_pressed(rl.KeyboardKey.KEY_F1):
        debug_mode = not debug_mode
        print(f"[debug] {'ACIK' if debug_mode else 'KAPALI'}")

    if paused:
        # ===== PAUSE MENU acik =====
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            # ESC ile devam et
            paused = False
            rl.disable_cursor()
        else:
            click = pause_menu_click()
            if click == "devam":
                paused = False
                rl.disable_cursor()
            elif click == "cikis":
                break  # oyundan cik
    elif inventory_open:
        # ===== ENVANTER acik ===== (sadece I ile kapanir)
        if rl.is_key_pressed(rl.KeyboardKey.KEY_I):
            inventory_open = False
            rl.disable_cursor()
    elif dialog.current_npc is not None:
        # ===== DIYALOG modu =====
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            dialog.exit_dialog()
        # Push-to-talk (SPACE basili tut)
        space_now = rl.is_key_down(rl.KeyboardKey.KEY_SPACE)
        if space_now and not space_was_down:
            if dialog.state == DialogState.IDLE:
                dialog.start_recording()
        elif not space_now and space_was_down:
            if dialog.state == DialogState.RECORDING:
                dialog.stop_recording_and_process()
        space_was_down = space_now
    else:
        # ===== EXPLORING modu =====
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            # Pause menu ac
            paused = True
            rl.enable_cursor()
        if rl.is_key_pressed(rl.KeyboardKey.KEY_I):
            inventory_open = True
            rl.enable_cursor()
        if rl.is_key_pressed(rl.KeyboardKey.KEY_E):
            nearby = find_nearby_actor()
            if nearby:
                dialog.enter(nearby.data)

    # ----- UPDATE -----
    player.update(dt, mouse_active)

    # ----- DRAW -----
    rl.begin_drawing()
    rl.clear_background(Color(135, 165, 200, 255))  # gokyuzu

    camera = player.get_camera()
    rl.begin_mode_3d(camera)

    # Zemin (cim)
    rl.draw_plane(Vector3(0, 0, 0), Vector2(60, 60), Color(80, 130, 70, 255))

    # Yol haci
    rl.draw_cube(Vector3(0, 0.02, 0), 40, 0.04, 4, Color(140, 115, 85, 255))
    rl.draw_cube(Vector3(0, 0.02, 0), 4, 0.04, 40, Color(140, 115, 85, 255))

    # Dekorasyon
    draw_decorations()

    # NPC'ler
    for a in actors:
        a.draw()

    rl.end_mode_3d()

    # ----- 2D HUD -----
    for a in actors:
        draw_npc_label(a, camera)

    draw_hud()
    draw_notification()

    if paused:
        draw_pause_menu()
    elif inventory_open:
        draw_inventory_panel()
    elif dialog.current_npc is None:
        nearby = find_nearby_actor()
        draw_near_hint(nearby)
        draw_crosshair()
    else:
        draw_dialog_overlay()

    rl.end_drawing()

rl.close_window()
print("[bye]")
