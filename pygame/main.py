"""Dr. Python - puzzle de pastillas y virus con Pygame.

Uso:  python main.py [--fullscreen | --window]

El juego se dibuja siempre en un lienzo de 640x480. En ventana se muestra
1:1; en pantalla completa se escala a la resolucion nativa con barras
negras (ej. 720x720 -> 720x540, 1280x720 -> 960x720).
Por defecto ("auto") usa pantalla completa cuando no hay escritorio
(consola / KMS, como en una Anbernic) y ventana cuando lo hay.
"""
import os
import sys

import pygame

from config import MAX_DT, load_settings
from controls import Controls
from game import Game
from renderer import Renderer, W, H

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


def open_display(fullscreen):
    """Devuelve (pantalla, lienzo, rect destino). Si lienzo es la pantalla,
    no hace falta escalar."""
    if fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
    else:
        screen = pygame.display.set_mode((W, H))
    sw, sh = screen.get_size()
    if (sw, sh) == (W, H):
        return screen, screen, None
    scale = min(sw / W, sh / H)
    size = (round(W * scale), round(H * scale))
    dest = pygame.Rect(((sw - size[0]) // 2, (sh - size[1]) // 2), size)
    return screen, pygame.Surface((W, H)).convert(), dest


def main(argv):
    pygame.init()
    pygame.display.set_caption("Dr. Python")
    screen, canvas, dest = open_display(want_fullscreen(load_settings(), argv))

    controls = Controls()
    game = Game(controls)
    renderer = Renderer()
    clock = pygame.time.Clock()

    while not game.quit:
        dt = min(clock.tick(FPS), MAX_DT)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                game.quit = True
            elif e.type == pygame.WINDOWFOCUSLOST:
                game.on_focus_lost()
            controls.handle(e)
        controls.update(dt)
        game.update(dt)
        controls.end_frame()

        renderer.update(dt, game)
        renderer.draw(canvas, game)
        if dest:
            screen.fill((0, 0, 0))
            # scale (no smoothscale): mucho mas barato por cuadro en ARM
            screen.blit(pygame.transform.scale(canvas, dest.size), dest)
        pygame.display.flip()

    controls.save()
    pygame.quit()


if __name__ == "__main__":
    main(sys.argv[1:])
