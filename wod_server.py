from dataclasses import dataclass
import orjson
import socket

import time
import threading

import perlin_noise
import math
import numpy as np
import random

import simple_socket
from constants import (
    ATTACK_DIST,
    BORDER_HEALING_MOD,
    CELL_SIZE,
    CITIES_PER_PLAYER,
    AREA_PER_CITIES,
    CITY_BORDER_RADIUS,
    CITY_DIST_PENAL_FULL,
    CITY_DIST_PENAL_START,
    CITY_DISTANCE,
    CITY_PLACE_TRIES,
    CITY_R,
    CITY_TROOP_CAPACITY,
    CITY_TROOP_GEN_RATE,
    CITY_VISIBILITY_RADIUS,
    COLLISION_DIST,
    ENEMY_COLLISION_DIST,
    HEALING_DIVISOR,
    MIN_CITY_DIST_PENAL,
    NO_CITY_HEALING,
    RATIO,
    PORTS,
    SERVER_FPS,
    TERRAIN_SPEED_MOD,
    TERRAIN_TYPES,
    THRESHOLD,
    FOREST,
    PLAINS,
    HILL,
    MOUNTAIN,
    TROOP_BORDER_RADIUS,
    TROOP_HEALTH,
    TROOP_VISIBILITY_RADIUS,
    Coordinate,
    Terrain_type,
)

def nd_zeros() -> np.ndarray:
    """Creates a numpy array of zeros with dtype of float32.

    Returns:
        np.ndarray: A numpy array of zeros, `world_info.rows + 1`, `world_info.cols + 1`
    """
    return np.zeros((world_info.rows + 1, world_info.cols + 1), dtype=np.float32)

def dir_dis_to_xy(direction: float, distance: float) -> Coordinate:
    """Converts a direction and distance to an x, y offset.

    Args:
        direction (float): Direction in degrees
        distance (float): Distance in that direction

    Returns:
        Coordinate: The x, y offset
    """
    return Coordinate(
        (distance * math.cos(math.radians(direction))),
        (distance * math.sin(math.radians(direction))),
    )


def xy_to_dir_dis(xy: Coordinate) -> tuple[float, float]:
    """Converts an x, y offset to a direction and distance.

    Args:
        xy (Coordinate): The x, y offset

    Returns:
        tuple[float, float]: The direction in degrees and the distance
    """
    x, y = xy
    return math.degrees(math.atan2(y, x)), math.hypot(x, y)


def get_grid_value(grid: np.ndarray, x: float, y: float) -> float:
    """Gets the interpolated value of the grid at a specific x, y coordinate.
    Args:
        grid (np.ndarray): The grid to sample
        x (float): The x coordinate to sample
        y (float): The y coordinate to sample

    Returns:
        float: The interpolated value of the grid at the given coordinates
    """
    x1, y1 = int(x), int(y)
    x2, y2 = min(x1 + 1, world_info.rows), min(y1 + 1, world_info.cols)

    dx, dy = x - x1, y - y1

    p11 = grid[x1, y1]
    p21 = grid[x2, y1]
    p12 = grid[x1, y2]
    p22 = grid[x2, y2]

    val = (
        p11 * (1 - dx) * (1 - dy)
        + p21 * dx * (1 - dy)
        + p12 * (1 - dx) * dy
        + p22 * dx * dy
    )
    return val


