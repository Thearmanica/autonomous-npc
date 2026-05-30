"""
Test 4: Test 3'un kopyasi + NPCBrain init ONCE
Eger Test 3 calisip Test 4 calismazsa, NPCBrain init sorun.
"""

import sys

print("Test 4: AI brain init ONCE...")

# NPCBrain'i ONCE yukle
from npc_brain import NPCBrain
brain = NPCBrain()
print("AI brain HAZIR. Ursina baslatiliyor...")

from panda3d.core import loadPrcFileData
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen 0')

from ursina import Ursina, Entity, color
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()

ground = Entity(model='cube', color=color.rgb(80, 130, 70),
                scale=(40, 0.1, 40), position=(0, -0.05, 0), collider='box')

Entity(model='cube', color=color.red, scale=2, position=(0, 1, 5))
Entity(model='cube', color=color.azure, scale=2, position=(-4, 1, 5))
Entity(model='cube', color=color.yellow, scale=2, position=(4, 1, 5))

player = FirstPersonController(position=(0, 1, 0), speed=8)

print("WASD = hareket. Kupleri ve zemini gormelisin.")

app.run()
