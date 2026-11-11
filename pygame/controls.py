"""Entrada unificada: cada comando tiene UNA lista de entradas que mezcla
teclado, mando (botones, cruceta y palancas) y mouse (botones y ruedita).

- Varios mandos a la vez y conexion/desconexion en caliente: cada mando se
  identifica por su instance_id mientras esta conectado; las asignaciones
  pueden ser para cualquier mando ("guid": "*") o para un modelo (su GUID).
- Si dos dispositivos sostienen el mismo comando y se suelta uno, el
  comando sigue activo por el otro.
- La autorrepeticion (DAS) vive aca, una sola vez, para cualquier origen.
- La ruedita del mouse da pulsos sueltos: cada muesca es un paso.
"""
import copy
from collections import Counter, defaultdict
from enum import Enum

import pygame

from config import load_json, save_json


class Command(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    DOWN = "down"
    UP = "up"
    ROTATE_CW = "rotate_cw"
    ROTATE_CCW = "rotate_ccw"
    PAUSE = "pause"
    ACCEPT = "accept"
    BACK = "back"


LABELS = {
    Command.LEFT: "Izquierda",
    Command.RIGHT: "Derecha",
    Command.DOWN: "Abajo / bajar",
    Command.UP: "Arriba (menus)",
    Command.ROTATE_CW: "Rotar horario",
    Command.ROTATE_CCW: "Rotar antihorario",
    Command.PAUSE: "Pausa",
    Command.ACCEPT: "Aceptar",
    Command.BACK: "Volver / salir",
}

# sin al menos una entrada en estos no se podria navegar los menus
ESSENTIAL = (Command.UP, Command.DOWN, Command.ACCEPT, Command.BACK)

ANY = "*"


def _k(name):
    return {"type": "key", "key": name}


def _jb(button):
    return {"type": "joy_button", "guid": ANY, "button": button}


def _hat(axis, direction):
    return {"type": "joy_hat", "guid": ANY, "hat": 0, "axis": axis, "direction": direction}


def _ax(axis, direction):
    return {"type": "joy_axis", "guid": ANY, "axis": axis, "direction": direction}


def _wheel(axis, direction):
    return {"type": "mouse_wheel", "axis": axis, "direction": direction}


def _mb(button):
    return {"type": "mouse_button", "button": button}


# Numeracion de botones "cruda" de SDL: en mandos tipo Xbox 0=A 1=B 6=Back 7=Start.
# Otros mandos (y los integrados de cada Anbernic) varian: para eso esta
# la pantalla de CONTROLES.
DEFAULT_CONFIG = {
    "version": 1,
    "axis_press": 0.55,       # la palanca "aprieta" al pasar este valor...
    "axis_release": 0.35,     # ...y "suelta" recien al bajar de este (sin titileo)
    "repeat": {
        "left": [160, 45],    # [demora inicial, intervalo] en ms
        "right": [160, 45],
    },
    "commands": {
        "left": [_k("left"), _k("a"), _wheel("y", 1), _wheel("x", -1), _hat("x", -1), _ax(0, -1)],
        "right": [_k("right"), _k("d"), _wheel("y", -1), _wheel("x", 1), _hat("x", 1), _ax(0, 1)],
        "down": [_k("down"), _k("s"), _mb(2), _hat("y", -1), _ax(1, 1)],
        "up": [_k("up"), _k("w"), _hat("y", 1), _ax(1, -1)],
        "rotate_cw": [_k("up"), _k("x"), _k("k"), _mb(1), _jb(0)],
        "rotate_ccw": [_k("z"), _k("j"), _mb(3), _jb(1)],
        "pause": [_k("p"), _jb(7)],
        "accept": [_k("return"), _k("space"), _mb(1), _jb(0), _jb(7)],
        "back": [_k("escape"), _k("backspace"), _jb(6)],
    },
}

CONFIG_FILE = "controls.json"
MAX_BINDINGS = 8
CAPTURE_AXIS = 0.7


def describe(b):
    """Texto corto para mostrar una entrada en pantalla."""
    t = b["type"]
    side = {-1: "-", 1: "+"}
    if t == "key":
        return b["key"].upper()
    if t == "mouse_button":
        return {1: "Mouse izq", 2: "Mouse medio", 3: "Mouse der"}.get(b["button"], f"Mouse {b['button']}")
    if t == "mouse_wheel":
        if b["axis"] == "y":
            return "Rueda arriba" if b["direction"] > 0 else "Rueda abajo"
        return "Rueda izq" if b["direction"] < 0 else "Rueda der"
    tag = "" if b.get("guid", ANY) == ANY else "*"   # * = solo ese modelo de mando
    if t == "joy_button":
        return f"Boton {b['button']}{tag}"
    if t == "joy_hat":
        name = {("x", -1): "izq", ("x", 1): "der", ("y", 1): "arriba", ("y", -1): "abajo"}
        return f"Cruceta {name[(b['axis'], b['direction'])]}{tag}"
    if t == "joy_axis":
        return f"Palanca {b['axis']}{side[b['direction']]}{tag}"
    return "?"


def _same(a, b):
    """Misma entrada fisica descrita (el GUID cuenta si ambos lo fijan)."""
    keys = (set(a) | set(b)) - {"guid"}
    if any(a.get(k) != b.get(k) for k in keys):
        return False
    return a.get("guid", ANY) == b.get("guid", ANY)


def _matches(binding, desc):
    keys = (set(binding) | set(desc)) - {"guid"}
    if any(binding.get(k) != desc.get(k) for k in keys):
        return False
    g = binding.get("guid", ANY)
    return g == ANY or g == desc.get("guid")


class Repeater:
    """Pasos extra mientras se mantiene un comando (la presion inicial no
    cuenta: esa ya llega como pulso)."""

    def __init__(self, delay, interval):
        self.delay, self.interval = delay, interval
        self.elapsed = 0
        self.started = False

    def update(self, held, dt):
        if not held:
            self.elapsed, self.started = 0, False
            return 0
        self.elapsed += dt
        count = 0
        limit = self.interval if self.started else self.delay
        while self.elapsed >= limit:
            self.elapsed -= limit
            self.started = True
            limit = self.interval
            count += 1
        return count


class Controls:
    def __init__(self):
        data = load_json(CONFIG_FILE, None)
        self.config = self._merge(data)
        self.joys = {}                        # instance_id -> Joystick
        self.sources = defaultdict(set)       # comando -> fuentes que lo sostienen
        self._pulses = Counter()              # presiones de este cuadro
        self._steps = Counter()               # presiones + autorrepeticion
        self._order = {}                      # comando -> numero de la ultima presion
        self._seq = 0
        self._hats = {}                       # (iid, hat) -> (x, y)
        self._axes = {}                       # (iid, eje) -> -1 / 0 / 1
        self._repeaters = {Command(k): Repeater(*v) for k, v in self.config["repeat"].items()}
        self.capturing = False
        self.captured = None                  # entrada atrapada en modo captura

    # ---- configuracion ---------------------------------------------------
    @staticmethod
    def _merge(data):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        if isinstance(data, dict) and data.get("version") == 1:
            for k in ("axis_press", "axis_release"):
                if isinstance(data.get(k), (int, float)):
                    cfg[k] = data[k]
            for k, v in data.get("repeat", {}).items():
                if k in cfg["repeat"] and isinstance(v, list) and len(v) == 2:
                    cfg["repeat"][k] = v
            for k, v in data.get("commands", {}).items():
                if k in cfg["commands"] and isinstance(v, list):
                    cfg["commands"][k] = [b for b in v if isinstance(b, dict) and "type" in b]
        for cmd in ESSENTIAL:  # nunca dejar los menus sin manejo
            if not cfg["commands"][cmd.value]:
                cfg["commands"][cmd.value] = copy.deepcopy(DEFAULT_CONFIG["commands"][cmd.value])
        return cfg

    def save(self):
        try:
            save_json(CONFIG_FILE, self.config)
        except OSError:
            pass  # sin carpeta escribible: los cambios valen solo esta sesion

    def bindings(self, cmd):
        return self.config["commands"][Command(cmd).value]

    def add_binding(self, cmd, desc):
        lst = self.bindings(cmd)
        if any(_same(b, desc) for b in lst):
            return
        lst.append(desc)
        del lst[:-MAX_BINDINGS]

    def remove_last(self, cmd):
        lst = self.bindings(cmd)
        if lst and not (cmd in ESSENTIAL and len(lst) == 1):
            lst.pop()
            return True
        return False

    def reset_defaults(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)

    # ---- consultas para el juego -------------------------------------------
    def pressed(self, cmd):
        """Cuantas veces se apreto en este cuadro (incluye pulsos de ruedita)."""
        return self._pulses[Command(cmd)]

    def held(self, cmd):
        return bool(self.sources[Command(cmd)])

    def steps(self, cmd):
        """Presiones + pasos de autorrepeticion en este cuadro."""
        return self._steps[Command(cmd)]

    def latest(self, a, b):
        """De dos comandos, el apretado mas recientemente."""
        return a if self._order.get(Command(a), -1) >= self._order.get(Command(b), -1) else b

    # ---- ciclo -------------------------------------------------------------
    def update(self, dt):
        """Llamar una vez por cuadro, despues de procesar los eventos."""
        self._steps = Counter(self._pulses)
        for cmd, rep in self._repeaters.items():
            self._steps[cmd] += rep.update(self.held(cmd), dt)

    def end_frame(self):
        self._pulses.clear()
        self._steps.clear()

    def release_all(self):
        """Al perder el foco: soltar todo para que nada quede 'pegado'."""
        self.sources.clear()

    def start_capture(self):
        self.capturing, self.captured = True, None

    def stop_capture(self):
        self.capturing = False

    # ---- eventos -------------------------------------------------------------
    def handle(self, e):
        if e.type == pygame.JOYDEVICEADDED:
            self._open(e.device_index)
        elif e.type == pygame.JOYDEVICEREMOVED:
            self._close(e.instance_id)
        elif e.type == pygame.WINDOWFOCUSLOST:
            self.release_all()
        else:
            for desc, token, pressed, count in self._physical(e):
                self._apply(desc, token, pressed, count)

    def _open(self, device_index):
        try:
            joy = pygame.joystick.Joystick(device_index)
        except pygame.error:
            return
        iid = joy.get_instance_id()
        if iid in self.joys:
            return
        self.joys[iid] = joy
        # estado inicial de palancas y gatillos: no disparar nada al conectar
        for a in range(joy.get_numaxes()):
            self._axes[(iid, a)] = self._axis_dir(0, joy.get_axis(a))
        for h in range(joy.get_numhats()):
            self._hats[(iid, h)] = joy.get_hat(h)

    def _close(self, iid):
        self.joys.pop(iid, None)
        for cmd in list(self.sources):
            self.sources[cmd] = {t for t in self.sources[cmd] if not (t[0].startswith("j") and t[1] == iid)}
        self._hats = {k: v for k, v in self._hats.items() if k[0] != iid}
        self._axes = {k: v for k, v in self._axes.items() if k[0] != iid}

    def _guid(self, iid):
        joy = self.joys.get(iid)
        return joy.get_guid() if joy else ANY

    def _axis_dir(self, current, v, press=None):
        press = self.config["axis_press"] if press is None else press
        release = self.config["axis_release"]
        if current == 1 and v < release:
            current = 0
        elif current == -1 and v > -release:
            current = 0
        if current == 0:
            if v >= press:
                current = 1
            elif v <= -press:
                current = -1
        return current

    def _physical(self, e):
        """Traduce un evento de pygame a (entrada, fuente, apretado, pulsos)."""
        t = e.type
        if t in (pygame.KEYDOWN, pygame.KEYUP):
            yield _k(pygame.key.name(e.key)), ("key", e.key), t == pygame.KEYDOWN, 1
        elif t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if e.button <= 3:  # 4-7 son la ruedita "vieja": ya llega como MOUSEWHEEL
                yield _mb(e.button), ("mouse", e.button), t == pygame.MOUSEBUTTONDOWN, 1
        elif t == pygame.MOUSEWHEEL:
            flip = -1 if getattr(e, "flipped", False) else 1
            for axis, v in (("y", e.y * flip), ("x", e.x * flip)):
                if v:
                    yield _wheel(axis, 1 if v > 0 else -1), None, True, min(3, abs(int(v)) or 1)
        elif t in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            iid = e.instance_id
            desc = {"type": "joy_button", "guid": self._guid(iid), "button": e.button}
            yield desc, ("jb", iid, e.button), t == pygame.JOYBUTTONDOWN, 1
        elif t == pygame.JOYHATMOTION:
            iid = e.instance_id
            prev = self._hats.get((iid, e.hat), (0, 0))
            self._hats[(iid, e.hat)] = e.value
            for i, axis in enumerate("xy"):
                for d in (-1, 1):
                    was, now = prev[i] == d, e.value[i] == d
                    if was != now:
                        desc = {"type": "joy_hat", "guid": self._guid(iid), "hat": e.hat,
                                "axis": axis, "direction": d}
                        yield desc, ("jh", iid, e.hat, axis, d), now, 1
        elif t == pygame.JOYAXISMOTION:
            iid = e.instance_id
            key = (iid, e.axis)
            prev = self._axes.get(key, 0)
            press = CAPTURE_AXIS if self.capturing else None
            now = self._axis_dir(prev, e.value, press)
            if now != prev:
                self._axes[key] = now
                for d, active in ((prev, False), (now, True)):
                    if d:
                        desc = {"type": "joy_axis", "guid": self._guid(iid), "axis": e.axis, "direction": d}
                        yield desc, ("ja", iid, e.axis, d), active, 1

    def _apply(self, desc, token, pressed, count):
        if self.capturing and pressed:
            # las presiones van a la captura; las liberaciones siguen su curso
            # normal (si no, la tecla que abrio la captura quedaria "pegada")
            if self.captured is None:
                self.captured = desc
            return
        for name, lst in self.config["commands"].items():
            if not any(_matches(b, desc) for b in lst):
                continue
            cmd = Command(name)
            if token is None:                         # ruedita: solo pulsos
                self._press(cmd, count)
            elif pressed:
                if token not in self.sources[cmd]:
                    self.sources[cmd].add(token)
                    self._press(cmd, count)
            else:
                self.sources[cmd].discard(token)

    def _press(self, cmd, count):
        self._pulses[cmd] += count
        self._seq += 1
        self._order[cmd] = self._seq
