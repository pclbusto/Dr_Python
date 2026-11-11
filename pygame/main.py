"""Dr. Python - puzzle de pastillas y virus con Pygame.

Controles:
  Izquierda / Derecha : mover
  Abajo               : bajar rapido
  Z / Arriba          : rotar antihorario / horario (X tambien rota horario)
  P                   : pausa
  Enter               : comenzar / continuar
  Esc                 : salir
"""
import math
import random
import sys

import pygame

from sprites import Sprites, frasco_layout

# ---------------------------------------------------------------- config ---
SCREEN_W, SCREEN_H = 640, 480
FPS = 60

COLS, ROWS = 8, 16
CELL = 20
BOARD_W, BOARD_H = COLS * CELL, ROWS * CELL
# el frasco se ajusta para que su hueco interior envuelva al tablero
LAYOUT = frasco_layout(BOARD_W, BOARD_H, pad=4, squash_top=0.72, screen_h=SCREEN_H)
FRAME_X = (SCREEN_W - LAYOUT["w"]) // 2
FRAME_Y = LAYOUT["y"]
BOARD_X = FRAME_X + LAYOUT["board_dx"]
BOARD_Y = FRAME_Y + LAYOUT["board_dy"]

MATCH_LEN = 3            # cuantos del mismo color en linea eliminan
SPAWN_COL = 3

CLEAR_TIME = 250         # ms que se muestra la explosion
FALL_STEP = 90           # ms por fila al caer pedazos sueltos
SOFT_DROP = 35           # ms por fila al apretar abajo
DAS_DELAY = 160          # ms antes de autorepetir izquierda/derecha
DAS_REPEAT = 45

RED, YELLOW, BLUE = 0, 1, 2
COLORS = {
    RED: (225, 55, 70),
    YELLOW: (245, 205, 45),
    BLUE: (55, 120, 235),
}
COLOR_NAMES = {RED: "Rojo", YELLOW: "Amarillo", BLUE: "Azul"}

BG = (18, 20, 34)
BOTTLE_GLASS = (40, 46, 72)
BOTTLE_EDGE = (170, 190, 230)
TEXT = (230, 235, 245)
DIM = (130, 140, 165)

# direccion hacia la otra mitad de la pastilla
OFFSETS = {"L": (0, -1), "R": (0, 1), "U": (-1, 0), "D": (1, 0)}
OPPOSITE = {"L": "R", "R": "L", "U": "D", "D": "U"}


class Cell:
    __slots__ = ("color", "virus", "link")

    def __init__(self, color, virus=False, link=None):
        self.color = color
        self.virus = virus
        self.link = link  # None = pedazo suelto / virus


# ------------------------------------------------------------- pastilla ---
class Pill:
    """Pastilla activa. Pivote (r, c) = celda inferior izquierda.
    Horizontal: c0 izquierda, c1 derecha.  Vertical: c0 arriba, c1 abajo."""

    def __init__(self, c0, c1):
        self.r, self.c = 0, SPAWN_COL
        self.vertical = False
        self.c0, self.c1 = c0, c1

    def cells(self, r=None, c=None, vertical=None):
        r = self.r if r is None else r
        c = self.c if c is None else c
        vertical = self.vertical if vertical is None else vertical
        if vertical:
            return [(r - 1, c, self.c0, "D"), (r, c, self.c1, "U")]
        return [(r, c, self.c0, "R"), (r, c + 1, self.c1, "L")]


