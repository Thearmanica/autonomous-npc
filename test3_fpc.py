"""
Test 3: FirstPersonController ile 3 kup
Test 1 calistiysa ama bu calismazsa, FPC bizim sorunumuz.
WASD ile gez, kuplerin renkli oldugunu gor.
"""

print("Test 3 basliyor...")

from panda3d.core import loadPrcFileData
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen 0')

from ursina import Ursina, Entity, color
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()

# Zemin - olmasin player dussun
ground = Entity(model='cube', color=color.rgb(80, 130, 70),
                scale=(40, 0.1, 40), position=(0, -0.05, 0), collider='box')

# 3 farkli renkli kup, player'in ONUNDE
Entity(model='cube', color=color.red, scale=2, position=(0, 1, 5))
Entity(model='cube', color=color.azure, scale=2, position=(-4, 1, 5))
Entity(model='cube', color=color.yellow, scale=2, position=(4, 1, 5))

# Player - kuplere bakacak sekilde
player = FirstPersonController(position=(0, 1, 0), speed=8)

print("WASD = hareket, mouse = bak.")
print("3 renkli kup gormeli (kirmizi/mavi/sari).")

app.run()
