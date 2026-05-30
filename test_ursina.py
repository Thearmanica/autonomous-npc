"""
Minimal Ursina test - hicbir AI yok, sadece pencere ac.
Eger bu calismiyorsa Ursina'da bir sorun var.
Eger calisiyorsa game_3d.py'da bir sorun var.
"""

print("[1] Panda3D config yukleniyor...")
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen #f')
print("[2] Panda3D config OK")

print("[3] Ursina import ediliyor...")
from ursina import Ursina, Entity, color
print("[4] Ursina import OK")

print("[5] Ursina() baslatiliyor...")
app = Ursina()
print("[6] Ursina baslatildi")

print("[7] Bir kup ekliyorum...")
cube = Entity(model='cube', color=color.orange, scale=2)
print("[8] Kup eklendi, app.run() cagriliyor...")

app.run()
print("[9] Pencere kapandi.")
