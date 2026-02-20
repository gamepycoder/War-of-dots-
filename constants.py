from collections import namedtuple

Coordinate = namedtuple('Coordinate', 'x y', defaults=[0, 0])

CELL_SIZE = 20
PLAYERS = 2
CITIES_PER_PLAYER = 5
CITY_DISTANCE = 15
AREA_PER_CITIES = 80000
RATIO = 9/16
AREA = PLAYERS * CITIES_PER_PLAYER * AREA_PER_CITIES

CITY_PLACE_TRIES = 100

class Terrain_type:
    def __init__(self, name, color, threshold, attack_mod=1, speed_mod=1):
        self.name = name
        self.color = color
        self.threshold = threshold
        self.attack_mod = attack_mod
        self.speed_mod = speed_mod

FOREST = Terrain_type("forest", (30, 125, 30), 0.5, attack_mod=0.75, speed_mod=0.8)
WATER = Terrain_type("water", (0, 220, 255), -0.1, attack_mod=0.5, speed_mod=0.6)
PLAINS = Terrain_type("plains", (20, 180, 20), 0.1, attack_mod=1.0, speed_mod=1.0)
HILL = Terrain_type("hill", (150, 150, 150), 0.7, attack_mod=1.5, speed_mod=0.7)
MOUNTAIN = Terrain_type("mountain", (100, 100, 100), 0.83, attack_mod=0.0, speed_mod=3.0)

CITY_COLOR = (255, 215, 0)

TERRAIN_TYPES = [
    WATER,
    FOREST,
    PLAINS,
    HILL,
    MOUNTAIN,
]

THRESHOLD = 0.5

TROOP_R = 7
TROOP_D = 2 * TROOP_R
CITY_R = 15
CITY_D = 2 * CITY_R

RED = (255, 0, 0)
BLUE = (0, 0, 255)
ORANGE = (255, 150, 0)
PURPLE = (175, 0, 175)
GREEN = (0, 175, 0)
CYAN = (0, 255, 255)

COLORS = [RED, BLUE, ORANGE, PURPLE, GREEN, CYAN]

TABLE = {
    1: [["v0", "p_top", "p_left"]],
    2: [["v1", "p_right", "p_top"]],
    3: [["p_left", "v0", "v1", "p_right"]],
    4: [["v2", "p_bottom", "p_right"]],
    5: [["v0", "p_top", "p_left"], ["v2", "p_right", "p_bottom"]],
    6: [["p_top", "v1", "v2", "p_bottom"]],
    7: [["p_left", "v0", "v1", "v2", "p_bottom"]],
    8: [["v3", "p_left", "p_bottom"]],
    9: [["p_top", "v0", "v3", "p_bottom"]],
    10: [["p_top", "v1", "p_right"], ["p_bottom", "v3", "p_left"]],
    11: [["v0", "v1", "p_right", "p_bottom", "v3"]],
    12: [["p_right", "v2", "v3", "p_left"]],
    13: [["v0", "p_top", "p_right", "v2", "v3"]],
    14: [["v1", "v2", "v3", "p_left", "p_top"]],
}

PORTS = [i for i in range(1200, 1300)]

TROOP_HEALTH = 100

CITY_DIST_PENAL_START = 250
CITY_DIST_PENAL_FULL = 1000
MIN_CITY_DIST_PENAL = 0.5
HEALING_DIVISOR = 25
NO_CITY_HEALING = -0.5
BORDER_HEALING_MOD = 0.5

TERRAIN_SPEED_MOD = 0.15
ATTACK_DIST = 32
COLLISION_DIST = 16
ENEMY_COLLISION_DIST = 30

PATH_SPACING = 100

TROOP_VISIBILITY_RADIUS = 75
CITY_VISIBILITY_RADIUS = 175
TROOP_BORDER_RADIUS = 40
CITY_BORDER_RADIUS = 80

CITY_TROOP_CAPACITY = 10
CITY_TROOP_GEN_RATE = 20

SERVER_FPS = 45
        