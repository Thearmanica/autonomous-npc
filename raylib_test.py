"""
Raylib minimal test - 3D sahne ac, WASD ile gez.
Eger calisirsa Raylib kurulumun OK, Ursina'dan vazgec, Raylib ile devam et.

Kurulum:
  pip install raylib

Cikis: ESC
"""

import pyray as rl
from pyray import Vector3, Color

# Pencere
rl.init_window(1280, 720, "Raylib Test - Otonom NPC Demo")
rl.set_target_fps(60)
rl.disable_cursor()  # mouse kilitle (FPS feel)

# Kamera - first person
camera = rl.Camera3D()
camera.position = Vector3(0, 2, -10)
camera.target = Vector3(0, 1, 0)
camera.up = Vector3(0, 1, 0)
camera.fovy = 70.0
camera.projection = rl.CAMERA_PERSPECTIVE

# Sahne nesneleri (positions and colors)
cubes = [
    (Vector3(0, 1, 0), Color(220, 50, 50, 255)),      # kirmizi
    (Vector3(4, 1, 0), Color(50, 100, 220, 255)),     # mavi
    (Vector3(-4, 1, 0), Color(220, 200, 50, 255)),    # sari
    (Vector3(8, 1, 0), Color(200, 50, 200, 255)),     # pembe
]

print("Raylib 3D test calisiyor.")
print("WASD = hareket, Mouse = bak, ESC = cikis")

while not rl.window_should_close():
    # Kamera kontrolu (FPS-style)
    rl.update_camera(camera, rl.CAMERA_FIRST_PERSON)

    # Cizim
    rl.begin_drawing()
    rl.clear_background(Color(135, 165, 200, 255))  # gokyuzu mavisi

    rl.begin_mode_3d(camera)
    
    # Zemin (genis duz)
    rl.draw_plane(Vector3(0, 0, 0), rl.Vector2(40, 40), Color(80, 130, 70, 255))

    # 4 renkli kup
    for pos, col in cubes:
        rl.draw_cube(pos, 1.5, 2.0, 1.5, col)
        rl.draw_cube_wires(pos, 1.5, 2.0, 1.5, rl.BLACK)

    # Yol haci (z-fighting yok, draw_plane farkli)
    rl.draw_cube(Vector3(0, 0.05, 0), 30, 0.1, 3, Color(140, 115, 85, 255))
    rl.draw_cube(Vector3(0, 0.05, 0), 3, 0.1, 30, Color(140, 115, 85, 255))

    rl.draw_grid(40, 1.0)  # debug grid

    rl.end_mode_3d()

    # HUD
    rl.draw_text("Raylib 3D test - WASD + Mouse", 10, 10, 20, rl.WHITE)
    rl.draw_text("4 renkli kup gormeli, FPS sayaci sag ust", 10, 35, 16, rl.WHITE)
    rl.draw_fps(1200, 10)

    rl.end_drawing()

rl.close_window()
print("Test bitti.")
