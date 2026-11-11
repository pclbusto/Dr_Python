"""Sprites generados desde las hojas originales al tamaño exacto de la
pantalla, con un cache en disco por tamaño.

La primera vez en cada resolucion se decodifican las hojas grandes
(~45 MB en memoria) y se escalan con suavizado; en equipos ARM lentos eso
lleva unos segundos. El resultado se guarda en cache_dir() y los
arranques siguientes cargan solo los sprites chicos."""
import hashlib
import os

import pygame

from config import ASSETS, RED, YELLOW, BLUE, cache_dir

CACHE_VERSION = 1
SOURCES = ("virus.png", "capsulas.png", "frasco.png", "lupa.png", "doctor.png")
COLOR_NAMES = {RED: "red", YELLOW: "yellow", BLUE: "blue"}

# medidas tomadas sobre las hojas originales
FRASCO_SIZE = (887, 1774)
FRASCO_INNER = (126, 509, 636, 1097)   # hueco interior x, y, w, h
FRASCO_TOP_END, FRASCO_BOT_START = 600, 1500
LUPA_LENS = (700, 465, 330)            # centro y radio de la lente
LUPA_SRC_H = 1297
DOCTOR_FRAMES = 8
DOCTOR_REF_H = 300                     # altura a la que se midieron las manos


def fit(surf, w, h):
    """Escala manteniendo proporcion para entrar en w x h."""
    sw, sh = surf.get_size()
    k = min(w / sw, h / sh)
    return pygame.transform.smoothscale(surf, (max(1, round(sw * k)), max(1, round(sh * k))))


def frasco_layout(board_w, board_h, pad, squash_top, canvas_h):
    """Escala y franjas del frasco para que su hueco interior envuelva un
    tablero de board_w x board_h. El cuello se achata (squash_top) y el
    cuerpo recto se estira lo necesario."""
    fw, fh = FRASCO_SIZE
    ix, iy, iw, ih = FRASCO_INNER
    s = (board_w + 2 * pad) / iw
    top_h = round(FRASCO_TOP_END * s * squash_top)
    inner_top = iy * s * squash_top
    bot_h = round((fh - FRASCO_BOT_START) * s)
    inner_bot = (iy + ih - FRASCO_BOT_START) * s
    mid_h = round(board_h + 2 * pad - (top_h - inner_top) - inner_bot)
    h = top_h + mid_h + bot_h
    return dict(w=round(fw * s), h=h, y=(canvas_h - h) // 2,
                top_h=top_h, mid_h=mid_h, bot_h=bot_h,
                board_dx=round(ix * s) + pad, board_dy=round(inner_top) + pad)


def _blobs(surf, min_area=2000):
    mask = pygame.mask.from_surface(surf, 64)
    return [r for r in mask.get_bounding_rects() if r.w * r.h >= min_area]


def _expect(rects, n, what):
    if len(rects) != n:
        raise RuntimeError(f"{what}: se esperaban {n} sprites y se encontraron {len(rects)}")


def _sources_signature():
    h = hashlib.md5()
    for name in SOURCES:
        st = os.stat(os.path.join(ASSETS, name))
        h.update(f"{name}:{st.st_size}:{int(st.st_mtime)};".encode())
    return h.hexdigest()[:10]