class WorldInfo:
    """Holds information about the world size and player count,
    and calculates the world size based on the player count."""

    def __init__(self, players: int) -> None:
        """Initializes the WorldInfo with the number of players and calculates the world size.

        Args:
            players (int): The number of players in the world
        """
        self.players = players
        self.calculate_size()

    def calculate_size(self) -> None:
        """Calculates the world size based on the number of players,
        cities per player, area per city, and aspect ratio."""
        self.area = self.players * CITIES_PER_PLAYER * AREA_PER_CITIES
        self.width = math.sqrt(self.area / RATIO)
        self.height = self.width * RATIO
        self.size = Coordinate(int(self.width), int(self.height))
        self.rows = int(self.size.x // CELL_SIZE)
        self.cols = int(self.size.y // CELL_SIZE)
        self.size = Coordinate(self.rows * CELL_SIZE, self.cols * CELL_SIZE)
        self.world_x, self.world_y = self.size


class Brush:
    """Represents a brush that can be applied to a grid to modify its values in a circular area."""

    def __init__(
        self, radius: float = 40.0, strength: float = 1.0, falloff: float = 0.0
    ) -> None:
        """Initializes the Brush with a radius, strength, and falloff.

        Args:
            radius (float, optional): The radius of the brush. Defaults to 40.0.
            strength (float, optional): The strength of the brush. Defaults to 1.0.
            falloff (float, optional): The falloff of the brush. Defaults to 0.0.
        """
        self.radius = radius
        self.strength = strength
        self.falloff = falloff

    def apply(self, grid: np.ndarray, pos: Coordinate, target_value: float) -> None:
        """Applies the brush to a grid at a specific position,
        modifying the grid values in a circular area based on the brush's strength and falloff.

        Args:
            grid (np.ndarray): The grid to modify
            pos (Coordinate): The position to apply the brush at
            target_value (float): The target value to set the brush area to
        """

        mx, my = pos
        cs = CELL_SIZE
        r = self.radius

        col_start = max(0, int((my - r) / cs))
        col_end = min(world_info.cols + 1, int((my + r) / cs) + 1)
        row_start = max(0, int((mx - r) / cs))
        row_end = min(world_info.rows + 1, int((mx + r) / cs) + 1)

        inv_r = 1.0 / r
        strength = self.strength
        falloff = self.falloff

        for j in range(row_start, row_end):
            px = j * cs
            dx_sq = (px - mx) ** 2

            for i in range(col_start, col_end):
                py = i * cs
                dy = py - my
                dist_sq = dy * dy + dx_sq

                if dist_sq <= r * r:
                    dist = math.sqrt(dist_sq)
                    t = dist * inv_r

                    weight = strength + t * (falloff - strength)

                    old = grid[j, i]
                    grid[j, i] = max(0.0, min(1.0, old + (target_value - old) * weight))


class Environment:
    """Represents the game environment, including terrain, cities, players, and troops."""

    def __init__(self) -> None:
        """Initializes the Environment, generating the terrain and cities,
        and assigning players to cities based on the world information.
        """
        self.terrain_marching = nd_zeros()
        self.forest_marching = nd_zeros()

        self.cities = []

        self.default_vision = nd_zeros()

        self.generate_terrain()
        self.generate_default_vision()
        left_bottom_city = max(self.cities, key=lambda c: c.position.y - c.position.x)
        top_left_city = min(self.cities, key=lambda c: c.position.x + c.position.y)
        middle_top_city = min(
            self.cities,
            key=lambda c: (abs(c.position.x - (world_info.rows * CELL_SIZE) / 2) * 1.5)
            + c.position.y,
        )
        middle_bottom_city = max(
            self.cities,
            key=lambda c: c.position.y
            - (abs(c.position.x - (world_info.rows * CELL_SIZE) / 2) * 1.5),
        )
        top_right_city = min(self.cities, key=lambda c: c.position.y - c.position.x)
        right_bottom_city = max(self.cities, key=lambda c: c.position.x + c.position.y)
        left_city = min(self.cities, key=lambda c: c.position.x)
        right_city = max(self.cities, key=lambda c: c.position.x)
        middle_city = min(
            self.cities,
            key=lambda c: abs(c.position.x - (world_info.rows * CELL_SIZE) / 2)
            + abs(c.position.y - (world_info.cols * CELL_SIZE) / 2),
        )
        if world_info.players == 2:
            self.players = [
                Player(left_city.position, self),
                Player(right_city.position, self),
            ]
            left_city.owner = self.players[0]
            right_city.owner = self.players[1]
        elif world_info.players == 3:
            self.players = [
                Player(left_bottom_city.position, self),
                Player(right_bottom_city.position, self),
                Player(middle_top_city.position, self),
            ]
            left_bottom_city.owner = self.players[0]
            right_bottom_city.owner = self.players[1]
            middle_top_city.owner = self.players[2]
        elif world_info.players == 4:
            self.players = [
                Player(left_bottom_city.position, self),
                Player(top_left_city.position, self),
                Player(top_right_city.position, self),
                Player(right_bottom_city.position, self),
            ]
            left_bottom_city.owner = self.players[0]
            top_left_city.owner = self.players[1]
            top_right_city.owner = self.players[2]
            right_bottom_city.owner = self.players[3]
        elif world_info.players == 5:
            self.players = [
                Player(left_bottom_city.position, self),
                Player(top_left_city.position, self),
                Player(middle_city.position, self),
                Player(top_right_city.position, self),
                Player(right_bottom_city.position, self),
            ]
            left_bottom_city.owner = self.players[0]
            top_left_city.owner = self.players[1]
            middle_city.owner = self.players[2]
            top_right_city.owner = self.players[3]
            right_bottom_city.owner = self.players[4]
        elif world_info.players == 6:
            self.players = [
                Player(left_bottom_city.position, self),
                Player(top_left_city.position, self),
                Player(middle_top_city.position, self),
                Player(middle_bottom_city.position, self),
                Player(top_right_city.position, self),
                Player(right_bottom_city.position, self),
            ]
            left_bottom_city.owner = self.players[0]
            top_left_city.owner = self.players[1]
            middle_top_city.owner = self.players[2]
            middle_bottom_city.owner = self.players[3]
            top_right_city.owner = self.players[4]
            right_bottom_city.owner = self.players[5]
        self.vision_brush = Brush(TROOP_VISIBILITY_RADIUS, 1)
        self.city_vision_brush = Brush(CITY_VISIBILITY_RADIUS, 1)
        self.border_brush = Brush(TROOP_BORDER_RADIUS, 0.05)
        self.city_border_brush = Brush(CITY_BORDER_RADIUS, 0.05)
        self.players_in_cities = [[] for _ in self.cities]

    def generate_terrain(self) -> None:
        """Generates the terrain and forest grids using Perlin noise,
        and places cities on suitable terrain locations.
        """

        def coastal_elevation_bias(x: float, y: float) -> float:
            """Calculates a bias for elevation based on distance from the center of the map,

            Args:
                x (float): The x coordinate to calculate the bias for
                y (float): The y coordinate to calculate the bias for

            Returns:
                float: The elevation bias based on distance from the center,
                with values closer to the "coast" being higher and values near the edges being lower,
                middle values being around 0.75
            """
            cx = world_info.rows / 2
            cy = world_info.cols / 2
            dx = abs(x - cx)
            dy = abs(y - cy)
            dist = math.sqrt(dx**2 + dy**2)
            max_dist = math.sqrt(cx**2 + cy**2)
            normalized_dist = dist / max_dist

            if normalized_dist <= 0.5:
                return 0.5 + max(normalized_dist, 0.25)
            else:
                return 1 - ((normalized_dist - 0.5) * 2)

        noise = perlin_noise.PerlinNoise(octaves=3)
        for y in range(world_info.cols + 1):
            for x in range(world_info.rows + 1):
                value = max(
                    0,
                    min(
                        1,
                        ((noise([x / 25, y / 25])) - 0.2)
                        + ((coastal_elevation_bias(x, y) * (1.2)) - 0.2),
                    ),
                )
                self.terrain_marching[x, y] = value
        forest_noise = perlin_noise.PerlinNoise(octaves=1.1)
        for y in range(world_info.cols + 1):
            for x in range(world_info.rows + 1):
                terrain_value = self.terrain_marching[x, y]
                value = (min(0.6, forest_noise([x / 30, y / 30])) * 2.0) + 0.3
                plains_diff = max(0, (PLAINS.threshold + 0.1) - terrain_value)
                hill_diff = max(0, terrain_value - (HILL.threshold - 0.1))

                diff_mult = 10
                self.forest_marching[x, y] = (
                    value - (plains_diff * diff_mult)
                ) - hill_diff * diff_mult

        def within_edges(cx: int, cy: int) -> bool:
            """Checks if a given coordinate is within the edges of the world,
            with a margin to prevent cities from being placed too close to the edge.

            Args:
                cx (int): The x coordinate to check
                cy (int): The y coordinate to check

            Returns:
                bool: True if the coordinates are within the edges of the world, False otherwise
            """
            edge_margin = 1
            return (
                cx >= edge_margin
                and cx <= world_info.rows - edge_margin
                and cy >= edge_margin
                and cy <= world_info.cols - edge_margin
            )

        tries = 0
        distance = CITY_DISTANCE
        while True:
            cx = random.randint(0, world_info.rows)
            cy = random.randint(0, world_info.cols)
            terrain_value = self.terrain_marching[cx, cy]

            if (
                (terrain_value > PLAINS.threshold and terrain_value < HILL.threshold)
                and all(
                    abs(cx * CELL_SIZE - city.position.x)
                    + abs(cy * CELL_SIZE - city.position.y)
                    >= CELL_SIZE * distance
                    for city in self.cities
                )
                and within_edges(cx, cy)
                and self.forest_marching[cx, cy] < THRESHOLD
            ):
                px = cx * CELL_SIZE
                py = cy * CELL_SIZE
                self.cities.append(City(Coordinate(px, py)))
                distance = CITY_DISTANCE
            if len(self.cities) >= (world_info.players * CITIES_PER_PLAYER):
                break
            tries += 1
            if tries >= CITY_PLACE_TRIES:
                distance = max(1, distance - 1)
                tries = 0

    def generate_default_vision(self) -> None:
        """Generates the default vision grid based on the terrain and forest grids"""
        for y in range(world_info.cols + 1):
            for x in range(world_info.rows + 1):
                terrain_value = self.terrain_marching[x, y]
                forest_value = self.forest_marching[x, y]
                self.default_vision[x, y] = 0.35 + (
                    max(min((((terrain_value + 0.1) / 1) + 0.2), 1), 0.2)
                    + (0.8 if forest_value > 0.6 else 0.0)
                )

    def draw_info(self, player: int) -> tuple[np.ndarray, np.ndarray, list, list]:
        """Returns the vision grid, border grid, visible troops, and cities for a given player.

        Args:
            player (int): The index of the player to get info for

        Returns:
            tuple[np.ndarray, np.ndarray, list, list]: The vision grid, border grid,
            list of visible troops, and list of cities
        """
        ply = self.players[player]
        vision_grid = ply.vision.copy()
        border_grid = ply.border.copy()
        troops = []
        cities = [
            (
                tuple(c.position),
                c.id,
                c.path,
                self.players.index(c.owner) if c.owner is not None else -1,
            )
            for c in self.cities
        ]
        for troop in [t for p in self.players for t in p.troops]:
            ply = self.players[player]

            vision = ply.vision
            pos = troop.position
            gx = pos.x / CELL_SIZE
            gy = pos.y / CELL_SIZE
            gx = max(0, min(world_info.rows, gx))
            gy = max(0, min(world_info.cols, gy))

            if get_grid_value(vision, gx, gy) < THRESHOLD:
                troops.append(
                    (
                        tuple(troop.position),
                        troop.id,
                        self.players.index(troop.owner),
                        troop.path,
                        troop.health,
                        troop.attacking
                    )
                )

        return vision_grid, border_grid, troops, cities

    def get_terrain_info(self) -> tuple[np.ndarray, np.ndarray, list, int]:
        """Gets the terrain and forest grids, list of city positions, and number of players for the world.

        Returns:
            tuple[np.ndarray, np.ndarray, list, int]: The terrain grid, forest grid,
            list of city positions, and number of players
        """
        return (
            self.terrain_marching,
            self.forest_marching,
            [tuple(c.position) for c in self.cities],
            world_info.players,
        )

    def get_terrain(self, value: float, fvalue: float) -> Terrain_type:
        """Determines the terrain type based on the terrain and forest value.
        Args:
            value (float): The terrain value
            fvalue (float): The forest value

        Returns:
            Terrain_type: The terrain type at the given location
        """
        if fvalue > FOREST.threshold:
            return FOREST
        for terrain_type in reversed(TERRAIN_TYPES):
            if value > terrain_type.threshold and terrain_type is not FOREST:
                return terrain_type

    def update_troops(self, paths_to_apply: list) -> None:
        """Updates the troops for all players based on the given paths to apply, and updates the vision for all players accordingly.

        Args:
            paths_to_apply (list): A list of tuples containing the troop id and the path to apply for that troop
        """
        self.players_in_cities = [[] for _ in self.cities]
        troop_ids = [info[0] for info in paths_to_apply]
        troop_paths = [info[1] for info in paths_to_apply]
        for player in self.players:
            self._update_player_vision_and_border(player)
            self._update_player_troops(player, troop_ids, troop_paths)

    def _update_player_vision_and_border(self, player: Player) -> None:
        """Updates the vision and border grids for a given player based on the cities they own and the cities owned by other players.

        Args:
            player (Player): The player to update the vision and border for.
        """
        player.vision = self.default_vision.copy()
        for city in self.cities:
            if city.owner is player:
                self.city_vision_brush.apply(player.vision, city.position, 0)
                self.city_border_brush.apply(player.border, city.position, 1.0)
        for other_player in self.players:
            if player is not other_player:
                for city in self.cities:
                    if city.owner is other_player:
                        self.city_border_brush.apply(player.border, city.position, 0.0)

    def _update_player_troops(
        self, player: Player, troop_ids: list, troop_paths: list
    ) -> None:
        """Updates the troops for a given player based on the provided troop ids and paths.

        Args:
            player (Player): The player whose troops are being updated
            troop_ids (list): The list of troop ids to update
            troop_paths (list): The list of paths to apply to the troops
        """
        to_remove = []
        for troop in player.troops:
            if troop.health <= 0:
                to_remove.append(troop)
                continue
            try:
                tidx = troop_ids.index(id(troop))
                troop.path = troop_paths[tidx]
            except ValueError:
                pass
            self._update_troop(player, troop)
        to_remove.reverse()
        for t in to_remove:
            player.troops.remove(t)

    def _update_troop(self, player: Player, troop: Troop) -> None:
        """Updates a single troop's position, health, and vision.

        Args:
            player (Player): The player the troop belongs to
            troop (Troop): The troop to update
        """
        old_pos = troop.position
        self._update_troop_health(player, troop, old_pos)
        enemies_in_range = []
        gx, gy = old_pos.x / CELL_SIZE, old_pos.y / CELL_SIZE
        terrain, forest = get_grid_value(self.terrain_marching, gx, gy), get_grid_value(
            self.forest_marching, gx, gy
        )
        on_terrain = self.get_terrain(terrain, forest)

        if troop.path:
            new_pos, enemies_in_range, on_terrain = self._move_troop_to_target(
                player, troop, old_pos, on_terrain, enemies_in_range
            )
        else:
            new_pos, enemies_in_range, on_terrain = self._move_troop_idle(
                player, troop, old_pos, on_terrain, enemies_in_range
            )

        self._apply_combat(enemies_in_range, on_terrain, troop)
        self._update_troop_vision_and_border(player, troop, on_terrain)
        self._check_troop_in_city(troop)

    def _update_troop_health(
        self, player: Player, troop: Troop, old_pos: Coordinate
    ) -> None:
        """Updates the health of a troop based on its distance from the nearest city owned by the player,
        and the average border strength along the line between the troop and the city.

        Args:
            player (Player): The player the troop belongs to
            troop (Troop): The troop whose health is being updated
            old_pos (Coordinate): The previous position of the troop
        """
        owned = [city.position for city in self.cities if city.owner is player]
        if owned:
            closest_city = min(
                owned,
                key=lambda x: xy_to_dir_dis(((old_pos.x - x.x), (old_pos.y - x.y)))[1],
            )
            city_dir, city_dist = xy_to_dir_dis(
                ((old_pos.x - closest_city.x), (old_pos.y - closest_city.y))
            )
            sample_points = [
                dir_dis_to_xy(city_dir, dist * CELL_SIZE)
                for dist in range(int(city_dist // CELL_SIZE) + 1)
            ]
            border_avg = 0
            if sample_points:
                border_avgs = []
                for other_player in self.players:
                    if other_player is not player:
                        border_avgs.append(
                            sum(
                                [
                                    get_grid_value(
                                        other_player.border,
                                        (closest_city.x + s_p.x) / CELL_SIZE,
                                        (closest_city.y + s_p.y) / CELL_SIZE,
                                    )
                                    for s_p in sample_points
                                ]
                            )
                            / len(sample_points)
                        )
                border_avg = sum(border_avgs) / len(border_avgs)
            dist_penal = max(
                ((city_dist + CITY_DIST_PENAL_START) / CITY_DIST_PENAL_FULL),
                MIN_CITY_DIST_PENAL,
            )
            healing_power = (1 - (border_avg * BORDER_HEALING_MOD)) - dist_penal
        else:
            healing_power = NO_CITY_HEALING
        troop.health += healing_power / HEALING_DIVISOR
        if troop.health > TROOP_HEALTH:
            troop.health = TROOP_HEALTH

    def _move_troop_to_target(
        self,
        player: Player,
        troop: Troop,
        old_pos: Coordinate,
        on_terrain: Terrain_type,
        enemies_in_range: list,
    ) -> tuple[Coordinate, list, Terrain_type]:
        """Moves a troop towards its target based on its path, while avoiding allies and checking for collisions with enemies and terrain.

        Args:
            player (Player): The player the troop belongs to
            troop (Troop): The troop to move
            old_pos (Coordinate): The previous position of the troop
            on_terrain (Terrain_type): The terrain type the troop is currently on
            enemies_in_range (list): A list of enemies currently in range of the troop

        Returns:
            tuple[Coordinate, list, Terrain_type]: The new position of the troop, the updated list of enemies in range, and the terrain type the troop is now on.
        """
        target = Coordinate(*troop.path[0])
        terrain_speed = on_terrain.speed_mod
        dir, distance = xy_to_dir_dis((target.x - old_pos.x, target.y - old_pos.y))
        distance = terrain_speed * TERRAIN_SPEED_MOD
        new_off_x, new_off_y = dir_dis_to_xy(dir, distance)
        new_pos = Coordinate(old_pos.x + new_off_x, old_pos.y + new_off_y)

        new_pos = self._avoid_allies(player, troop, new_pos)
        new_pos, enemies_in_range, on_terrain = self._check_collisions(
            player, troop, new_pos, enemies_in_range
        )

        dir, distance = xy_to_dir_dis(
            (target.x - troop.position.x, target.y - troop.position.y)
        )
        if distance < ((terrain_speed * TERRAIN_SPEED_MOD) * 2):
            troop.path.pop(0)

        return new_pos, enemies_in_range, on_terrain

    def _move_troop_idle(
        self,
        player: Player,
        troop: Troop,
        old_pos: Coordinate,
        on_terrain: Terrain_type,
        enemies_in_range: list,
    ) -> tuple[Coordinate, list, Terrain_type]:
        """Moves a troop that is not following a path (idle).

        Args:
            player (Player): The player the troop belongs to
            troop (Troop): The troop to move
            old_pos (Coordinate): The previous position of the troop
            on_terrain (Terrain_type): The terrain type the troop is currently on
            enemies_in_range (list): A list of enemies currently in range of the troop
        Returns:
            tuple[Coordinate, list, Terrain_type]: The new position of the troop,
            the updated list of enemies in range, and the terrain type the troop is now on.
        """
        new_pos = self._avoid_allies(player, troop, old_pos)
        new_pos, enemies_in_range, on_terrain = self._check_collisions(
            player, troop, new_pos, enemies_in_range
        )
        return new_pos, enemies_in_range, on_terrain

    def _avoid_allies(
        self, player: Player, troop: Troop, new_pos: Coordinate
    ) -> Coordinate:
        """Keeps troop away from positions occupied by allies.

        Args:
            player (Player): The player the troop belongs to
            troop (Troop): The troop to move
            new_pos (Coordinate): The proposed new position of the troop

        Returns:
            Coordinate: The adjusted position of the troop, avoiding allies.
        """
        for other_t in player.troops:
            if other_t == troop:
                continue
            other_x, other_y = other_t.position
            old_off_x, old_off_y = new_pos.x - other_x, new_pos.y - other_y
            dir, distance = xy_to_dir_dis((old_off_x, old_off_y))
            if distance < COLLISION_DIST:
                distance = COLLISION_DIST
                new_off = dir_dis_to_xy(dir, distance)
                change = Coordinate(new_off.x - old_off_x, new_off.y - old_off_y)
                new_pos = Coordinate(new_pos.x + change.x, new_pos.y + change.y)
                if troop.path:
                    target = Coordinate(*troop.path[0])
                    off = (target.x - other_x, target.y - other_y)
                    dir, distance = xy_to_dir_dis(off)
                    if distance < COLLISION_DIST and len(troop.path) > 1:
                        troop.path.pop(0)

        return new_pos

    def _check_collisions(
        self, player: Player, troop: Troop, new_pos: Coordinate, enemies_in_range: list
    ) -> tuple[Coordinate, list, Terrain_type]:
        """Checks for collisions with other troops and terrain.

        Args:
            player (Player): The player the troop belongs to
            troop (Troop): The troop to check collisions for
            new_pos (Coordinate): The proposed new position of the troop
            enemies_in_range (list): A list of enemies currently in range of the troop

        Returns:
            tuple[Coordinate, list, Terrain_type]: The new position of the troop,
            the updated list of enemies in range, and the terrain type the troop is now on.
        """
        gx = new_pos.x / CELL_SIZE
        gy = new_pos.y / CELL_SIZE
        terrain = get_grid_value(self.terrain_marching, gx, gy)
        forest = get_grid_value(self.forest_marching, gx, gy)
        new_terrain = self.get_terrain(terrain, forest)

        hit_enemy = False
        for other_player in self.players:
            if player is not other_player:
                self.border_brush.apply(other_player.border, troop.position, 0.0)
                for other_t in other_player.troops:
                    other_x, other_y = other_t.position
                    off_x, off_y = new_pos.x - other_x, new_pos.y - other_y
                    dir, distance = xy_to_dir_dis((off_x, off_y))
                    if distance < ENEMY_COLLISION_DIST:
                        distance = ENEMY_COLLISION_DIST
                        new_off = dir_dis_to_xy(dir, distance)
                        change = Coordinate(new_off.x - off_x, new_off.y - off_y)
                        new_pos = Coordinate(new_pos.x + change.x, new_pos.y + change.y)
                        # hit_enemy = True
                    if distance < ATTACK_DIST:
                        enemies_in_range.append((other_t, distance))

        out_of_world = (
            new_pos.x > world_info.world_x
            or new_pos.x < 0
            or new_pos.y > world_info.world_y
            or new_pos.y < 0
        )

        if  new_terrain is not MOUNTAIN and not out_of_world:# and not hit_enemy
            troop.position = new_pos

        return new_pos, enemies_in_range, new_terrain

    def _apply_combat(self, enemies_in_range: list, on_terrain: Terrain_type, troop: Troop) -> None:
        """Applies combat damage to nearest enemy in range based on terrain.

        Args:
            enemies_in_range (list): A list of enemies currently in range of the troop
            on_terrain (Terrain_type): The terrain type the troop is on
        """
        if enemies_in_range:
            attack_power = on_terrain.attack_mod / 25
            closest = min(enemies_in_range, key=lambda x: x[1])
            closest[0].health -= attack_power
        troop.attacking = bool(enemies_in_range)

    def _update_troop_vision_and_border(
        self, player: Player, troop: Troop, on_terrain: Terrain_type
    ) -> None:
        """Updates the vision and border grids for a troop based on its current terrain.

        Args:
            player (Player): The player the troop belongs to
            troop (Troop): The troop to update vision and border for
            on_terrain (Terrain_type): The terrain type the troop is on
        """
        if on_terrain is HILL:
            self.city_vision_brush.apply(player.vision, troop.position, 0)
        else:
            self.vision_brush.apply(player.vision, troop.position, 0)
        self.border_brush.apply(player.border, troop.position, 1.0)

    def _check_troop_in_city(self, troop: Troop) -> None:
        """Checks if a troop is in a city and adds it's owner to the list of players in that city.

        Args:
            troop (Troop): The troop to check
        """
        for _i, city in enumerate(self.cities):
            cx, cy = city.position
            tx, ty = troop.position
            dir, dist = xy_to_dir_dis((tx - cx, ty - cy))
            if dist < CITY_R and troop.owner not in self.players_in_cities[_i]:
                self.players_in_cities[_i].append(troop.owner)
                break

    def update_cities(self, paths_to_apply: list) -> None:
        """Updates the ownership and troop production of cities
        based on the players currently in the cities and the paths to apply for each city.

        Args:
            paths_to_apply (list): A list of tuples (city_id, path) to apply to each city
        """
        city_ids = [info[0] for info in paths_to_apply]
        city_paths = [info[1] for info in paths_to_apply]
        for i, city in enumerate(self.cities):
            try:
                cidx = city_ids.index(id(city))
                city.path = city_paths[cidx]
            except ValueError:
                pass
            cx, cy = city.position
            last_owner = city.owner
            if len(self.players_in_cities[i]) == 1:
                city.owner = self.players_in_cities[i][0]
            if last_owner is not city.owner:
                city.timer = 0
                city.path = []
            if city.owner is not None:
                city.timer += 1
                t_per_c = len(city.owner.troops) / len(
                    [c for c in self.cities if c.owner == city.owner]
                )
                if city.timer >= (SERVER_FPS * (CITY_TROOP_GEN_RATE * max(1, t_per_c))) and t_per_c < CITY_TROOP_CAPACITY:
                    city.owner.troops.append(
                        Troop(
                            Coordinate(
                                cx + random.randrange(-6, 6),
                                cy + random.randrange(-6, 6),
                            ),
                            city.owner,
                            city.path.copy(),
                        )
                    )
                    city.timer = 0


@dataclass
class Troop:
    """Represents a troop in the game world."""

    position: Coordinate
    owner: object
    path: list = None
    health: int = TROOP_HEALTH

    def __post_init__(self) -> None:
        """Initializes the troop's ID and path if not set."""
        if self.path is None:
            self.path = []
        self.id = id(self)


@dataclass
class City:
    """Represents a city in the game world."""

    position: Coordinate
    timer: int = 0
    owner: object = None

    def __post_init__(self) -> None:
        """Initializes the city's ID and path."""
        self.id = id(self)
        self.path = []


class Player:
    """Represents a player in the game world, including their starting position, troops, vision, and border."""

    def __init__(self, start_pos, environment) -> None:
        """Initializes the player with a starting position, creates an initial troop for the player,
        and sets up the vision and border grids based on the environment's default vision.

        Args:
            start_pos (_type_): The starting position of the player in the world
            environment (_type_): The environment object that contains default vision data
        """
        self.start_pos = start_pos
        self.troops = [Troop(self.start_pos, self)]
        self.border = nd_zeros()
        self.vision = environment.default_vision.copy()


class Game:
    def __init__(self) -> None:
        """Initializes the game, setting up the server, environment, player inputs, and threading events for synchronization."""
        self.FPS = SERVER_FPS
        self.last_time = time.perf_counter()
        self.frame_time = 1 / self.FPS
        self.done = False
        self.server = simple_socket.Server(
            socket.gethostbyname(str(socket.gethostname())), PORTS[0]
        )
        self.environment = Environment()
        self.player_inputs = [[] for i in range(world_info.players)]
        self.player_city_inputs = [[] for i in range(world_info.players)]
        self.player_pause_requests = [
            threading.Event() for i in range(world_info.players)
        ]
        self.started_event = threading.Event()
        self.player_connected_events = [
            threading.Event() for i in range(world_info.players)
        ]
        self.player_threads = [
            threading.Thread(target=self.handle_player, args=(i,))
            for i in range(world_info.players)
        ]
        self.draw_info = [
            (
                nd_zeros(),
                nd_zeros(),
                [],
                [],
            )
            for i in range(world_info.players)
        ]

    def run_game(self) -> None:
        """Runs the main game loop, handling player connections, game logic updates, and synchronization of player actions and game state."""
        try:
            port = int(input("Enter port to use (0 - 99): "))
            self.server.port = PORTS[max(0, min(99, port))]
        except ValueError:
            port = 0
            self.server.port = PORTS[port]
        print(
            "ip: ",
            self.server.ip,
            ", port: ",
            port,
            " (",
            self.server.port,
            ")",
            sep="",
        )
        print("starting server...")
        self.server.start()
        print("waiting for players...")
        self.server.lsn(conns=world_info.players)
        for player_num in range(world_info.players):
            self.player_threads[player_num].start()
        for player_num in range(world_info.players):
            self.player_connected_events[player_num].wait()
        print("All players connected, starting game!")
        self.started_event.set()
        self.fame = 0
        last_report = time.perf_counter()
        while not self.done:
            all_paused = all(
                [
                    not self.player_pause_requests[i].is_set()
                    for i in range(world_info.players)
                ]
            )
            if all_paused:
                time.sleep(0.1)
                continue
            self.game_logic()
            current_time = time.perf_counter()
            delta_time = current_time - self.last_time
            if delta_time < self.frame_time:
                time.sleep(self.frame_time - delta_time)
            self.last_time = time.perf_counter()
            self.fame += 1
            if current_time - last_report >= 30:
                fps = 1 / delta_time if delta_time > 0 else 0
                print(
                    f"Speed: {fps} FPS",
                    f"Delta Time: {delta_time:.4f} seconds",
                    f"sleep time: {self.frame_time - delta_time:.4f} seconds",
                )
                last_report = current_time

    def handle_player(self, player_number: int) -> None:
        """Handles the connection and communication with a single player,
        including sending initial terrain information, receiving player inputs,
        and sending updated game state information.

        Args:
            player_number (int): The number of the player to handle.
        """
        while not self.done:
            self.player_pause_requests[player_number].clear()
            print("Waiting for player ", player_number, " to connect...")
            try:
                conn, addr = self.server.accept()
                self.player_connected_events[player_number].set()
                print("player: ", player_number, " connected")

                self.server.send(
                    [conn],
                    orjson.dumps(
                        (
                            *self.environment.get_terrain_info(),
                            player_number,
                        ),
                        option=orjson.OPT_SERIALIZE_NUMPY,
                    ),
                )
                self.started_event.wait()
                self.player_pause_requests[player_number].set()
                draw_info = orjson.dumps(
                    self.draw_info[player_number], option=orjson.OPT_SERIALIZE_NUMPY
                )
                while True:
                    draw_info = orjson.dumps(
                        self.draw_info[player_number],
                        option=orjson.OPT_SERIALIZE_NUMPY,
                    )
                    self.server.send([conn], draw_info)
                    try:
                        player_in = orjson.loads(self.server.rcv(conn))
                    except Exception as e:
                        print("Error receiving data from player: ", player_number, e)
                        player_in = [[], []]
                    if player_in == "close" or self.done:
                        self.server.close(conn)
                        print("player: ", player_number, " left")
                        break
                    if player_in:
                        if player_in == "pause":
                            self.player_pause_requests[player_number].clear()
                        elif player_in == "unpause":
                            self.player_pause_requests[player_number].set()
                        else:
                            self.player_inputs[player_number].extend(player_in[0])
                            self.player_city_inputs[player_number].extend(player_in[1])
            except Exception as e:
                print("Error handling player: ", player_number, e)
                self.server.close(conn)
                print("player: ", player_number, " left")

    def game_logic(self) -> None:
        """Processes the game logic for each frame,
        updates city ownership and troop movements based on player inputs."""
        city_paths_to_apply = []
        for p_num in range(world_info.players):
            if self.player_city_inputs[p_num]:
                city_paths_to_apply.extend(self.player_city_inputs[p_num])
        self.player_city_inputs = [[] for i in range(world_info.players)]
        self.environment.update_cities(city_paths_to_apply)
        paths_to_apply = []
        for p_num in range(world_info.players):
            if self.player_inputs[p_num]:
                paths_to_apply.extend(self.player_inputs[p_num])
        self.player_inputs = [[] for i in range(world_info.players)]
        self.environment.update_troops(paths_to_apply)
        self.draw_info = [
            self.environment.draw_info(i) for i in range(world_info.players)
        ]


if __name__ == "__main__":
    try:
        players = int(input("Enter number of players (2-6): "))
        if players < 2 or players > 6:
            print("Invalid number of players, defaulting to 2")
            players = 2
        world_info = WorldInfo(players)
    except ValueError:
        print("Invalid number of players, defaulting to 2")
        world_info = WorldInfo(2)
    game_play = Game()
    game_play.run_game()
