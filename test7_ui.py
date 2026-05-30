"""
Test 7: Test 6 + cesitli UI text'leri.
Test 6 calistiysa ve Test 7 calismazsa, UI text'leri sorun.
"""

import sys

from npc_brain import NPCBrain
brain = NPCBrain()
print("AI brain HAZIR.")

from panda3d.core import loadPrcFileData
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen 0')

from ursina import Ursina, Entity, Text, color, camera
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()

# Zemin
ground = Entity(model='cube', color=color.rgb(80, 130, 70),
                scale=(40, 0.1, 40), position=(0, -0.05, 0), collider='box')


def make_building(x, z, c):
    Entity(model='cube', color=color.rgb(*c), scale=(6, 3.5, 6),
           position=(x, 1.75, z), collider='box')
    Entity(model='cube', color=color.rgb(150, 60, 50),
           scale=(7, 0.5, 7), position=(x, 3.7, z), rotation=(0, 45, 0))
    Entity(model='cube', color=color.rgb(60, 40, 25),
           scale=(1.2, 2, 0.2), position=(x, 1, z - 3.1))


npc_positions = [
    (-8, 5, color.red, (120, 100, 90)),
    (8, 5, color.azure, (220, 130, 180)),
    (-8, -5, color.yellow, (80, 120, 180)),
    (8, -5, color.magenta, (220, 190, 100)),
]

for nx, nz, c, building_c in npc_positions:
    make_building(nx, nz + 3, building_c)
    body = Entity(model='cube', color=c, scale=(1.1, 1.3, 0.7),
                  position=(nx, 1.6, nz), collider='box')
    Entity(model='sphere', color=color.rgb(230, 190, 160),
           scale=0.6, position=(nx, 2.55, nz))
    Text(f"NPC {nx},{nz}", position=(0, 3.2, 0), parent=body,
         scale=20, billboard=True, background=True, color=color.white)

player = FirstPersonController(position=(0, 1, 0), speed=8)

# ===== Test 7 ekstrasi: UI text'leri =====
hud = Text(text='Altin: 100\nEnvanter: bos\nGorevler: yok',
           position=(-0.86, 0.48), scale=1, color=color.white,
           background=True, origin=(-0.5, 0.5))

# Hicbir sey yoksa bu Text'in arkasinda quad var, sorun belki bu
notif = Text(text='', position=(0.55, 0.45), scale=1.3,
             color=color.yellow, background=True, enabled=False)

# Dialog Text'leri (gizli)
dialog_name = Text(parent=camera.ui, text='hidden', position=(-0.82, -0.18),
                   scale=1.5, color=color.yellow, background=True, enabled=False)
dialog_status = Text(parent=camera.ui, text='hidden', position=(0.45, -0.18),
                     scale=1, color=color.gray, background=True, enabled=False)
dialog_user = Text(parent=camera.ui, text='hidden', position=(-0.82, -0.27),
                   scale=0.9, color=color.azure, background=True, enabled=False)
dialog_npc = Text(parent=camera.ui, text='hidden', position=(-0.82, -0.36),
                  scale=0.9, color=color.white, background=True, enabled=False)
near_hint = Text(parent=camera.ui, text='hint', position=(0, -0.05),
                 scale=1.4, color=color.yellow, background=True, enabled=False)

print("Test 7: NPC + UI text'leri. NPC'ler RENKLI gormeli.")

app.run()
