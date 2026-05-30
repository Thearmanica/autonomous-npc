"""
Test 2: Eger Test 1 beyazsa, shader probleminin oldugunu kanitlamak icin
explicit unlit shader kullan.
"""

print("Test 2 basliyor (unlit shader)...")

from panda3d.core import loadPrcFileData
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen 0')

from ursina import Ursina, Entity, color, EditorCamera
from ursina.shaders import unlit_shader

app = Ursina()

EditorCamera()

# unlit shader ile - bu lighting'i devre disi birakir, ham renk gosterir
cube = Entity(model='cube', color=color.red, scale=2, position=(0, 0, 0),
              shader=unlit_shader)
cube2 = Entity(model='cube', color=color.azure, scale=1.5, position=(3, 0, 0),
               shader=unlit_shader)
cube3 = Entity(model='cube', color=color.yellow, scale=1.5, position=(-3, 0, 0),
               shader=unlit_shader)

print("Unlit shader ile 3 kup. Renkler gozukmeli.")

app.run()
