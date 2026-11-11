"""Prepara los sprites del juego a partir de las hojas originales.

Lee las hojas grandes de assets/src/, recorta cada sprite, lo achica a un
tamaño cercano al de uso y guarda archivos sueltos en assets/ junto con
assets/meta.json (medidas del frasco, lente de la lupa, etc.).

Se corre una sola vez (o cuando cambian las hojas):
    python tools/build_assets.py
El juego solo usa lo generado, así arranca rápido en equipos ARM.
"""
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "src")
OUT = os.path.join(ROOT, "assets")

# medidas tomadas a mano sobre las hojas originales
FRASCO_INNER = (126, 509, 636, 1097)       # hueco interior x, y, w, h
FRASCO_TOP_END, FRASCO_BOT_START = 600, 1500
LUPA_LENS = (700, 465, 330)                # centro x, y y radio de la lente
DOCTOR_FRAMES = 8

# tamaño de salida
VIRUS_SIZE = 96
HALF_SIZE = 64
DOCTOR_H = 300            # las anclas de la mano están medidas a esta altura
FRASCO_H = 600
LUPA_H = 256


def load(name):
    return pygame.image.load(os.path.join(SRC, name)).convert_alpha()


def save(surf, name):
    pygame.image.save(surf, os.path.join(OUT, name))
    print("  ", name, surf.get_size())


def blobs(surf, min_area=2000):
    mask = pygame.mask.from_surface(surf, 64)
    return [r for r in mask.get_bounding_rects() if r.w * r.h >= min_area]


def fit(surf, w, h):
    sw, sh = surf.get_size()
    k = min(w / sw, h / sh)
    return pygame.transform.smoothscale(surf, (max(1, round(sw * k)), max(1, round(sh * k))))


def expect(rects, n, what):
    if len(rects) != n:
        sys.exit(f"{what}: se esperaban {n} sprites y se encontraron {len(rects)}")


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    meta = {}

    # virus: amarillo, azul, rojo (de izquierda a derecha)
    sheet = load("virus.png")
    rects = sorted(blobs(sheet), key=lambda r: r.x)
    expect(rects, 3, "virus.png")
    for name, r in zip(("yellow", "blue", "red"), rects):
        save(fit(sheet.subsurface(r), VIRUS_SIZE, VIRUS_SIZE), f"virus_{name}.png")

    # capsulas: fila de abajo = mitades izquierdas (rojo, azul, amarillo)
    # y mitades derechas (rojo, azul, amarillo)
    sheet = load("capsulas.png")
    halves = sorted([r for r in blobs(sheet) if r.y > sheet.get_height() * 0.6],
                    key=lambda r: r.x)
    expect(halves, 6, "capsulas.png (fila de mitades)")
    for side, group in (("left", halves[:3]), ("right", halves[3:])):
        for name, r in zip(("red", "blue", "yellow"), group):
            img = pygame.transform.smoothscale(sheet.subsurface(r), (HALF_SIZE, HALF_SIZE))
            save(img, f"half_{side}_{name}.png")

    # doctor: 8 cuadros iguales, recortados con la misma caja
    sheet = load("doctor.png")
    fw = sheet.get_width() // DOCTOR_FRAMES
    union = None
    for i in range(DOCTOR_FRAMES):
        r = sheet.subsurface((i * fw, 0, fw, sheet.get_height())).get_bounding_rect()
        union = r if union is None else union.union(r)
    for i in range(DOCTOR_FRAMES):
        crop = sheet.subsurface((i * fw + union.x, union.y, union.w, union.h))
        save(fit(crop, 10000, DOCTOR_H), f"doctor_{i}.png")
    meta["doctor"] = {"frames": DOCTOR_FRAMES, "height": DOCTOR_H}

    # frasco: se achica entero y se guardan sus medidas a la nueva escala
    src = load("frasco.png")
    k = FRASCO_H / src.get_height()
    save(pygame.transform.smoothscale(src, (round(src.get_width() * k), FRASCO_H)), "frasco.png")
    meta["frasco"] = {
        "size": [round(src.get_width() * k), FRASCO_H],
        "inner": [round(v * k) for v in FRASCO_INNER],
        "top_end": round(FRASCO_TOP_END * k),
        "bot_start": round(FRASCO_BOT_START * k),
    }

    # lupa
    src = load("lupa.png")
    k = LUPA_H / src.get_height()
    save(pygame.transform.smoothscale(src, (round(src.get_width() * k), LUPA_H)), "lupa.png")
    meta["lupa"] = {"lens": [round(v * k) for v in LUPA_LENS]}

    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("   meta.json")


if __name__ == "__main__":
    main()
