"""Tablero: celdas, pastilla activa, colisiones, matches y caidas.

No depende de pygame: se puede probar por separado."""
import random

from config import COLS, ROWS, MATCH_LEN, SPAWN_COL, PILL_COLORS

# direccion hacia la otra mitad de la pastilla
OFFSETS = {"L": (0, -1), "R": (0, 1), "U": (-1, 0), "D": (1, 0)}


class Cell:
    __slots__ = ("color", "virus", "link")

    def __init__(self, color, virus=False, link=None):
        self.color = color
        self.virus = virus
        self.link = link  # None = virus o pedazo suelto


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


class Board:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.grid = [[None] * COLS for _ in range(ROWS)]

    # ---- consultas -------------------------------------------------------
    def __getitem__(self, rc):
        r, c = rc
        return self.grid[r][c]

    def virus_count(self, color=None):
        return sum(1 for row in self.grid for cell in row
                   if cell and cell.virus and (color is None or cell.color == color))

    def free(self, r, c):
        if c < 0 or c >= COLS or r >= ROWS:
            return False
        if r < 0:
            return True  # por encima del frasco: permitido mientras vuela
        return self.grid[r][c] is None

    def fits(self, pill, r, c, vertical):
        return all(self.free(rr, cc) for rr, cc, _, _ in pill.cells(r, c, vertical))

    # ---- virus -----------------------------------------------------------
    def place_viruses(self, count, top_row):
        spots = [(r, c) for r in range(top_row, ROWS) for c in range(COLS)]
        self.rng.shuffle(spots)
        placed = 0
        for r, c in spots:
            if placed >= count:
                break
            # alterna colores para un reparto parejo, sin dejar lineas armadas
            k = placed % 3
            for col in PILL_COLORS[k:] + PILL_COLORS[:k]:
                self.grid[r][c] = Cell(col, virus=True)
                if self.run_through(r, c) < MATCH_LEN - 1:
                    placed += 1
                    break
                self.grid[r][c] = None
        return placed

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

    # ---- pastilla activa -------------------------------------------------
    def move(self, pill, dc):
        if self.fits(pill, pill.r, pill.c + dc, pill.vertical):
            pill.c += dc
            return True
        return False

    def rotate(self, pill, clockwise):
        """Rota sobre el pivote. Si al acostarse choca a la derecha, prueba
        correrse una columna a la izquierda (al pararse nunca puede chocar
        de costado porque ocupa solo la columna del pivote)."""
        nv = not pill.vertical
        for kick in (0, -1):
            if self.fits(pill, pill.r, pill.c + kick, nv):
                if (pill.vertical and clockwise) or (not pill.vertical and not clockwise):
                    pill.c0, pill.c1 = pill.c1, pill.c0
                pill.vertical = nv
                pill.c += kick
                return True
        return False

    def drop(self, pill):
        """Baja una fila. False si no pudo (hay que fijarla)."""
        if self.fits(pill, pill.r + 1, pill.c, pill.vertical):
            pill.r += 1
            return True
        return False

    def lock(self, pill):
        """Fija la pastilla. False si quedo asomando por arriba (perdiste)."""
        cells = pill.cells()
        if any(r < 0 for r, _, _, _ in cells):
            return False
        for r, c, col, link in cells:
            self.grid[r][c] = Cell(col, link=link)
        return True

    # ---- resolucion ------------------------------------------------------
    def find_matches(self):
        found = set()
        for line in self._lines():
            run = []
            for pos in line + [None]:
                cell = self.grid[pos[0]][pos[1]] if pos else None
                if run and (cell is None or cell.color != self.grid[run[0][0]][run[0][1]].color):
                    if len(run) >= MATCH_LEN:
                        found.update(run)
                    run = []
                if cell is not None:
                    run.append(pos)
        return found

    @staticmethod
    def _lines():
        for r in range(ROWS):
            yield [(r, c) for c in range(COLS)]
        for c in range(COLS):
            yield [(r, c) for r in range(ROWS)]

    def clear(self, cells):
        """Borra las celdas; las mitades que pierden pareja quedan sueltas.
        Devuelve cuantos virus se eliminaron."""
        killed = 0
        for r, c in cells:
            cell = self.grid[r][c]
            if cell.virus:
                killed += 1
            elif cell.link:
                dr, dc = OFFSETS[cell.link]
                partner = self.grid[r + dr][c + dc]
                if partner and (r + dr, c + dc) not in cells:
                    partner.link = None
            self.grid[r][c] = None
        return killed

    def gravity_step(self, dry=False):
        """Baja una fila todo pedazo sin apoyo. True si algo cayo (o caeria)."""
        g = self.grid
        moved = False
        for r in range(ROWS - 2, -1, -1):
            for c in range(COLS):
                cell = g[r][c]
                if cell is None or cell.virus or cell.link in ("L", "D"):
                    continue  # "L" y "D" los mueve su otra mitad
                if cell.link == "R":                 # horizontal: ambas libres abajo
                    falls = g[r + 1][c] is None and g[r + 1][c + 1] is None
                else:                                # vertical (U) o suelta
                    falls = g[r + 1][c] is None
                if not falls:
                    continue
                if dry:
                    return True
                moved = True
                g[r + 1][c], g[r][c] = cell, None
                if cell.link == "R":
                    g[r + 1][c + 1], g[r][c + 1] = g[r][c + 1], None
                elif cell.link == "U":
                    g[r][c], g[r - 1][c] = g[r - 1][c], None
        return moved
