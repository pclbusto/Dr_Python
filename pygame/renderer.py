"""Todo lo que se dibuja, directo a la resolucion real.

Las medidas estan pensadas en "unidades de 640x480" y se multiplican por la
escala de la pantalla con p(): en 640x480 la escala es 1, en 1280x720 es
1.5, en 1920x1080 es 2.25. Los sprites se generan a ese tamaño (ver
sprites.py), asi que en pantallas grandes se ve nitido, sin agrandar."""
import math
import random

import pygame

from config import COLS, ROWS, SPAWN_COL, RED, YELLOW, BLUE, CLEAR_TIME
from controls import Command as C, LABELS, describe
from game import State, CONTROL_CMDS
from sprites import Sprites, frasco_layout

BASE_W, BASE_H = 640, 480

COLORS = {RED: (225, 55, 70), YELLOW: (245, 205, 45), BLUE: (55, 120, 235)}
GLASS = (40, 46, 72)
TEXT = (230, 235, 245)
DIM = (150, 160, 185)
HILITE = (255, 214, 80)
PANEL = (14, 16, 28, 215)

# palma de la mano del doctor en cada cuadro, medida a 300 px de alto
HAND_ANCHORS = [(48, 125), (32, 165), (50, 188), (22, 148),
                (30, 122), (50, 178), (42, 182), (25, 135)]
FRAME_MS = 140


class Layout:
    """Posiciones de todo, ya en pixeles reales para la escala dada."""

    def __init__(self, scale):
        self.scale = scale
        self.w, self.h = round(BASE_W * scale), round(BASE_H * scale)
        self.cell = max(8, round(20 * scale))
        self.board_w, self.board_h = COLS * self.cell, ROWS * self.cell
        self.frasco = frasco_layout(self.board_w, self.board_h, pad=self.p(4),
                                    squash_top=0.72, canvas_h=self.h)
        self.frame_x = (self.w - self.frasco["w"]) // 2
        self.frame_y = self.frasco["y"]
        self.board_x = self.frame_x + self.frasco["board_dx"]
        self.board_y = self.frame_y + self.frasco["board_dy"]
        self.right_x = self.frame_x + self.frasco["w"]
        self.doctor_h = self.p(210)
        self.lupa_h = self.p(190)
        self.lupa_virus = self.p(34)

    def p(self, v):
        """Unidades de 640x480 -> pixeles reales."""
        return round(v * self.scale)

    def cell_rect(self, r, c):
        return pygame.Rect(self.board_x + c * self.cell, self.board_y + r * self.cell,
                           self.cell, self.cell)


