"""Carga y recorta los sprites de la carpeta assets/."""
import os

import pygame

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# medidas del frasco original (frasco.png, 887x1774)
FRASCO_SIZE = (887, 1774)
FRASCO_INNER = pygame.Rect(126, 509, 636, 1097)   # hueco interior
FRASCO_TOP_END = 600                              # fin del cuello/hombros
FRASCO_BOT_START = 1500                           # inicio de la base

# centro y radio interior de la lente en lupa.png (1212x1297)
LUPA_LENS = (700, 465, 330)


def load(name):
    return pygame.image.load(os.path.join(ASSETS, name)).convert_alpha()


def blobs(surf, min_area=2000):
    """Rectangulos de cada sprite separado por transparencia."""
    mask = pygame.mask.from_surface(surf, 64)
    return [r for r in mask.get_bounding_rects() if r.w * r.h >= min_area]


def fit(surf, w, h):
    """Escala manteniendo proporcion para entrar en w x h."""
    sw, sh = surf.get_size()
    k = min(w / sw, h / sh)
    return pygame.transform.smoothscale(surf, (max(1, round(sw * k)), max(1, round(sh * k))))


def frasco_layout(board_w, board_h, pad, squash_top, screen_h):
    """Calcula escala y posiciones para que el hueco interior del frasco
    envuelva un tablero de board_w x board_h. Devuelve un dict."""
    s = (board_w + 2 * pad) / FRASCO_INNER.w
    top_h = round(FRASCO_TOP_END * s * squash_top)
    inner_top = FRASCO_INNER.y * s * squash_top
    bot_h = round((FRASCO_SIZE[1] - FRASCO_BOT_START) * s)
    inner_bot = (FRASCO_INNER.bottom - FRASCO_BOT_START) * s
    mid_h = round(board_h + 2 * pad - (top_h - inner_top) - inner_bot)
    w = round(FRASCO_SIZE[0] * s)
    h = top_h + mid_h + bot_h
    y = (screen_h - h) // 2
    return dict(scale=s, w=w, h=h, y=y, top_h=top_h, mid_h=mid_h, bot_h=bot_h,
                board_dx=round(FRASCO_INNER.x * s) + pad,
                board_dy=round(inner_top) + pad)


class Sprites:
    def __init__(self, cell, colors, layout, doctor_h=190, lupa_h=190):
        RED, YELLOW, BLUE = colors
        self.cell = cell

        # ---- virus: hoja con amarillo, azul, rojo (izq a der)
        sheet = load("virus.png")
        rects = sorted(blobs(sheet), key=lambda r: r.x)
        raw = dict(zip((YELLOW, BLUE, RED), (sheet.subsurface(r) for r in rects)))
        self.virus_raw = raw
        self.virus = {}
        for col, img in raw.items():
            base = fit(img, cell + 5, cell + 5)  # las patitas pueden asomar
            # 3 cuadros de balanceo
            self.virus[col] = [pygame.transform.rotozoom(base, a, 1.0) for a in (-10, 0, 10)]

        # ---- capsulas: fila 1 enteras (rojo, azul, amarillo),
        #      fila 3 mitades: izquierdas r/a/am, derechas r/a/am
        sheet = load("capsulas.png")
        rects = blobs(sheet)
        halves = sorted([r for r in rects if r.y > sheet.get_height() * 0.6], key=lambda r: r.x)
        order = (RED, BLUE, YELLOW)
        left = {c: sheet.subsurface(r) for c, r in zip(order, halves[:3])}
        right = {c: sheet.subsurface(r) for c, r in zip(order, halves[3:6])}
        self.half = {}
        self.single = {}
        for c in order:
            L = pygame.transform.smoothscale(left[c], (cell, cell))
            R = pygame.transform.smoothscale(right[c], (cell, cell))
            self.half[(c, "R")] = L                                  # pareja a la derecha
            self.half[(c, "L")] = R                                  # pareja a la izquierda
            self.half[(c, "D")] = pygame.transform.rotate(L, -90)    # mitad de arriba
            self.half[(c, "U")] = pygame.transform.rotate(R, -90)    # mitad de abajo
            # pedazo suelto: media izquierda + media derecha => redondito
            pad = max(2, cell // 8)
            hw, hh = (cell - 2 * pad) // 2, cell - 2 * pad
            one = pygame.Surface((cell, cell), pygame.SRCALPHA)
            one.blit(pygame.transform.smoothscale(left[c], (hw, hh)), (pad, pad))
            one.blit(pygame.transform.smoothscale(right[c], (hw, hh)), (pad + hw, pad))
            self.single[c] = one

        # ---- frasco en 3 franjas (cuello, cuerpo estirable, base)
        src = load("frasco.png")
        L = layout
        fw = L["w"]
        frame = pygame.Surface((fw, L["h"]), pygame.SRCALPHA)
        parts = (
            ((0, FRASCO_TOP_END), L["top_h"]),
            ((FRASCO_TOP_END, FRASCO_BOT_START), L["mid_h"]),
            ((FRASCO_BOT_START, FRASCO_SIZE[1]), L["bot_h"]),
        )
        y = 0
        for (a, b), h in parts:
            piece = src.subsurface((0, a, FRASCO_SIZE[0], b - a))
            frame.blit(pygame.transform.smoothscale(piece, (fw, h)), (0, y))
            y += h
        self.frasco = frame

        # ---- doctor: 8 cuadros iguales en horizontal
        sheet = load("doctor.png")
        n = 8
        fw = sheet.get_width() // n
        union = None
        for i in range(n):
            r = sheet.subsurface((i * fw, 0, fw, sheet.get_height())).get_bounding_rect()
            union = r if union is None else union.union(r)
        self.doctor = [fit(sheet.subsurface((i * fw + union.x, union.y, union.w, union.h)),
                           1000, doctor_h) for i in range(n)]

        # ---- lupa
        src = load("lupa.png")
        k = lupa_h / src.get_height()
        self.lupa = pygame.transform.smoothscale(
            src, (round(src.get_width() * k), lupa_h))
        cx, cy, r = LUPA_LENS
        self.lupa_lens = (round(cx * k), round(cy * k), round(r * k))

    def virus_big(self, col, size):
        return fit(self.virus_raw[col], size, size)
