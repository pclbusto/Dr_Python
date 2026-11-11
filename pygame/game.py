"""Estados del juego y sus transiciones. Recibe comandos abstractos
(controls.Command), nunca teclas ni botones, y no dibuja nada."""
import random
from enum import Enum, auto

from board import Board, Pill
from config import (CLEAR_TIME, FALL_STEP, MAX_LEVEL, PILL_COLORS, SOFT_DROP,
                    THROW_TIME, gravity_for, load_json, save_json, virus_count_for)
from controls import Command as C, ESSENTIAL

CAPTURE_TIMEOUT = 6000


class State(Enum):
    TITLE = auto()
    THROW = auto()       # la pastilla vuela de la mano al frasco
    PLAY = auto()
    CLEARING = auto()    # explosion de lo eliminado
    FALLING = auto()     # caen los pedazos sueltos
    PAUSED = auto()
    CLEARED = auto()     # nivel limpio
    GAMEOVER = auto()
    CONTROLS = auto()    # pantalla de reasignacion
    CAPTURE = auto()     # esperando la entrada para un comando


ACTIVE = (State.THROW, State.PLAY, State.CLEARING, State.FALLING)

TITLE_MENU = ("JUGAR", "CONTROLES", "SALIR")
PAUSE_MENU = ("SEGUIR", "CONTROLES", "ABANDONAR")
CONTROL_CMDS = (C.LEFT, C.RIGHT, C.DOWN, C.UP, C.ROTATE_CW, C.ROTATE_CCW,
                C.PAUSE, C.ACCEPT, C.BACK)
CONTROL_MENU = CONTROL_CMDS + ("RESTAURAR", "VOLVER")