# ---------------------------------------------------------------- juego ---
class Game:
    def __init__(self):
        self.font = pygame.font.Font(None, 28)
        self.big = pygame.font.Font(None, 56)
        self.small = pygame.font.Font(None, 22)
        self.title_font = pygame.font.Font(None, 44)
        self.spr = Sprites(CELL, (RED, YELLOW, BLUE), LAYOUT)
        self.lupa_virus = {c: self.spr.virus_big(c, 34) for c in COLORS}
        self.state = "title"
        self.level = 0
        self.score = 0
        self.top = 10000
        self.ticks = 0

    # ---- setup ---------------------------------------------------------
    def start_level(self):
        self.grid = [[None] * COLS for _ in range(ROWS)]
        self.place_viruses(min(4 * (self.level + 1), 96))
        self.pill = None
        self.next = self.random_pill()
        self.gravity = max(90, 650 - self.level * 35)
        self.fall_timer = 0
        self.das_timer = 0
        self.das_dir = 0
        self.chain = 0
        self.state = "play"
        self.spawn()

    def random_pill(self):
        return (random.choice(list(COLORS)), random.choice(list(COLORS)))

    def place_viruses(self, count):
        top_row = max(5, 8 - self.level // 3)  # niveles altos: virus mas arriba
        spots = [(r, c) for r in range(top_row, ROWS) for c in range(COLS)]
        random.shuffle(spots)
        placed = 0
        colors = list(COLORS)
        for r, c in spots:
            if placed >= count:
                break
            # alterna colores para un reparto parejo, evitando lineas formadas
            order = colors[placed % 3:] + colors[:placed % 3]
            for col in order:
                self.grid[r][c] = Cell(col, virus=True)
                if self.run_through(r, c) < MATCH_LEN:
                    placed += 1
                    break
                self.grid[r][c] = None
        self.viruses = placed

    def run_through(self, r, c):
        """Largo maximo de linea del mismo color que pasa por (r, c)."""
        col = self.grid[r][c].color
        best = 1
        for dr, dc in ((0, 1), (1, 0)):
            n = 1
            for s in (1, -1):
                rr, cc = r + dr * s, c + dc * s
                while 0 <= rr < ROWS and 0 <= cc < COLS and self.grid[rr][cc] \
                        and self.grid[rr][cc].color == col:
                    n += 1
                    rr += dr * s
                    cc += dc * s
            best = max(best, n)
        return best

    # ---- pastilla activa -----------------------------------------------
    def free(self, r, c):
        if c < 0 or c >= COLS or r >= ROWS:
            return False
        if r < 0:
            return True  # por encima del frasco: permitido mientras vuela
        return self.grid[r][c] is None

    def fits(self, r, c, vertical):
        return all(self.free(rr, cc) for rr, cc, _, _ in
                   self.pill.cells(r, c, vertical))

    def spawn(self):
        c0, c1 = self.next
        self.pill = Pill(c0, c1)
        self.next = self.random_pill()
        self.fall_timer = 0
        if not self.fits(self.pill.r, self.pill.c, False):
            self.state = "gameover"
            self.top = max(self.top, self.score)

    def move(self, dc):
        p = self.pill
        if self.fits(p.r, p.c + dc, p.vertical):
            p.c += dc
            return True
        return False

    def rotate(self, clockwise):
        p = self.pill
        nv = not p.vertical
        for kick in (0, -1):  # si choca a la derecha, empuja a la izquierda
            if self.fits(p.r, p.c + kick, nv):
                # reordena colores segun sentido
                if (p.vertical and clockwise) or (not p.vertical and not clockwise):
                    p.c0, p.c1 = p.c1, p.c0
                p.vertical = nv
                p.c += kick
                return

    def step_down(self):
        p = self.pill
        if self.fits(p.r + 1, p.c, p.vertical):
            p.r += 1
            return True
        self.lock()
        return False

    def lock(self):
        for r, c, col, link in self.pill.cells():
            if r < 0:
                self.state = "gameover"
                self.top = max(self.top, self.score)
                return
            self.grid[r][c] = Cell(col, link=link)
        self.pill = None
        self.chain = 0
        self.resolve()

    # ---- resolucion: coincidencias y caidas -----------------------------
    def find_matches(self):
        found = set()
        for r in range(ROWS):
            c = 0
            while c < COLS:
                cell = self.grid[r][c]
                if cell is None:
                    c += 1
                    continue
                e = c
                while e + 1 < COLS and self.grid[r][e + 1] and \
                        self.grid[r][e + 1].color == cell.color:
                    e += 1
                if e - c + 1 >= MATCH_LEN:
                    found.update((r, x) for x in range(c, e + 1))
                c = e + 1
        for c in range(COLS):
            r = 0
            while r < ROWS:
                cell = self.grid[r][c]
                if cell is None:
                    r += 1
                    continue
                e = r
                while e + 1 < ROWS and self.grid[e + 1][c] and \
                        self.grid[e + 1][c].color == cell.color:
                    e += 1
                if e - r + 1 >= MATCH_LEN:
                    found.update((y, c) for y in range(r, e + 1))
                r = e + 1
        return found

    def resolve(self):
        matches = self.find_matches()
        if matches:
            self.matches = matches
            self.timer = CLEAR_TIME
            self.state = "clearing"
        elif self.gravity_step(dry=True):
            self.timer = FALL_STEP
            self.state = "falling"
        elif self.viruses == 0:
            self.state = "cleared"
        else:
            self.state = "play"
            self.spawn()

    def clear_matches(self):
        killed = 0
        for r, c in self.matches:
            cell = self.grid[r][c]
            if cell.virus:
                killed += 1
            elif cell.link:
                dr, dc = OFFSETS[cell.link]
                partner = self.grid[r + dr][c + dc]
                if partner:
                    partner.link = None  # la otra mitad queda suelta
            self.grid[r][c] = None
        if killed:
            self.chain += 1
            self.score += sum(100 * (2 ** i) for i in range(killed)) * self.chain
        self.viruses -= killed
        self.matches = set()

    def gravity_step(self, dry=False):
        """Baja una fila todo pedazo sin apoyo. Devuelve True si algo cayo."""
        g = self.grid
        moved = False
        for r in range(ROWS - 2, -1, -1):
            for c in range(COLS):
                cell = g[r][c]
                if cell is None or cell.virus:
                    continue
                if cell.link == "R":           # mitad izquierda horizontal
                    if g[r + 1][c] is None and g[r + 1][c + 1] is None:
                        moved = True
                        if not dry:
                            g[r + 1][c], g[r][c] = cell, None
                            g[r + 1][c + 1], g[r][c + 1] = g[r][c + 1], None
                elif cell.link == "L":         # la maneja su mitad izquierda
                    continue
                elif cell.link == "D":         # mitad superior: la maneja la inferior
                    continue
                elif cell.link == "U":         # mitad inferior vertical
                    if g[r + 1][c] is None:
                        moved = True
                        if not dry:
                            g[r + 1][c], g[r][c] = cell, g[r - 1][c]
                            g[r - 1][c] = None
                else:                          # pedazo suelto
                    if g[r + 1][c] is None:
                        moved = True
                        if not dry:
                            g[r + 1][c], g[r][c] = cell, None
                if moved and dry:
                    return True
        return moved

    # ---- loop ----------------------------------------------------------
    def handle_event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if self.state == "title":
            if k == pygame.K_UP:
                self.level = min(20, self.level + 1)
            elif k == pygame.K_DOWN:
                self.level = max(0, self.level - 1)
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self.score = 0
                self.start_level()
        elif self.state == "cleared" and k in (pygame.K_RETURN, pygame.K_SPACE):
            self.level += 1
            self.start_level()
        elif self.state == "gameover" and k in (pygame.K_RETURN, pygame.K_SPACE):
            self.state = "title"
        elif self.state == "paused" and k in (pygame.K_p, pygame.K_RETURN):
            self.state = "play"
        elif self.state == "play" and self.pill:
            if k == pygame.K_LEFT:
                self.move(-1)
                self.das_dir, self.das_timer = -1, DAS_DELAY
            elif k == pygame.K_RIGHT:
                self.move(1)
                self.das_dir, self.das_timer = 1, DAS_DELAY
            elif k in (pygame.K_UP, pygame.K_x):
                self.rotate(True)
            elif k == pygame.K_z:
                self.rotate(False)
            elif k == pygame.K_p:
                self.state = "paused"

    def update(self, dt):
        self.ticks += dt
        if self.state == "play" and self.pill:
            keys = pygame.key.get_pressed()
            # autorepeticion lateral
            held = (-1 if keys[pygame.K_LEFT] else 0) + (1 if keys[pygame.K_RIGHT] else 0)
            if held and held == self.das_dir:
                self.das_timer -= dt
                while self.das_timer <= 0:
                    self.move(held)
                    self.das_timer += DAS_REPEAT
            else:
                self.das_dir = 0
            # caida
            interval = SOFT_DROP if keys[pygame.K_DOWN] else self.gravity
            self.fall_timer += dt
            while self.fall_timer >= interval and self.pill:
                self.fall_timer -= interval
                if keys[pygame.K_DOWN]:
                    self.score += 1
                self.step_down()
        elif self.state == "clearing":
            self.timer -= dt
            if self.timer <= 0:
                self.clear_matches()
                self.timer = FALL_STEP
                self.state = "falling"
        elif self.state == "falling":
            self.timer -= dt
            if self.timer <= 0:
                if self.gravity_step():
                    self.timer = FALL_STEP
                else:
                    self.resolve()

    # ---- dibujo --------------------------------------------------------
    def cell_rect(self, r, c):
        return pygame.Rect(BOARD_X + c * CELL, BOARD_Y + r * CELL, CELL, CELL)

    def draw_half(self, surf, rect, color_id, link):
        img = self.spr.half[(color_id, link)] if link else self.spr.single[color_id]
        surf.blit(img, rect)

    def draw_virus(self, surf, rect, color_id, phase):
        frames = self.spr.virus[color_id]
        t = self.ticks / 220 + phase
        i = (0, 1, 2, 1)[int(t) % 4]
        img = frames[i]
        bob = round(math.sin(t * 1.3) * 1)
        surf.blit(img, img.get_rect(center=(rect.centerx, rect.centery + bob)))

    def draw_glass(self, surf):
        inner = pygame.Rect(BOARD_X - 4, BOARD_Y - 4, BOARD_W + 8, BOARD_H + 8)
        pygame.draw.rect(surf, BOTTLE_GLASS, inner, border_radius=12)

    def draw_text(self, surf, txt, font, color, pos, center=False):
        img = font.render(txt, True, color)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        surf.blit(img, r)

    def draw_panel(self, surf):
        # izquierda: doctor animado + lupa con los tres virus
        frames = self.spr.doctor
        n = len(frames)
        k = int(self.ticks / 140) % (2 * n - 2)       # ida y vuelta
        doc = frames[k if k < n else 2 * n - 2 - k]
        surf.blit(doc, doc.get_rect(midbottom=(FRAME_X // 2, 210)))

        lupa = self.spr.lupa
        lx, ly = (FRAME_X - lupa.get_width()) // 2, SCREEN_H - lupa.get_height() - 20
        lcx, lcy, lr = self.spr.lupa_lens
        pygame.draw.circle(surf, BOTTLE_GLASS, (lx + lcx, ly + lcy), lr)
        for i, col in enumerate((RED, YELLOW, BLUE)):
            a = self.ticks / 900 + i * 2 * math.pi / 3
            img = self.lupa_virus[col]
            hop = abs(math.sin(self.ticks / 160 + i)) * 4
            p = (lx + lcx + math.cos(a) * lr * 0.45,
                 ly + lcy + math.sin(a) * lr * 0.45 - hop)
            if self.state != "title" and not self.count_color(col):
                continue  # color erradicado: desaparece de la lupa
            surf.blit(img, img.get_rect(center=p))
        surf.blit(lupa, (lx, ly))

        # derecha: puntajes, siguiente, nivel, virus
        rx = FRAME_X + LAYOUT["w"] + 30
        self.draw_text(surf, "TOP", self.small, DIM, (rx, 30))
        self.draw_text(surf, f"{self.top:07d}", self.font, TEXT, (rx, 50))
        self.draw_text(surf, "PUNTOS", self.small, DIM, (rx, 90))
        self.draw_text(surf, f"{self.score:07d}", self.font, TEXT, (rx, 110))

        self.draw_text(surf, "SIGUIENTE", self.small, DIM, (rx, 160))
        box = pygame.Rect(rx, 182, CELL * 4, CELL * 2)
        pygame.draw.rect(surf, BOTTLE_GLASS, box, border_radius=8)
        if self.state != "title":
            c0, c1 = self.next
            y = box.y + CELL // 2
            self.draw_half(surf, pygame.Rect(box.x + CELL, y, CELL, CELL), c0, "R")
            self.draw_half(surf, pygame.Rect(box.x + 2 * CELL, y, CELL, CELL), c1, "L")

        self.draw_text(surf, "NIVEL", self.small, DIM, (rx, 250))
        self.draw_text(surf, f"{self.level:02d}", self.font, TEXT, (rx, 270))
        self.draw_text(surf, "VIRUS", self.small, DIM, (rx, 310))
        v = self.viruses if self.state != "title" else 0
        self.draw_text(surf, f"{v:02d}", self.font, TEXT, (rx, 330))

    def count_color(self, col):
        return sum(1 for row in self.grid for c in row if c and c.virus and c.color == col)

    def draw(self, surf):
        surf.fill(BG)
        self.draw_glass(surf)
        self.draw_panel(surf)
        cx = BOARD_X + BOARD_W // 2

        if self.state == "title":
            surf.blit(self.spr.frasco, (FRAME_X, FRAME_Y))
            self.draw_text(surf, "DR.", self.title_font, TEXT, (cx, 160), center=True)
            self.draw_text(surf, "PYTHON", self.title_font, TEXT, (cx, 195), center=True)
            self.draw_text(surf, f"Nivel: {self.level:02d}", self.font, TEXT, (cx, 255), center=True)
            self.draw_text(surf, "Arriba/Abajo", self.small, DIM, (cx, 282), center=True)
            self.draw_text(surf, "ENTER: jugar", self.font, TEXT, (cx, 340), center=True)
            return

        flash = self.state == "clearing"
        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]
                if not cell:
                    continue
                rect = self.cell_rect(r, c)
                if flash and (r, c) in self.matches:
                    k = 1 - self.timer / CLEAR_TIME
                    rad = int(CELL // 2 * (0.6 + k))
                    pygame.draw.circle(surf, (255, 255, 255), rect.center, rad, 3)
                    pygame.draw.circle(surf, COLORS[cell.color], rect.center,
                                       max(1, int(rad * (1 - k))))
                    continue
                if cell.virus:
                    self.draw_virus(surf, rect, cell.color, (r * 7 + c * 3) % 6)
                else:
                    self.draw_half(surf, rect, cell.color, cell.link)

        if self.pill and self.state in ("play", "paused"):
            for r, c, col, link in self.pill.cells():
                if r >= 0:
                    self.draw_half(surf, self.cell_rect(r, c), col, link)

        # el frasco va encima para tapar bordes de las piezas
        surf.blit(self.spr.frasco, (FRAME_X, FRAME_Y))

        msg = {"paused": ("PAUSA", "P para seguir"),
               "cleared": ("NIVEL LIMPIO!", "ENTER: seguir"),
               "gameover": ("GAME OVER", "ENTER: volver")}.get(self.state)
        if msg:
            shade = pygame.Surface((BOARD_W, 90), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 200))
            mid = BOARD_Y + BOARD_H // 2
            surf.blit(shade, (BOARD_X, mid - 45))
            self.draw_text(surf, msg[0], self.font, TEXT, (cx, mid - 12), center=True)
            self.draw_text(surf, msg[1], self.small, DIM, (cx, mid + 18), center=True)

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Dr. Python")
    clock = pygame.time.Clock()
    game = Game()
    while True:
        dt = clock.tick(FPS)
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            game.handle_event(e)
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()


if __name__ == "__main__":
    main()
