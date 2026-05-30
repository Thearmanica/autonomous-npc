"""
Test 6: Test 5 + binalar. NPC ARKASINDA bina var.
Test 5 calistiysa ama Test 6 calismazsa, bina entityleri sorunlu.
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


def make_building(x, z, c):
    """Test 6 ekstra: bina."""
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
    # Bina arkada
    make_building(nx, nz + 3, building_c)

    # NPC govde
    body = Entity(model='cube', color=c, scale=(1.1, 1.3, 0.7),
                  position=(nx, 1.6, nz), collider='box')
    # Kafa
    Entity(model='sphere', color=color.rgb(230, 190, 160),
           scale=0.6, position=(nx, 2.55, nz))
    # Label
    Text(f"NPC {nx},{nz}", position=(0, 3.2, 0), parent=body,
         scale=20, billboard=True, background=True, color=color.white)

player = FirstPersonController(position=(0, 1, 0), speed=8)

print("4 NPC + 4 bina. 16 entity. Renkli gormeli.")

app.run()
