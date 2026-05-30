"""
Test 5: Test 4 calistigi temele NPCActor benzeri yapi ekle.
4 NPC = 4 govde + 4 kafa + 4 etiket = 12 entity.
Beyaz olursa parent=body sorunlu.
"""

import sys

from npc_brain import NPCBrain
brain = NPCBrain()
print("AI brain HAZIR.")

from panda3d.core import loadPrcFileData
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen 0')

from ursina import Ursina, Entity, Text, color
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()

# Zemin
ground = Entity(model='cube', color=color.rgb(80, 130, 70),
                scale=(40, 0.1, 40), position=(0, -0.05, 0), collider='box')

# 4 "NPC" - sade
npc_positions = [
    (-8, 5, color.red),
    (8, 5, color.azure),
    (-8, -5, color.yellow),
    (8, -5, color.magenta),
]

for nx, nz, c in npc_positions:
    # Govde
    body = Entity(model='cube', color=c, scale=(1.1, 1.3, 0.7),
                  position=(nx, 1.6, nz), collider='box')
    # Kafa
    Entity(model='sphere', color=color.rgb(230, 190, 160),
           scale=0.6, position=(nx, 2.55, nz))
    # Label - parent=body ile (kritik test!)
    Text(f"NPC {nx},{nz}", position=(0, 3.2, 0), parent=body,
         scale=20, billboard=True, background=True, color=color.white)

player = FirstPersonController(position=(0, 1, 0), speed=8)

print("4 NPC renkli olmali (kirmizi/mavi/sari/pembe).")

app.run()
