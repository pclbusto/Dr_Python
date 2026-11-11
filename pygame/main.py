"""Dr. Python - puzzle de pastillas y virus con Pygame.

Uso:  python main.py [--fullscreen | --window] [--scale N]

Todo se dibuja directo a la resolucion real: el diseño es de 640x480 y se
multiplica por la escala de la pantalla (1 en 640x480, 1.5 en 1280x720 o
720x720, 2.25 en 1920x1080), con barras negras si la proporcion no es 4:3.
Los sprites se generan a ese tamaño desde las hojas originales y quedan en
cache, asi que solo el primer arranque en cada resolucion tarda mas.

Por defecto ("auto") usa pantalla completa cuando no hay escritorio
(consola / KMS, como en una Anbernic) y ventana cuando lo hay.
--scale N agranda la ventana en el escritorio (ej. --scale 2 -> 1280x960).
"""
import os
import sys

import pygame

from config import MAX_DT, load_settings
from controls import Controls
from game import Game
from renderer import Renderer, BASE_W, BASE_H

FPS = 60


def want_fullscreen(settings, argv):
    if "--fullscreen" in argv:
        return True
    if "--window" in argv:
        return False
    mode = settings.get("fullscreen", "auto")
    if mode == "auto":
        return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return bool(mode)


def window_scale(settings, argv):
    if "--scale" in argv:
        try:
            return max(1.0, float(argv[argv.index("--scale") + 1]))
        except (IndexError, ValueError):
            pass
    return max(1.0, float(settings.get("window_scale", 1)))


def open_display(fullscreen, wscale):
    """Devuelve (pantalla, area de dibujo, escala). El area es una
    subsuperficie centrada de la pantalla: se dibuja ahi sin copiar."""
    if fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
    else:
        screen = pygame.display.set_mode((round(BASE_W * wscale), round(BASE_H * wscale)))
    sw, sh = screen.get_size()
    scale = min(sw / BASE_W, sh / BASE_H)
    w, h = round(BASE_W * scale), round(BASE_H * scale)
    area = pygame.Rect(((sw - w) // 2, (sh - h) // 2), (w, h))
    screen.fill((0, 0, 0))
    return screen, screen.subsurface(area), scale


def show_building(screen):
    """Aviso mientras se generan los sprites por primera vez."""
    screen.fill((0, 0, 0))
    font = pygame.font.Font(None, max(20, screen.get_height() // 20))
    img = font.render("Preparando graficos para esta pantalla...", True, (230, 235, 245))
    screen.blit(img, img.get_rect(center=screen.get_rect().center))
    pygame.display.flip()


def main(argv):
    pygame.init()
    pygame.display.set_caption("Dr. Python")
    settings = load_settings()
    screen, canvas, scale = open_display(want_fullscreen(settings, argv), window_scale(settings, argv))

    controls = Controls()
    game = Game(controls)
    renderer = Renderer(scale, on_build=lambda: show_building(screen))
    screen.fill((0, 0, 0))
    clock = pygame.time.Clock()

    while not game.quit:
        dt = min(clock.tick(FPS), MAX_DT)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                game.quit = True
            elif e.type == pygame.WINDOWFOCUSLOST:
                game.on_focus_lost()
            elif e.type == pygame.WINDOWEXPOSED:
                screen.fill((0, 0, 0))  # repinta las barras negras
            controls.handle(e)
        controls.update(dt)
        game.update(dt)
        controls.end_frame()

        renderer.update(dt, game)
        renderer.draw(canvas, game)
        pygame.display.flip()

    controls.save()
    pygame.quit()


if __name__ == "__main__":
    main(sys.argv[1:])
