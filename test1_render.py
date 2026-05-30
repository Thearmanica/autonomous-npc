"""
Test 1: Sadece bir kup ekranda gozukuyor mu?
Eger bu BEYAZ ise sistem-level shader sorunu var.
Eger RENKLI bir kup gorursen render OK, sorun game_3d.py'de.
"""

print("Test 1 basliyor...")

from panda3d.core import loadPrcFileData
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'fullscreen 0')

from ursina import Ursina, Entity, color, EditorCamera

app = Ursina()

# Editor kamera - mouse ile dondurulebilir, debug icin ideal
EditorCamera()

# Tek bir KIRMIZI kup, hicbir texture yok
cube = Entity(model='cube', color=color.red, scale=2, position=(0, 0, 0))

# Bir mavi kup
cube2 = Entity(model='cube', color=color.azure, scale=1.5, position=(3, 0, 0))

# Bir sari kup
cube3 = Entity(model='cube', color=color.yellow, scale=1.5, position=(-3, 0, 0))

print("3 farkli renkli kup ekrandalik. Mouse'la cevirin.")
print("ESC = cik")

app.run()
