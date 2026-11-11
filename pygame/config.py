"""Constantes del juego, rutas y lectura/escritura de archivos de usuario."""
import json
import os

# ------------------------------------------------------------------ reglas --
COLS, ROWS = 8, 16
MATCH_LEN = 4            # cuantos del mismo color en linea eliminan
SPAWN_COL = 3
MAX_LEVEL = 20

RED, YELLOW, BLUE = 0, 1, 2
PILL_COLORS = (RED, YELLOW, BLUE)

# ---------------------------------------------------------------- tiempos --
# todo en milisegundos
CLEAR_TIME = 250         # explosion de lo eliminado
SOFT_DROP = 35           # una fila al mantener abajo
THROW_TIME = 520         # vuelo de la pastilla de la mano al frasco
MAX_DT = 100             # tope por cuadro para no "saltar" tras un tiron


def gravity_for(level):
    """ms por fila de la pastilla que controlas."""
    return max(90, 650 - level * 35)


def fall_step_for(level):
    """ms por fila de los pedazos sueltos tras una eliminacion: el doble de
    rapido que la pastilla de ese nivel, asi se siente proporcional."""
    return gravity_for(level) // 2


def virus_count_for(level):
    return min(4 * (level + 1), 96)


# ------------------------------------------------------------------ rutas --
ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")


def user_dir():
    """Carpeta escribible para configuracion y records.

    DRPYTHON_CONFIG_DIR la fuerza (util en PortMaster: apuntarla a conf/);
    si no, se usa $XDG_CONFIG_HOME/dr-python o ~/.config/dr-python."""
    path = os.environ.get("DRPYTHON_CONFIG_DIR")
    if not path:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        path = os.path.join(base, "dr-python")
    os.makedirs(path, exist_ok=True)
    return path


def cache_dir():
    """Carpeta para los sprites ya escalados a cada resolucion.

    DRPYTHON_CACHE_DIR la fuerza; si no, $XDG_CACHE_HOME/dr-python o
    ~/.cache/dr-python. Devuelve None si no se puede crear (sin cache)."""
    path = os.environ.get("DRPYTHON_CACHE_DIR")
    if not path:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        path = os.path.join(base, "dr-python")
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        return None


def load_json(name, default):
    try:
        with open(os.path.join(user_dir(), name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, data):
    """Escritura atomica: si se corta la luz no queda un archivo a medias."""
    path = os.path.join(user_dir(), name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------- ajustes --
DEFAULT_SETTINGS = {
    # "auto": pantalla completa si no hay escritorio (consola/KMS, ej. Anbernic)
    "fullscreen": "auto",
}


def load_settings():
    data = load_json("settings.json", {})
    return {**DEFAULT_SETTINGS, **data}