def make_floor(W, H, tile):
    """Piso de hospital: damero gris claro / gris oscuro con juntas."""
    rnd = random.Random(4)
    surf = pygame.Surface((W, H))
    light, dark = (160, 162, 157), (78, 81, 88)
    surf.fill((52, 54, 60))  # juntas
    for ty in range(0, H, tile):
        for tx in range(0, W, tile):
            base = light if (tx // tile + ty // tile) % 2 == 0 else dark
            j = rnd.randint(-5, 5)
            col = tuple(max(0, min(255, v + j)) for v in base)
            r = pygame.Rect(tx + 1, ty + 1, tile - 2, tile - 2)
            pygame.draw.rect(surf, col, r)
            hi = tuple(min(255, v + 14) for v in col)
            lo = tuple(max(0, v - 14) for v in col)
            pygame.draw.line(surf, hi, r.topleft, r.topright)
            pygame.draw.line(surf, hi, r.topleft, r.bottomleft)
            pygame.draw.line(surf, lo, r.bottomleft, r.bottomright)
            pygame.draw.line(surf, lo, r.topright, r.bottomright)
    return surf.convert()


class Renderer:
    def __init__(self, scale=1.0, on_build=None):
        self.L = L = Layout(scale)
        self.p = p = L.p
        self.W, self.H = L.w, L.h
        self.font = pygame.font.Font(None, p(28))
        self.small = pygame.font.Font(None, p(22))
        self.tiny = pygame.font.Font(None, p(19))
        self.title_font = pygame.font.Font(None, p(44))
        self.spr = Sprites(L.cell, L.frasco, L.doctor_h, L.lupa_h, L.lupa_virus, on_build)
        self.lupa_virus = self.spr.lupa_virus
        self.floor = make_floor(self.W, self.H, p(40))
        self._boxes = {}

        dw, dh = self.spr.doctor[0].get_size()
        self.doctor_rect = pygame.Rect(0, 0, dw, dh)
        self.doctor_rect.midbottom = ((L.right_x + self.W) // 2 + p(8), self.H - p(8))
        k = self.spr.doctor_scale
        self.hand_points = [(self.doctor_rect.x + x * k, self.doctor_rect.y + y * k)
                            for x, y in HAND_ANCHORS]
        self.hand_pos = self.hand_points[0]
        self.ticks = 0
        self.seen_throw = 0
        self.throw_from = self.hand_pos

    # ---- animacion (solo visual) ---------------------------------------------
    def doctor_frame(self):
        n = len(self.spr.doctor)
        k = int(self.ticks / FRAME_MS) % (2 * n - 2)       # ida y vuelta
        return k if k < n else 2 * n - 2 - k

    def update(self, dt, game):
        self.ticks += dt
        # la pastilla en la mano sigue suavemente a la palma del cuadro actual
        tx, ty = self.hand_points[self.doctor_frame()]
        hx, hy = self.hand_pos
        a = min(1.0, dt / 60)
        self.hand_pos = (hx + (tx - hx) * a, hy + (ty - hy) * a)
        if game.throw_seq != self.seen_throw:   # empezo un lanzamiento
            self.seen_throw = game.throw_seq
            self.throw_from = self.hand_pos

    # ---- piezas ----------------------------------------------------------------
    def draw_half(self, surf, rect, color, link):
        img = self.spr.half[(color, link)] if link else self.spr.single[color]
        surf.blit(img, rect)

    def draw_virus(self, surf, rect, color, phase):
        t = self.ticks / 220 + phase
        img = self.spr.virus[color][(0, 1, 2, 1)[int(t) % 4]]
        bob = round(math.sin(t * 1.3))
        surf.blit(img, img.get_rect(center=(rect.centerx, rect.centery + bob)))

    def pill_image(self, colors, angle=0.0):
        cell = self.L.cell
        s = pygame.Surface((cell * 2, cell), pygame.SRCALPHA)
        s.blit(self.spr.half[(colors[0], "R")], (0, 0))
        s.blit(self.spr.half[(colors[1], "L")], (cell, 0))
        return pygame.transform.rotozoom(s, angle, 1.0) if angle else s

    def blit_pill(self, surf, colors, center, angle=0.0):
        img = self.pill_image(colors, angle)
        surf.blit(img, img.get_rect(center=center))

    # ---- texto y paneles ---------------------------------------------------------
    def text(self, surf, txt, font, color, pos, center=False, right=False):
        img = font.render(txt, True, color)
        r = img.get_rect()
        if center:
            r.center = pos
        elif right:
            r.topright = pos
        else:
            r.topleft = pos
        surf.blit(img, r)
        return r

    def box(self, surf, rect, color=PANEL):
        """Panel semitransparente. Se arma una vez por tamaño y color: a
        1080p crearlo en cada cuadro saldria caro."""
        key = (rect.size, color)
        shade = self._boxes.get(key)
        if shade is None:
            shade = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(shade, color, shade.get_rect(), border_radius=self.p(10))
            self._boxes[key] = shade
        surf.blit(shade, rect)

    def fit_text(self, txt, font, width):
        if font.size(txt)[0] <= width:
            return txt
        while txt and font.size(txt + "...")[0] > width:
            txt = txt[:-1]
        return txt + "..."

    # ---- escena ------------------------------------------------------------------
    @staticmethod
    def in_title(game):
        """Pantalla de titulo, o controles abiertos desde el titulo."""
        return game.state == State.TITLE or (
            game.state in (State.CONTROLS, State.CAPTURE) and game.controls_return == State.TITLE)

    def draw(self, surf, game):
        L, p = self.L, self.p
        surf.blit(self.floor, (0, 0))
        pygame.draw.rect(surf, GLASS, (L.board_x - p(4), L.board_y - p(4),
                                       L.board_w + p(8), L.board_h + p(8)), border_radius=p(12))
        self.draw_sides(surf, game)

        st = game.state
        in_title = self.in_title(game)
        if not in_title:
            self.draw_board(surf, game)
        surf.blit(self.spr.frasco, (L.frame_x, L.frame_y))
        if st == State.THROW:
            self.draw_throw(surf, game)

        if in_title:
            self.draw_title(surf, game)
        elif st == State.PAUSED:
            self.draw_menu_box(surf, game, "PAUSA")
        elif st == State.CLEARED:
            self.draw_banner(surf, "NIVEL LIMPIO!", "ACEPTAR: seguir")
        elif st == State.GAMEOVER:
            self.draw_banner(surf, "GAME OVER", "ACEPTAR: volver")
        if st in (State.CONTROLS, State.CAPTURE):
            self.draw_controls(surf, game)

    def draw_board(self, surf, game):
        L = self.L
        clearing = game.state == State.CLEARING
        for r in range(ROWS):
            for c in range(COLS):
                cell = game.board.grid[r][c]
                if not cell:
                    continue
                rect = L.cell_rect(r, c)
                if clearing and (r, c) in game.matches:
                    k = 1 - max(0, game.timer) / CLEAR_TIME
                    rad = int(L.cell // 2 * (0.6 + k))
                    pygame.draw.circle(surf, (255, 255, 255), rect.center, rad, max(1, self.p(3)))
                    pygame.draw.circle(surf, COLORS[cell.color], rect.center,
                                       max(1, int(rad * (1 - k))))
                elif cell.virus:
                    self.draw_virus(surf, rect, cell.color, (r * 7 + c * 3) % 6)
                else:
                    self.draw_half(surf, rect, cell.color, cell.link)
        p = game.pill
        if p:
            for r, c, col, link in p.cells():
                if r >= 0:
                    self.draw_half(surf, L.cell_rect(r, c), col, link)

    def draw_throw(self, surf, game):
        """Parabola girando desde la mano hasta la boca del frasco."""
        L, p = self.L, self.p
        t = game.throw_progress
        x0, y0 = self.throw_from
        y0 -= L.cell // 2 + p(2)
        x1 = L.board_x + (SPAWN_COL + 1) * L.cell
        y1 = L.board_y + L.cell / 2
        peak = min(y0, y1) - p(70)
        ctrl = 2 * peak - (y0 + y1) / 2          # bezier que pasa por el pico
        x = x0 + (x1 - x0) * t
        y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * ctrl + t ** 2 * y1
        self.blit_pill(surf, game.throw_colors, (x, y), 720 * t)   # dos vueltas

    def draw_sides(self, surf, game):
        L, p = self.L, self.p
        playing = not self.in_title(game)

        # izquierda: puntajes y lupa
        self.box(surf, pygame.Rect(p(10), p(18), L.frame_x - p(20), p(132)))
        self.text(surf, "TOP", self.small, DIM, (p(24), p(28)))
        self.text(surf, f"{game.top:07d}", self.font, TEXT, (p(24), p(48)))
        self.text(surf, "PUNTOS", self.small, DIM, (p(24), p(88)))
        self.text(surf, f"{game.score:07d}", self.font, TEXT, (p(24), p(108)))

        lupa = self.spr.lupa
        ux, uy = (L.frame_x - lupa.get_width()) // 2, self.H - lupa.get_height() - p(20)
        lcx, lcy, lr = self.spr.lupa_lens
        pygame.draw.circle(surf, GLASS, (ux + lcx, uy + lcy), lr)
        for i, col in enumerate((RED, YELLOW, BLUE)):
            if playing and not game.board.virus_count(col):
                continue  # color erradicado: desaparece de la lupa
            a = self.ticks / 900 + i * 2 * math.pi / 3
            img = self.lupa_virus[col]
            hop = abs(math.sin(self.ticks / 160 + i)) * p(4)
            pos = (ux + lcx + math.cos(a) * lr * 0.45, uy + lcy + math.sin(a) * lr * 0.45 - hop)
            surf.blit(img, img.get_rect(center=pos))
        surf.blit(lupa, (ux, uy))

        # derecha: nivel, virus y el doctor con la siguiente pastilla
        rx = L.right_x + p(26)
        self.box(surf, pygame.Rect(rx - p(10), p(18), self.W - rx - p(8), p(132)))
        self.text(surf, "NIVEL", self.small, DIM, (rx + p(4), p(28)))
        self.text(surf, f"{game.level:02d}", self.font, TEXT, (rx + p(4), p(48)))
        self.text(surf, "VIRUS", self.small, DIM, (rx + p(4), p(88)))
        self.text(surf, f"{game.viruses if playing else 0:02d}", self.font, TEXT, (rx + p(4), p(108)))

        surf.blit(self.spr.doctor[self.doctor_frame()], self.doctor_rect)
        if game.next:
            t = self.ticks / 260
            hop = abs(math.sin(t)) * p(16)
            hx, hy = self.hand_pos
            self.blit_pill(surf, game.next, (hx, hy - L.cell // 2 - p(2) - hop), math.sin(t * 0.5) * 12)

    # ---- menus -------------------------------------------------------------------
    def menu_cursor(self, surf, rect):
        img = self.spr.single[RED]
        surf.blit(img, img.get_rect(midright=(rect.left - self.p(6), rect.centery)))

    def draw_title(self, surf, game):
        L, p = self.L, self.p
        cx = L.board_x + L.board_w // 2
        self.text(surf, "DR.", self.title_font, TEXT, (cx, p(150)), center=True)
        self.text(surf, "PYTHON", self.title_font, TEXT, (cx, p(185)), center=True)
        lvl = self.text(surf, f"Nivel  < {game.level:02d} >", self.font, TEXT, (cx, p(240)), center=True)
        if game.state == State.TITLE:
            for i, item in enumerate(game.menu_items):
                sel = i == game.menu
                r = self.text(surf, item, self.font, HILITE if sel else TEXT,
                              (cx, p(295 + i * 34)), center=True)
                if sel:
                    self.menu_cursor(surf, r)
            if game.menu == 0:
                self.text(surf, "izq / der", self.tiny, DIM, (cx, lvl.bottom + p(10)), center=True)

    def draw_menu_box(self, surf, game, title):
        L, p = self.L, self.p
        cx = L.board_x + L.board_w // 2
        mid = L.board_y + L.board_h // 2
        rect = pygame.Rect(L.board_x, mid - p(75), L.board_w, p(150))
        self.box(surf, rect, (0, 0, 0, 205))
        self.text(surf, title, self.font, TEXT, (cx, rect.y + p(22)), center=True)
        for i, item in enumerate(game.menu_items):
            sel = i == game.menu
            r = self.text(surf, item, self.small, HILITE if sel else TEXT,
                          (cx + p(8), rect.y + p(62 + i * 28)), center=True)
            if sel:
                self.menu_cursor(surf, r)

    def draw_banner(self, surf, title, hint):
        L, p = self.L, self.p
        cx = L.board_x + L.board_w // 2
        mid = L.board_y + L.board_h // 2
        self.box(surf, pygame.Rect(L.board_x, mid - p(45), L.board_w, p(90)), (0, 0, 0, 205))
        self.text(surf, title, self.font, TEXT, (cx, mid - p(12)), center=True)
        self.text(surf, hint, self.small, DIM, (cx, mid + p(18)), center=True)

    def draw_controls(self, surf, game):
        ctl, p, W = game.ctl, self.p, self.W
        panel = pygame.Rect(p(16), p(12), W - p(32), self.H - p(24))
        self.box(surf, panel, (10, 12, 22, 238))
        self.text(surf, "CONTROLES", self.font, TEXT, (W // 2, p(34)), center=True)
        self.text(surf, "Cada comando acepta teclado, mando y mouse a la vez",
                  self.tiny, DIM, (W // 2, p(56)), center=True)

        y0, row_h = p(74), p(28)
        label_x, bind_x = p(54), p(220)
        for i, item in enumerate(game.menu_items):
            y = y0 + i * row_h + (p(8) if i >= len(CONTROL_CMDS) else 0)
            sel = i == game.menu
            if sel:
                self.box(surf, pygame.Rect(panel.x + p(8), y - p(3), panel.w - p(16), row_h - p(2)),
                         (60, 70, 110, 200))
            color = HILITE if sel else TEXT
            if item in CONTROL_CMDS:
                self.text(surf, LABELS[item], self.small, color, (label_x, y + p(2)))
                if game.state == State.CAPTURE and sel:
                    secs = max(0, game.capture_left) // 1000 + 1
                    txt = f"Presiona una tecla, boton o rueda...  ({secs})"
                    self.text(surf, txt, self.small, HILITE, (bind_x, y + p(2)))
                else:
                    names = ", ".join(describe(b) for b in ctl.bindings(item)) or "(sin asignar)"
                    names = self.fit_text(names, self.small, panel.right - bind_x - p(16))
                    self.text(surf, names, self.small, DIM if not sel else TEXT, (bind_x, y + p(2)))
            else:
                label = "Restaurar valores de fabrica" if item == "RESTAURAR" else "Volver"
                self.text(surf, label, self.small, color, (label_x, y + p(2)))

        def first(cmd):
            b = ctl.bindings(cmd)
            return describe(b[0]) if b else "?"

        if game.state == State.CAPTURE:
            hint = "ESCAPE cancela"
        else:
            hint = (f"{first(C.ACCEPT)}: agregar entrada    "
                    f"{first(C.ROTATE_CCW)}: quitar la ultima    {first(C.BACK)}: volver")
        self.text(surf, hint, self.tiny, DIM, (W // 2, panel.bottom - p(34)), center=True)
        if game.message:
            self.text(surf, game.message, self.small, HILITE, (W // 2, panel.bottom - p(14)), center=True)
