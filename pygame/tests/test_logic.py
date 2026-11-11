"""Pruebas de logica sin ventana:  python tests/test_logic.py"""
import os
import random
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["DRPYTHON_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ["DRPYTHON_CACHE_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from board import Board, Cell, Pill  # noqa: E402
from config import RED, YELLOW, BLUE, ROWS, COLS, MATCH_LEN, SOFT_DROP  # noqa: E402
from controls import Controls, Command as C  # noqa: E402
from game import Game, State  # noqa: E402

pygame.init()
pygame.display.set_mode((640, 480))
EV = pygame.event.Event


def key(k, down=True):
    return EV(pygame.KEYDOWN if down else pygame.KEYUP, key=k, mod=0, unicode="", scancode=0)


def frame(ctl, game=None, dt=16, events=()):
    for e in events:
        ctl.handle(e)
    ctl.update(dt)
    if game:
        game.update(dt)
    ctl.end_frame()


def test_match_is_four():
    assert MATCH_LEN == 4
    b = Board()
    for r in (13, 14, 15):
        b.grid[r][0] = Cell(RED, virus=True)
    assert not b.find_matches(), "tres en linea no deben eliminar"
    b.grid[12][0] = Cell(RED)
    assert b.find_matches() == {(12, 0), (13, 0), (14, 0), (15, 0)}


def test_orphan_half_falls_and_pairs_fall_together():
    b = Board()
    b.grid[15][3] = Cell(BLUE, virus=True)
    # horizontal rojo-amarillo arriba de una columna roja de 3 virus
    for r in (13, 14, 15):
        b.grid[r][0] = Cell(RED, virus=True)
    b.grid[12][0], b.grid[12][1] = Cell(RED, link="R"), Cell(YELLOW, link="L")
    assert b.clear(b.find_matches()) == 3
    assert b.grid[12][1].link is None            # quedo suelta
    while b.gravity_step():
        pass
    assert b.grid[15][1] and b.grid[15][1].color == YELLOW

    b = Board()
    b.grid[5][2], b.grid[5][3] = Cell(RED, link="R"), Cell(BLUE, link="L")
    b.grid[15][2] = Cell(YELLOW, virus=True)      # apoyo solo bajo una mitad
    while b.gravity_step():
        pass
    assert b.grid[14][2].link == "R" and b.grid[14][3].link == "L"


def test_viruses_never_start_three_in_line():
    for seed in range(30):
        b = Board(random.Random(seed))
        n = b.place_viruses(84, 5)
        assert n > 70
        for r in range(ROWS):
            for c in range(COLS):
                if b.grid[r][c]:
                    assert b.run_through(r, c) < MATCH_LEN - 1


def test_debris_falls_twice_as_fast_as_pill():
    from config import gravity_for
    for level in (0, 10):
        g = Game(Controls())
        g.level = level
        g.start_level()
        g.board = Board()
        g.viruses = 1
        g.board.grid[15][0] = Cell(BLUE, virus=True)
        g.board.grid[2][3] = Cell(RED)            # pedazo suelto: cae 13 filas
        g.resolve()
        t = 0
        while g.state == State.FALLING:
            g.update(10)
            t += 10
        per_row = t / 13
        assert abs(per_row - gravity_for(level) / 2) < 15, (level, per_row)


def test_rotation_kicks_off_right_wall():
    b = Board()
    p = Pill(RED, BLUE)
    p.r, p.c, p.vertical = 10, COLS - 1, True
    assert b.rotate(p, True) and not p.vertical and p.c == COLS - 2


def test_controls_multi_source_and_repeat():
    ctl = Controls()
    hat = EV(pygame.JOYHATMOTION, instance_id=0, hat=0, value=(-1, 0), joy=0)
    frame(ctl, events=[key(pygame.K_LEFT)])
    ctl.handle(hat)                               # otro dispositivo sostiene izquierda
    ctl.handle(key(pygame.K_LEFT, False))         # se suelta el teclado
    assert ctl.held(C.LEFT), "la cruceta sigue sosteniendo izquierda"
    total = 0
    for _ in range(20):                           # 320 ms sostenido
        ctl.update(16)
        total += ctl.steps(C.LEFT)
        ctl.end_frame()
    assert total >= 3, total                      # autorrepeticion
    ctl.handle(EV(pygame.JOYHATMOTION, instance_id=0, hat=0, value=(0, 0), joy=0))
    assert not ctl.held(C.LEFT)


def test_wheel_pulses_and_axis_hysteresis():
    ctl = Controls()
    ctl.handle(EV(pygame.MOUSEWHEEL, x=0, y=1, flipped=False, precise_x=0.0, precise_y=1.0))
    ctl.update(16)
    assert ctl.steps(C.LEFT) == 1 and not ctl.held(C.LEFT)
    ctl.end_frame()

    ax = lambda v: EV(pygame.JOYAXISMOTION, instance_id=0, axis=0, value=v, joy=0)  # noqa: E731
    ctl.handle(ax(0.5))
    assert not ctl.held(C.RIGHT)
    ctl.handle(ax(0.6))
    assert ctl.held(C.RIGHT)
    ctl.handle(ax(0.4))                           # entre umbrales: sigue apretado
    assert ctl.held(C.RIGHT)
    ctl.handle(ax(0.2))
    assert not ctl.held(C.RIGHT)


def play_game(seed=1):
    ctl = Controls()
    g = Game(ctl, random.Random(seed))
    g.level = 3
    g.start_level()
    while g.state != State.PLAY:
        frame(ctl, g)
    return ctl, g


def test_soft_drop_does_not_teleport():
    ctl, g = play_game()
    r0 = g.pill.r
    g.fall_timer = g.gravity - 1                  # gravedad casi vencida
    frame(ctl, g, events=[key(pygame.K_DOWN)])
    assert g.pill.r - r0 <= 2, g.pill.r - r0


def test_left_right_last_pressed_wins():
    ctl, g = play_game()
    c0 = g.pill.c
    frame(ctl, g, events=[key(pygame.K_LEFT)])
    frame(ctl, g, events=[key(pygame.K_RIGHT)])   # ahora las dos sostenidas
    assert g.pill.c == c0                         # -1 y +1
    frame(ctl, g, events=[key(pygame.K_RIGHT, False)])
    for _ in range(15):
        frame(ctl, g)
    assert g.pill.c < c0, "al soltar derecha, izquierda retoma la repeticion"


def test_pause_in_any_active_state():
    ctl, g = play_game()
    g.start_throw()
    frame(ctl, g, events=[key(pygame.K_p)])
    assert g.state == State.PAUSED and g.resume_state == State.THROW
    frame(ctl, g, events=[key(pygame.K_p, False), key(pygame.K_p)])
    assert g.state == State.THROW


def test_rebind_capture():
    ctl = Controls()
    g = Game(ctl)
    g.open_controls()
    g.menu = 0                                    # Izquierda
    frame(ctl, g, events=[key(pygame.K_RETURN)])
    assert g.state == State.CAPTURE
    frame(ctl, g, events=[EV(pygame.JOYBUTTONDOWN, instance_id=0, button=5, joy=0)])
    assert g.state == State.CONTROLS
    assert any(b.get("button") == 5 for b in ctl.bindings(C.LEFT))
    g.close_controls()
    assert Controls().bindings(C.LEFT)[-1].get("button") == 5, "se guardo en disco"


def test_key_released_during_capture_is_not_stuck():
    ctl = Controls()
    g = Game(ctl)
    g.open_controls()
    frame(ctl, g, events=[key(pygame.K_RETURN)])           # abre la captura
    frame(ctl, g, events=[key(pygame.K_RETURN, False)])    # se suelta durante la captura
    frame(ctl, g, events=[key(pygame.K_ESCAPE)])           # cancela
    assert g.state == State.CONTROLS
    assert not ctl.held(C.ACCEPT), "Aceptar no debe quedar pegado"


def test_random_games_with_renderer():
    from renderer import Renderer
    surf = pygame.Surface((640, 480))
    r = Renderer()
    keys = [pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_z, pygame.K_DOWN]
    for seed in range(3):
        rng = random.Random(seed)
        ctl = Controls()
        g = Game(ctl, random.Random(seed))
        g.level = 5
        g.start_level()
        held = set()
        for i in range(6000):
            ev = []
            if rng.random() < 0.1:
                k = rng.choice(keys)
                ev.append(key(k, k not in held))
                held ^= {k}
            frame(ctl, g, 30, ev)
            r.update(30, g)
            if i % 50 == 0:
                r.draw(surf, g)
            if g.state in (State.GAMEOVER, State.CLEARED):
                break
        assert g.state in (State.GAMEOVER, State.CLEARED, State.PLAY, State.THROW,
                           State.FALLING, State.CLEARING), g.state


def test_renderer_scales_and_cache():
    from renderer import Renderer
    for scale in (1.25, 1.5, 2.25):   # la 1.0 ya la genero otra prueba
        r = Renderer(scale)
        assert r.spr.built, "primera vez: se generan los sprites"
        surf = pygame.Surface((r.W, r.H))
        assert (r.W, r.H) == (round(640 * scale), round(480 * scale))
        assert r.L.cell == round(20 * scale)
        assert r.spr.doctor[0].get_height() == round(210 * scale)
        g = Game(Controls(), random.Random(1))
        g.start_level()
        for _ in range(60):
            g.update(16)
            r.update(16, g)
        r.draw(surf, g)
        assert not Renderer(scale).spr.built, "segunda vez: sale del cache"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} pruebas pasaron")