def _build(cell, frasco, doctor_h, lupa_h, lupa_virus):
    """Genera todos los sprites desde las hojas originales."""
    def load(name):
        return pygame.image.load(os.path.join(ASSETS, name)).convert_alpha()

    out = {}

    # virus: amarillo, azul, rojo (de izquierda a derecha)
    sheet = load("virus.png")
    rects = sorted(_blobs(sheet), key=lambda r: r.x)
    _expect(rects, 3, "virus.png")
    for color, r in zip((YELLOW, BLUE, RED), rects):
        crop = sheet.subsurface(r)
        n = COLOR_NAMES[color]
        out[f"virus_{n}"] = fit(crop, cell + 5, cell + 5)   # las patitas pueden asomar
        out[f"lupavirus_{n}"] = fit(crop, lupa_virus, lupa_virus)
    del sheet

    # capsulas: fila de abajo = mitades izquierdas (rojo, azul, amarillo)
    # y mitades derechas (rojo, azul, amarillo)
    sheet = load("capsulas.png")
    halves = sorted([r for r in _blobs(sheet) if r.y > sheet.get_height() * 0.6],
                    key=lambda r: r.x)
    _expect(halves, 6, "capsulas.png (fila de mitades)")
    pad = max(2, cell // 8)
    hw, hh = (cell - 2 * pad) // 2, cell - 2 * pad
    for i, color in enumerate((RED, BLUE, YELLOW)):
        n = COLOR_NAMES[color]
        left, right = sheet.subsurface(halves[i]), sheet.subsurface(halves[i + 3])
        out[f"half_left_{n}"] = pygame.transform.smoothscale(left, (cell, cell))
        out[f"half_right_{n}"] = pygame.transform.smoothscale(right, (cell, cell))
        one = pygame.Surface((cell, cell), pygame.SRCALPHA)   # pedazo suelto
        one.blit(pygame.transform.smoothscale(left, (hw, hh)), (pad, pad))
        one.blit(pygame.transform.smoothscale(right, (hw, hh)), (pad + hw, pad))
        out[f"single_{n}"] = one
    del sheet

    # frasco en 3 franjas: cuello, cuerpo (se estira) y base
    src = load("frasco.png")
    fw, fh = src.get_size()
    frame = pygame.Surface((frasco["w"], frasco["h"]), pygame.SRCALPHA)
    y = 0
    for (a, b), h in (((0, FRASCO_TOP_END), frasco["top_h"]),
                      ((FRASCO_TOP_END, FRASCO_BOT_START), frasco["mid_h"]),
                      ((FRASCO_BOT_START, fh), frasco["bot_h"])):
        piece = src.subsurface((0, a, fw, b - a))
        frame.blit(pygame.transform.smoothscale(piece, (frasco["w"], h)), (0, y))
        y += h
    out["frasco"] = frame
    del src

    # doctor: 8 cuadros iguales, recortados con la misma caja
    sheet = load("doctor.png")
    fw = sheet.get_width() // DOCTOR_FRAMES
    union = None
    for i in range(DOCTOR_FRAMES):
        r = sheet.subsurface((i * fw, 0, fw, sheet.get_height())).get_bounding_rect()
        union = r if union is None else union.union(r)
    for i in range(DOCTOR_FRAMES):
        crop = sheet.subsurface((i * fw + union.x, union.y, union.w, union.h))
        out[f"doctor_{i}"] = fit(crop, 100000, doctor_h)
    del sheet

    # lupa
    src = load("lupa.png")
    k = lupa_h / src.get_height()
    out["lupa"] = pygame.transform.smoothscale(src, (round(src.get_width() * k), lupa_h))
    return out


class Sprites:
    def __init__(self, cell, frasco, doctor_h, lupa_h, lupa_virus, on_build=None):
        """on_build: funcion que se llama antes de generar (para avisar en
        pantalla que el primer arranque puede tardar)."""
        self.cell = cell
        self.built = False
        key = (f"v{CACHE_VERSION}-c{cell}-f{frasco['w']}x{frasco['h']}-{frasco['top_h']}"
               f"-{frasco['mid_h']}-d{doctor_h}-l{lupa_h}-{lupa_virus}-{_sources_signature()}")
        base = cache_dir()
        folder = os.path.join(base, key) if base else None
        imgs = self._load_cache(folder)
        if imgs is None:
            if on_build:
                on_build()
            imgs = _build(cell, frasco, doctor_h, lupa_h, lupa_virus)
            self._save_cache(folder, imgs)
            self.built = True

        # virus: 3 cuadros de balanceo cada uno
        self.virus, self.lupa_virus, self.half, self.single = {}, {}, {}, {}
        for c, n in COLOR_NAMES.items():
            base_img = imgs[f"virus_{n}"]
            self.virus[c] = [pygame.transform.rotozoom(base_img, a, 1.0) for a in (-10, 0, 10)]
            self.lupa_virus[c] = imgs[f"lupavirus_{n}"]
            L, R = imgs[f"half_left_{n}"], imgs[f"half_right_{n}"]
            self.half[(c, "R")] = L                                  # pareja a la derecha
            self.half[(c, "L")] = R                                  # pareja a la izquierda
            self.half[(c, "D")] = pygame.transform.rotate(L, -90)    # mitad de arriba
            self.half[(c, "U")] = pygame.transform.rotate(R, -90)    # mitad de abajo
            self.single[c] = imgs[f"single_{n}"]
        self.frasco = imgs["frasco"]
        self.doctor = [imgs[f"doctor_{i}"] for i in range(DOCTOR_FRAMES)]
        self.doctor_scale = doctor_h / DOCTOR_REF_H
        self.lupa = imgs["lupa"]
        k = lupa_h / LUPA_SRC_H
        self.lupa_lens = tuple(round(v * k) for v in LUPA_LENS)

    @staticmethod
    def _load_cache(folder):
        if not folder or not os.path.exists(os.path.join(folder, "ok")):
            return None
        try:
            imgs = {}
            for name in os.listdir(folder):
                if name.endswith(".png"):
                    imgs[name[:-4]] = pygame.image.load(os.path.join(folder, name)).convert_alpha()
            return imgs
        except (OSError, pygame.error):
            return None

    @staticmethod
    def _save_cache(folder, imgs):
        if not folder:
            return
        try:
            os.makedirs(folder, exist_ok=True)
            for name, surf in imgs.items():
                pygame.image.save(surf, os.path.join(folder, name + ".png"))
            open(os.path.join(folder, "ok"), "w").close()   # marca de cache completo
        except (OSError, pygame.error):
            pass  # sin cache: la proxima vez se vuelve a generar