class Game:
    def __init__(self, controls, rng=None):
        self.ctl = controls
        self.rng = rng or random.Random()
        self.state = State.TITLE
        self.level = 0
        self.score = 0
        self.top = int(load_json("record.json", {}).get("top", 0))
        self.board = Board(self.rng)
        self.viruses = 0
        self.pill = None
        self.next = self.random_pill()
        self.throw_colors = None
        self.throw_seq = 0          # cambia en cada lanzamiento (para el dibujo)
        self.throw_elapsed = 0
        self.matches = set()
        self.timer = 0
        self.chain = 0
        self.fall_timer = 0
        self.soft_timer = 0
        self.menu = 0               # opcion elegida del menu visible
        self.resume_state = None    # a donde vuelve la pausa
        self.controls_return = State.TITLE
        self.capture_cmd = None
        self.capture_left = 0
        self.message = ""
        self.quit = False

    # ---- utilidades --------------------------------------------------------
    def random_pill(self):
        return (self.rng.choice(PILL_COLORS), self.rng.choice(PILL_COLORS))

    @property
    def throw_progress(self):
        return min(1.0, self.throw_elapsed / THROW_TIME)

    @property
    def menu_items(self):
        return {State.TITLE: TITLE_MENU, State.PAUSED: PAUSE_MENU,
                State.CONTROLS: CONTROL_MENU, State.CAPTURE: CONTROL_MENU}.get(self.state, ())

    def save_record(self):
        if self.score > self.top:
            self.top = self.score
        try:
            save_json("record.json", {"top": self.top})
        except OSError:
            pass  # sin carpeta escribible: el record vive solo en esta sesion

    # ---- flujo de partida --------------------------------------------------
    def start_level(self):
        self.board = Board(self.rng)
        top_row = max(5, 8 - self.level // 3)    # niveles altos: virus mas arriba
        self.viruses = self.board.place_viruses(virus_count_for(self.level), top_row)
        self.gravity = gravity_for(self.level)
        self.pill = None
        self.next = self.random_pill()
        self.start_throw()

    def start_throw(self):
        self.pill = None
        self.throw_colors = self.next or self.random_pill()
        self.next = None             # la mano queda vacia mientras vuela
        self.throw_elapsed = 0
        self.throw_seq += 1
        self.state = State.THROW

    def spawn(self):
        self.pill = Pill(*self.throw_colors)
        self.next = self.random_pill()
        self.fall_timer = self.soft_timer = 0
        if self.board.fits(self.pill, self.pill.r, self.pill.c, False):
            self.state = State.PLAY
        else:
            self.game_over()

    def game_over(self):
        self.state = State.GAMEOVER
        self.save_record()

    def step_down(self, soft=False):
        if self.board.drop(self.pill):
            if soft:
                self.score += 1
            return True
        if not self.board.lock(self.pill):
            self.pill = None
            self.game_over()
            return False
        self.pill = None
        self.chain = 0
        self.resolve()
        return False

    def resolve(self):
        matches = self.board.find_matches()
        if matches:
            self.matches = matches
            self.timer = CLEAR_TIME
            self.state = State.CLEARING
        elif self.board.gravity_step(dry=True):
            self.timer = FALL_STEP
            self.state = State.FALLING
        elif self.viruses == 0:
            self.state = State.CLEARED
            self.save_record()
        else:
            self.start_throw()

    def clear_matches(self):
        killed = self.board.clear(self.matches)
        if killed:
            self.chain += 1
            self.score += sum(100 * 2 ** i for i in range(killed)) * self.chain
        self.viruses -= killed
        self.matches = set()

    def pause(self):
        self.resume_state = self.state
        self.state = State.PAUSED
        self.menu = 0

    def on_focus_lost(self):
        if self.state in ACTIVE:
            self.pause()

    # ---- cuadro --------------------------------------------------------------
    def update(self, dt):
        handler = {
            State.TITLE: self._title,
            State.THROW: self._throw,
            State.PLAY: self._play,
            State.CLEARING: self._clearing,
            State.FALLING: self._falling,
            State.PAUSED: self._paused,
            State.CLEARED: self._cleared,
            State.GAMEOVER: self._gameover,
            State.CONTROLS: self._controls,
            State.CAPTURE: self._capture,
        }[self.state]
        if self.state in ACTIVE and (self.ctl.pressed(C.PAUSE) or self.ctl.pressed(C.BACK)):
            self.pause()
            return
        handler(dt)

    def _nav(self, n):
        ctl = self.ctl
        if ctl.pressed(C.UP):
            self.menu = (self.menu - 1) % n
        if ctl.pressed(C.DOWN):
            self.menu = (self.menu + 1) % n

    def _title(self, dt):
        ctl = self.ctl
        self._nav(len(TITLE_MENU))
        item = TITLE_MENU[self.menu]
        if item == "JUGAR":
            delta = ctl.steps(C.RIGHT) - ctl.steps(C.LEFT)
            self.level = max(0, min(MAX_LEVEL, self.level + delta))
        if ctl.pressed(C.ACCEPT):
            if item == "JUGAR":
                self.score = 0
                self.start_level()
            elif item == "CONTROLES":
                self.open_controls()
            else:
                self.quit = True
        elif ctl.pressed(C.BACK):
            self.quit = True

    def _throw(self, dt):
        self.throw_elapsed += dt
        if self.throw_elapsed >= THROW_TIME:
            self.spawn()

    def _play(self, dt):
        ctl, b, p = self.ctl, self.board, self.pill
        for _ in range(ctl.pressed(C.ROTATE_CW)):
            b.rotate(p, True)
        for _ in range(ctl.pressed(C.ROTATE_CCW)):
            b.rotate(p, False)

        left, right = ctl.steps(C.LEFT), ctl.steps(C.RIGHT)
        if ctl.held(C.LEFT) and ctl.held(C.RIGHT):
            # las dos sostenidas: gana la ultima apretada
            if ctl.latest(C.LEFT, C.RIGHT) == C.LEFT:
                right = 0
            else:
                left = 0
        for _ in range(left):
            b.move(p, -1)
        for _ in range(right):
            b.move(p, 1)

        if ctl.held(C.DOWN):
            # bajar rapido usa su propio reloj: no hereda lo acumulado por la gravedad
            self.fall_timer = 0
            self.soft_timer = SOFT_DROP if ctl.pressed(C.DOWN) else self.soft_timer + dt
            while self.soft_timer >= SOFT_DROP and self.pill:
                self.soft_timer -= SOFT_DROP
                self.step_down(soft=True)
        else:
            self.soft_timer = 0
            self.fall_timer += dt
            while self.fall_timer >= self.gravity and self.pill:
                self.fall_timer -= self.gravity
                self.step_down()

    def _clearing(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.clear_matches()
            self.timer += FALL_STEP
            self.state = State.FALLING

    def _falling(self, dt):
        self.timer -= dt
        while self.timer <= 0 and self.state == State.FALLING:
            if self.board.gravity_step():
                self.timer += FALL_STEP
            else:
                self.resolve()

    def _paused(self, dt):
        ctl = self.ctl
        self._nav(len(PAUSE_MENU))
        if ctl.pressed(C.PAUSE) or ctl.pressed(C.BACK):
            self.state = self.resume_state
        elif ctl.pressed(C.ACCEPT):
            item = PAUSE_MENU[self.menu]
            if item == "SEGUIR":
                self.state = self.resume_state
            elif item == "CONTROLES":
                self.open_controls()
            else:
                self.save_record()
                self.to_title()

    def _cleared(self, dt):
        if self.ctl.pressed(C.ACCEPT):
            self.level = min(MAX_LEVEL, self.level + 1)
            self.start_level()
        elif self.ctl.pressed(C.BACK):
            self.to_title()

    def _gameover(self, dt):
        if self.ctl.pressed(C.ACCEPT) or self.ctl.pressed(C.BACK):
            self.to_title()

    def to_title(self):
        self.state = State.TITLE
        self.menu = 0
        self.pill = None
        self.next = self.random_pill()

    # ---- pantalla de controles -----------------------------------------------
    def open_controls(self):
        self.controls_return = self.state
        self.state = State.CONTROLS
        self.menu = 0
        self.message = ""

    def close_controls(self):
        self.ctl.save()
        self.state = self.controls_return
        self.menu = 1  # vuelve parado en "CONTROLES"

    def _controls(self, dt):
        ctl = self.ctl
        self._nav(len(CONTROL_MENU))
        item = CONTROL_MENU[self.menu]
        if ctl.pressed(C.BACK):
            self.close_controls()
        elif ctl.pressed(C.ACCEPT):
            if item == "RESTAURAR":
                ctl.reset_defaults()
                self.message = "Controles restaurados"
            elif item == "VOLVER":
                self.close_controls()
            else:
                self.capture_cmd = item
                self.capture_left = CAPTURE_TIMEOUT
                self.state = State.CAPTURE
                self.message = ""
                ctl.start_capture()
        elif ctl.pressed(C.ROTATE_CCW) and item in CONTROL_CMDS:
            # no se usa IZQUIERDA: la ruedita tambien lo es y borraria al scrollear
            if ctl.remove_last(item):
                self.message = "Quitada la ultima entrada"
            elif item in ESSENTIAL:
                self.message = "Este comando necesita al menos una entrada"

    def _capture(self, dt):
        ctl = self.ctl
        self.capture_left -= dt
        got = ctl.captured
        if got is None and self.capture_left > 0:
            return
        ctl.stop_capture()
        self.state = State.CONTROLS
        if got is None:
            self.message = "Sin cambios (tiempo agotado)"
        elif got == {"type": "key", "key": "escape"}:
            self.message = "Cancelado"
        else:
            ctl.add_binding(self.capture_cmd, got)
            self.message = "Entrada agregada"
