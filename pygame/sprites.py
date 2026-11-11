"""Carga los sprites ya preparados por tools/build_assets.py y los escala
una sola vez al tamaño de uso."""
import json
import os

import pygame

from config import ASSETS, RED, YELLOW, BLUE

COLOR_FILES = {RED: "red", YELLOW: "yellow", BLUE: "blue"}


def load(name):
    return pygame.image.load(os.path.join(ASSETS, name)).convert_alpha()


def load_meta():
    with open(os.path.join(ASSETS, "meta.json")) as f:
        return json.load(f)


def fit(surf, w, h):
    """Escala manteniendo proporcion para entrar en w x h."""
    sw, sh = surf.get_size()
    k = min(w / sw, h / sh)
    return pygame.transform.smoothscale(surf, (max(1, round(sw * k)), max(1, round(sh * k))))


def frasco_layout(meta, board_w, board_h, pad, squash_top, screen_h):
    """Escala y franjas del frasco para que su hueco interior envuelva un
    tablero de board_w x board_h. El cuello se achata (squash_top) y el
    cuerpo recto se estira lo necesario."""
    f = meta["frasco"]
    fw, fh = f["size"]
    ix, iy, iw, ih = f["inner"]
    top_end, bot_start = f["top_end"], f["bot_start"]
    s = (board_w + 2 * pad) / iw
    top_h = round(top_end * s * squash_top)
    inner_top = iy * s * squash_top
    bot_h = round((fh - bot_start) * s)
    inner_bot = (iy + ih - bot_start) * s
    mid_h = round(board_h + 2 * pad - (top_h - inner_top) - inner_bot)
    h = top_h + mid_h + bot_h
    return dict(w=round(fw * s), h=h, y=(screen_h - h) // 2,
                top_h=top_h, mid_h=mid_h, bot_h=bot_h,
                board_dx=round(ix * s) + pad, board_dy=round(inner_top) + pad)


class Sprites:
    def __init__(self, cell, meta, layout, doctor_h, lupa_h):
        self.cell = cell

        # virus: 3 cuadros de balanceo cada uno
        self.virus_raw = {c: load(f"virus_{n}.png") for c, n in COLOR_FILES.items()}
        self.virus = {}
        for c, img in self.virus_raw.items():
            base = fit(img, cell + 5, cell + 5)  # las patitas pueden asomar
            self.virus[c] = [pygame.transform.rotozoom(base, a, 1.0) for a in (-10, 0, 10)]

        # mitades de pastilla en las 4 orientaciones + pedazo suelto
        self.half, self.single = {}, {}
        pad = max(2, cell // 8)
        hw, hh = (cell - 2 * pad) // 2, cell - 2 * pad
        for c, n in COLOR_FILES.items():
            left, right = load(f"half_left_{n}.png"), load(f"half_right_{n}.png")
            L = pygame.transform.smoothscale(left, (cell, cell))
            R = pygame.transform.smoothscale(right, (cell, cell))
            self.half[(c, "R")] = L                                  # pareja a la derecha
            self.half[(c, "L")] = R                                  # pareja a la izquierda
            self.half[(c, "D")] = pygame.transform.rotate(L, -90)    # mitad de arriba
            self.half[(c, "U")] = pygame.transform.rotate(R, -90)    # mitad de abajo
            one = pygame.Surface((cell, cell), pygame.SRCALPHA)      # media + media
            one.blit(pygame.transform.smoothscale(left, (hw, hh)), (pad, pad))
            one.blit(pygame.transform.smoothscale(right, (hw, hh)), (pad + hw, pad))
            self.single[c] = one

        # frasco en 3 franjas: cuello, cuerpo (se estira) y base
        src = load("frasco.png")
        f = meta["frasco"]
        fw_src, fh_src = f["size"]
        frame = pygame.Surface((layout["w"], layout["h"]), pygame.SRCALPHA)
        y = 0
        for (a, b), h in (((0, f["top_end"]), layout["top_h"]),
                          ((f["top_end"], f["bot_start"]), layout["mid_h"]),
                          ((f["bot_start"], fh_src), layout["bot_h"])):
            piece = src.subsurface((0, a, fw_src, b - a))
            frame.blit(pygame.transform.smoothscale(piece, (layout["w"], h)), (0, y))
            y += h
        self.frasco = frame

        # doctor animado
        n = meta["doctor"]["frames"]
        self.doctor = [fit(load(f"doctor_{i}.png"), 10000, doctor_h) for i in range(n)]
        self.doctor_scale = doctor_h / meta["doctor"]["height"]

        # lupa
        src = load("lupa.png")
        k = lupa_h / src.get_height()
        self.lupa = pygame.transform.smoothscale(src, (round(src.get_width() * k), lupa_h))
        cx, cy, r = meta["lupa"]["lens"]
        self.lupa_lens = (round(cx * k), round(cy * k), round(r * k))

    def virus_big(self, col, size):
        return fit(self.virus_raw[col], size, size)
