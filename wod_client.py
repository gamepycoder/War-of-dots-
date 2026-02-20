import random
import pygame
import orjson
import math
import numpy as np

from constants import (
    CITY_COLOR,
    CITY_R,
    HILL,
    MOUNTAIN,
    PATH_SPACING,
    PLAINS,
    TABLE,
    CELL_SIZE,
    CITIES_PER_PLAYER,
    AREA_PER_CITIES,
    RATIO,
    THRESHOLD,
    COLORS,
    PORTS,
    TERRAIN_TYPES,
    FOREST,
    TROOP_D,
    TROOP_HEALTH,
    TROOP_R,
    WATER,
)
import simple_socket


def dir_dis_to_xy(direction: float, distance: float) -> tuple:
    """Converts a direction and distance to an x, y offset.

    Args:
        direction (float): Direction in degrees
        distance (float): Distance in that direction

    Returns:
        tuple: The x, y offset
    """
    return (
        (distance * math.cos(math.radians(direction))),
        (distance * math.sin(math.radians(direction))),
    )


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
        self.size = (int(self.width), int(self.height))
        self.rows = int(self.size[0] // CELL_SIZE)
        self.cols = int(self.size[1] // CELL_SIZE)
        self.size = (self.rows * CELL_SIZE, self.cols * CELL_SIZE)
        self.world_x, self.world_y = self.size


def interp(threshold: float, a: float, b: float) -> float:
    """Interpolates a value between two values based on a threshold.

    Args:
        threshold (float): The threshold value to interpolate against
        a (float): The first value
        b (float): The second value

    Returns:
        float: The interpolated value between a and b based on the threshold
    """
    if a == b:
        return 0.5
    t = (threshold - a) / (b - a)
    return max(0.0, min(1.0, t))


def marching_squares(
    grid: np.ndarray, cell_size: float, rows: int, cols: int, threshold: float
) -> list:
    """Performs marching squares on a grid to extract contour lines.

    Args:
        grid (np.ndarray): The grid to perform marching squares on
        cell_size (float): The size of each cell in the grid
        rows (int): The number of rows in the grid
        cols (int): The number of columns in the grid
        threshold (float): The threshold value to use for contour extraction

    Returns:
        list: The list of segments extracted from the grid
    """
    segments = []
    cs = cell_size
    for j in range(rows):
        for i in range(cols):
            c0 = grid[j, i]
            c3 = grid[j, i + 1]
            c2 = grid[j + 1, i + 1]
            c1 = grid[j + 1, i]

            p_top = interp(threshold, c0, c1)
            p_right = interp(threshold, c1, c2)
            p_bottom = interp(threshold, c3, c2)
            p_left = interp(threshold, c0, c3)

            x = j * cs
            y = i * cs
            p0 = (x + p_top * cs, y)
            p1 = (x + cs, y + p_right * cs)
            p2 = (x + p_bottom * cs, y + cs)
            p3 = (x, y + p_left * cs)
            idx = 0
            if c0 > threshold:
                idx |= 1
            if c1 > threshold:
                idx |= 2
            if c2 > threshold:
                idx |= 4
            if c3 > threshold:
                idx |= 8
            if idx == 0 or idx == 15:
                pass
            elif idx == 1:
                segments.append((p3, p0))
            elif idx == 2:
                segments.append((p0, p1))
            elif idx == 3:
                segments.append((p3, p1))
            elif idx == 4:
                segments.append((p1, p2))
            elif idx == 5:
                segments.append((p3, p0))
                segments.append((p1, p2))
            elif idx == 6:
                segments.append((p0, p2))
            elif idx == 7:
                segments.append((p3, p2))
            elif idx == 8:
                segments.append((p2, p3))
            elif idx == 9:
                segments.append((p0, p2))
            elif idx == 10:
                segments.append((p0, p1))
                segments.append((p2, p3))
            elif idx == 11:
                segments.append((p1, p2))
            elif idx == 12:
                segments.append((p1, p3))
            elif idx == 13:
                segments.append((p0, p1))
            elif idx == 14:
                segments.append((p3, p0))
    return segments


def marching_squares_poly(
    grid: np.ndarray, cell_size: float, rows: int, cols: int, threshold: float
) -> list:
    """Performs marching squares on a grid to extract polygonal regions.

    Args:
        grid (np.ndarray): The grid to perform marching squares on
        cell_size (float): The size of each cell in the grid
        rows (int): The number of rows in the grid
        cols (int): The number of columns in the grid
        threshold (float): The threshold value to use for polygon extraction

    Returns:
        list: The list of polygons extracted from the grid
    """
    polys = []
    cs = cell_size
    thr = threshold

    for i in range(rows):
        for j in range(cols):
            c0 = grid[i, j]
            c1 = grid[i, j + 1]
            c2 = grid[i + 1, j + 1]
            c3 = grid[i + 1, j]

            row_pos = i * cs
            col_pos = j * cs

            v0 = (row_pos, col_pos)
            v1 = (row_pos, col_pos + cs)
            v2 = (row_pos + cs, col_pos + cs)
            v3 = (row_pos + cs, col_pos)

            p_top = (row_pos, col_pos + interp(threshold, c0, c1) * cs)
            p_right = (row_pos + interp(threshold, c1, c2) * cs, col_pos + cs)
            p_bottom = (row_pos + cs, col_pos + interp(threshold, c3, c2) * cs)
            p_left = (row_pos + interp(threshold, c0, c3) * cs, col_pos)

            inside = [c0 > thr, c1 > thr, c2 > thr, c3 > thr]
            idx = 0
            if inside[0]:
                idx |= 1
            if inside[1]:
                idx |= 2
            if inside[2]:
                idx |= 4
            if inside[3]:
                idx |= 8

            if idx == 0:
                continue
            if idx == 15:
                polys.append([v0, v1, v2, v3])
                continue

            pts = {
                "v0": v0,
                "v1": v1,
                "v2": v2,
                "v3": v3,
                "p_top": p_top,
                "p_right": p_right,
                "p_bottom": p_bottom,
                "p_left": p_left,
            }

            specs = TABLE.get(idx, [])
            for spec in specs:
                poly = [pts[name] for name in spec]
                compact = []
                for p in poly:
                    if not compact or (
                        abs(p[0] - compact[-1][0]) > 1e-9
                        or abs(p[1] - compact[-1][1]) > 1e-9
                    ):
                        compact.append(p)
                if len(compact) >= 3:
                    polys.append(compact)

    return polys


def marching_squares_layers(
    grid: np.ndarray, cell_size: float, rows: int, cols: int, thresholds: list[float]
) -> list:
    """Performs marching squares on a grid to extract polygonal regions for multiple thresholds, creating layers of polygons.

    Args:
        grid (np.ndarray): The grid to perform marching squares on
        cell_size (float): The size of each cell in the grid
        rows (int): The number of rows in the grid
        cols (int): The number of columns in the grid
        thresholds (list[float]): The list of threshold values to use for polygon extraction

    Returns:
        list: The list of layers of polygons extracted from the grid
    """
    layers = []
    for thr in thresholds:
        threshold = thr
        polys = marching_squares_poly(grid, cell_size, rows, cols, threshold)
        layers.append(polys)
    return layers


class Game:
    """Represents the client-side game application, handling the connection to the server, receiving terrain and game state information,
    and managing the player input and rendering of the game world.
    """

    def __init__(self, title: str) -> None:
        """Initializes the Game client, connects to the server, receives initial terrain and game state information,
        and sets up the game window and rendering parameters.

        Args:
            title (str): The title of the game window
        """
        ip, port = input("ip\n: "), input("\nport\n: ")
        print("connecting...")
        while True:
            try:
                self.client = simple_socket.Client(
                    ip, PORTS[min(99, max(0, int(port)))]
                )
                self.client.connect()
                break
            except Exception as e:
                print(f"connection error: {e}")
                print(
                    "connection failed, make sure server has started and ip and port match, trying again..."
                )
        print("connection successful!")

        print("drawing terrain...")
        try:
            (
                self.terrain_grid,
                self.forrest_grid,
                self.cities,
                players,
                self.player_num,
            ) = orjson.loads(self.client.rcv())
            self.terrain_grid = np.array(self.terrain_grid)
            self.forrest_grid = np.array(self.forrest_grid)
        except Exception as e:
            print(f"error loading terrain data: {e}")
            print("unable to load terrain data, closing connection")
            self.client.close()
            raise
        self.world_info = WorldInfo(players)
        pygame.init()
        info_object = pygame.display.Info()
        desktop_width = info_object.current_w
        desktop_height = info_object.current_h
        self.size = (desktop_width - 20, desktop_height - 100)
        self.factor = min(
            self.size[0] / self.world_info.world_x,
            self.size[1] / self.world_info.world_y,
        )
        self.screen = pygame.display.set_mode(self.size)
        pygame.display.set_caption(title)
        pygame.event.set_allowed(
            [
                pygame.KEYDOWN,
                pygame.QUIT,
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP,
                pygame.MOUSEMOTION,
                pygame.MOUSEWHEEL,
            ]
        )
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 48)
        self.done = False

        self.zoom_levels = [1, 1.2, 1.4, 1.6, 1.8, 2, 2.5, 3, 3.5, 4]
        self.zoom_idx = self.zoom_levels.index(1)
        self.zoom = self.get_zoom(self.zoom_idx)

        self.camx, self.camy = 0.0, 0.0

        self.panning = False
        self.pan_start_mouse = (0, 0)
        self.pan_start_cam = (0.0, 0.0)

        self.draw_info = None
        self.player_input = "pause"
        self.paths = []
        self.drawing_path = False
        self.city_paths = []
        self.drawing_city_path = False

        self.pause = True

        self.terrain_by_zoom = {}

    def run_game(self) -> None:
        """Runs the main game loop, handling player input, rendering the game world,
        and communicating with the server for game state updates.
        """
        self.color = COLORS[self.player_num]
        layers = marching_squares_layers(
            self.terrain_grid,
            CELL_SIZE,
            self.world_info.rows,
            self.world_info.cols,
            list([t.threshold for t in TERRAIN_TYPES if t is not FOREST]),
        )
        layers.append(
            marching_squares_poly(
                self.forrest_grid,
                CELL_SIZE,
                self.world_info.rows,
                self.world_info.cols,
                FOREST.threshold,
            )
        )

        for i in range(len(self.zoom_levels)):
            z = self.get_zoom(i)
            sw = max(1, int(self.world_info.world_x * z))
            sh = max(1, int(self.world_info.world_y * z))
            surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for poly in layers[0]:
                scaled = [(int(x * z), int(y * z)) for x, y in poly]
                pygame.draw.polygon(surf, WATER.color, scaled, 0)
            for poly in layers[1]:
                scaled = [(int(x * z), int(y * z)) for x, y in poly]
                pygame.draw.polygon(surf, PLAINS.color, scaled, 0)
            for poly in layers[2]:
                scaled = [(int(x * z), int(y * z)) for x, y in poly]
                pygame.draw.polygon(surf, HILL.color, scaled, 0)
            for poly in layers[3]:
                scaled = [(int(x * z), int(y * z)) for x, y in poly]
                pygame.draw.polygon(surf, MOUNTAIN.color, scaled, 0)
            for poly in layers[4]:
                scaled = [(int(x * z), int(y * z)) for x, y in poly]
                pygame.draw.polygon(surf, FOREST.color, scaled, 0)

            for position in self.cities:
                if position is None:
                    continue
                cx, cy = int(position[0] * z), int(position[1] * z)
                pygame.draw.circle(surf, CITY_COLOR, (cx, cy), max(1, int(CITY_R * z)))
            self.terrain_by_zoom[z] = surf

        print("terrain drawn! starting game (waiting for other players)...")
        try:
            self.draw_info = orjson.loads(self.client.rcv())
        except Exception as e:
            print(f"error loading draw info: {e}")
            self.client.close()
            raise
        while not self.done:
            self.handle_events()
            self.draw()
            pygame.display.flip()
            self.clock.tick(30)
        self.client.close()
        pygame.quit()

    def handle_events(self) -> None:
        """Handles player input events, including mouse and keyboard events for controlling the camera,
        selecting troops and cities, and submitting paths to the server.
        """
        if not self.pause:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.done = True
                    self.player_input = "close"
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse_down(e)
                elif e.type == pygame.MOUSEBUTTONUP:
                    self.handle_mouse_up(e)
                elif e.type == pygame.MOUSEMOTION:
                    self.handle_mouse_motion(e)
                elif e.type == pygame.MOUSEWHEEL:
                    self.handle_mouse_wheel(e)
                elif e.type == pygame.KEYDOWN:
                    self.handle_key_down(e)
        else:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.done = True
                    self.player_input = "close"
                elif e.type == pygame.KEYDOWN:
                    self.handle_paused_key_down(e)

        self.client.send(orjson.dumps(self.player_input))
        self.player_input = [[], []]

    def handle_mouse_down(self, e: pygame.event.Event) -> None:
        """Handles mouse button down events for starting camera panning or selecting troops and cities.

        Args:
            e (pygame.event.Event): The mouse button down event
        """
        if e.button == 3 and not self.drawing_path and not self.drawing_city_path:
            self.panning = True
            self.pan_start_mouse = e.pos
            self.pan_start_cam = (self.camx, self.camy)
        elif e.button == 1:
            self.handle_left_click(e)

    def handle_left_click(self, e: pygame.event.Event) -> None:
        """Handles left mouse button clicks for selecting troops or cities.

        Args:
            e (pygame.event.Event): The left mouse button down event
        """
        mx, my = e.pos[0], e.pos[1]

        # Try to select a troop
        best = self.find_troop_at_click(mx, my)
        if best is not None:
            self.start_troop_path(best, mx, my)
        else:
            # Try to select a city
            best_city = self.find_city_at_click(mx, my)
            if best_city is not None:
                self.start_city_path(best_city, mx, my)

    def find_troop_at_click(self, mx: int, my: int) -> int:
        """Finds a troop at the given screen coordinates.

        Args:
            mx (int): The x-coordinate in screen space.
            my (int): The y-coordinate in screen space.
        Returns:
            int: The troop ID of the selected troop, or None if no troop is selected.
        """
        troops = self.draw_info[2]
        r = max(1, int(TROOP_R * self.zoom))
        r_s = r * 2
        best = None
        best_dist2 = None

        for pos, tid, owner, path, health, attacking in troops:
            if owner == self.player_num:
                sx = int((pos[0] - self.camx) * self.zoom)
                sy = int((pos[1] - self.camy) * self.zoom)
                dx = mx - sx
                dy = my - sy
                d2 = dx * dx + dy * dy
                if d2 <= r_s * r_s:
                    if best is None or d2 < best_dist2:
                        self.best_troop_pos = pos
                        best = tid
                        best_dist2 = d2
        return best

    def find_city_at_click(self, mx: int, my: int) -> int:
        """Finds a city at the given screen coordinates.
        Args:
            mx (int): The x-coordinate in screen space.
            my (int): The y-coordinate in screen space.
        Returns:
            int: The city ID of the selected city, or None if no city is selected.
        """
        cities = self.draw_info[3]
        r = max(1, int(CITY_R * self.zoom))
        r_s = r * 2
        best_city = None
        best_dist2 = None

        for pos, cid, path, owner in cities:
            if owner == self.player_num:
                sx = int((pos[0] - self.camx) * self.zoom)
                sy = int((pos[1] - self.camy) * self.zoom)
                dx = mx - sx
                dy = my - sy
                d2 = dx * dx + dy * dy
                if d2 <= r_s * r_s:
                    if best_city is None or d2 < best_dist2:
                        self.best_city_pos = pos
                        best_city = cid
                        best_dist2 = d2
        return best_city

    def start_troop_path(self, tid: int, mx: int, my: int) -> None:
        """Starts drawing a path for a troop.

        Args:
            tid (int): The troop ID to start drawing a path for.
            mx (int): The x-coordinate in screen space.
            my (int): The y-coordinate in screen space.
        """
        self.drawing_path = True
        self.remove_existing_troop_path(tid)
        self.paths.append((tid, [self.best_troop_pos]))

    def start_city_path(self, cid: int, mx: int, my: int) -> None:
        """Starts drawing a path for a city.

        Args:
            cid (int): The city ID to start drawing a path for.
            mx (int): The x-coordinate in screen space.
            my (int): The y-coordinate in screen space.
        """
        self.drawing_city_path = True
        self.remove_existing_city_path(cid)
        self.city_paths.append((cid, [self.best_city_pos]))

    def remove_existing_troop_path(self, tid: int) -> None:
        """Removes an existing path for a troop.

        Args:
            tid (int): The troop ID to remove the path for.
        """
        to_pop = None
        for i, id_path in enumerate(self.paths):
            if id_path[0] == tid:
                to_pop = i
        if to_pop is not None:
            self.paths.pop(to_pop)

    def remove_existing_city_path(self, cid: int) -> None:
        """Removes an existing path for a city.

        Args:
            cid (int): The city ID to remove the path for.
        """
        to_pop = None
        for i, id_path in enumerate(self.city_paths):
            if id_path[0] == cid:
                to_pop = i
        if to_pop is not None:
            self.city_paths.pop(to_pop)

    def handle_mouse_up(self, e: pygame.event.Event) -> None:
        """Handles mouse button up events for stopping camera panning or finishing path drawing.
        Args:
            e (pygame.event.Event): The mouse button up event
        """
        if e.button == 3:
            self.panning = False
        if e.button == 1:
            self.drawing_path = False
            self.drawing_city_path = False

    def handle_mouse_motion(self, e: pygame.event.Event) -> None:
        """Handles mouse motion events for drawing paths or panning the camera.
        Args:
            e (pygame.event.Event): The mouse motion event
        """
        if self.drawing_path:
            self.extend_troop_path(e.pos)
        elif self.drawing_city_path:
            self.extend_city_path(e.pos)
        elif self.panning:
            self.pan_camera(e.pos)

    def extend_troop_path(self, pos: tuple[int, int]) -> None:
        """Extends the path for a troop.

        Args:
            pos (tuple[int, int]): The position in screen space to extend the path to.
        """
        mx, my = pos
        wx = self.camx + mx / self.zoom
        wy = self.camy + my / self.zoom
        lx, ly = self.paths[-1][1][-1]
        dx = wx - lx
        dy = wy - ly
        if dx * dx + dy * dy > (PATH_SPACING / max(1.0, self.zoom)):
            self.paths[-1][1].append((wx, wy))

    def extend_city_path(self, pos: tuple[int, int]) -> None:
        """Extends the path for a city.

        Args:
            pos (tuple[int, int]): The position in screen space to extend the path to.
        """
        mx, my = pos
        wx = self.camx + mx / self.zoom
        wy = self.camy + my / self.zoom
        lx, ly = self.city_paths[-1][1][-1]
        dx = wx - lx
        dy = wy - ly
        if dx * dx + dy * dy > (PATH_SPACING / max(1.0, self.zoom)):
            self.city_paths[-1][1].append((wx, wy))

    def pan_camera(self, pos: tuple[int, int]) -> None:
        """Pans the camera to a new position.

        Args:
            pos (tuple[int, int]): The position in screen space to pan the camera to.
        """
        mx, my = pos
        sx, sy = self.pan_start_mouse
        dx = mx - sx
        dy = my - sy
        self.camx = self.pan_start_cam[0] - dx / self.zoom
        self.camy = self.pan_start_cam[1] - dy / self.zoom
        self.clamp_camera()

    def handle_mouse_wheel(self, e: pygame.event.Event) -> None:
        """Handles mouse wheel events for zooming in and out.

        Args:
            e (pygame.event.Event): The mouse wheel event
        """
        if not self.drawing_path and not self.drawing_city_path:
            mx, my = pygame.mouse.get_pos()
            if e.y > 0:
                self.zoom_in_at((mx, my))
            elif e.y < 0:
                self.zoom_out_at((mx, my))

    def handle_key_down(self, e: pygame.event.Event) -> None:
        """Handles key down events for various game actions.

        Args:
            e (pygame.event.Event): The key down event
        """
        if e.key == pygame.K_c:
            self.paths = []
            self.city_paths = []
        elif e.key == pygame.K_SPACE:
            self.submit_paths()
        elif e.key == pygame.K_p:
            self.player_input = "pause"
            self.pause = True

    def submit_paths(self) -> None:
        """Submits the currently drawn paths for troops and cities to the server, and resets the path drawing state."""
        if (not self.drawing_path and not self.drawing_city_path) and (
            self.paths or self.city_paths
        ):
            for id, path in self.paths:
                path.pop(0)
            for id, path in self.city_paths:
                path.pop(0)
            self.player_input[0] = self.paths
            self.player_input[1] = self.city_paths
            self.paths = []
            self.city_paths = []

    def handle_paused_key_down(self, e: pygame.event.Event) -> None:
        """Handles key down events when the game is paused.

        Args:
            e (pygame.event.Event): The paused key down event
        """
        if e.key == pygame.K_p:
            self.player_input = "unpause"
            self.pause = False

    def zoom_in_at(self, screen_pos: tuple[int, int]) -> None:
        """Zooms in at a specific screen position.

        Args:
            screen_pos (tuple[int, int]): The position in screen space to zoom in at.
        """
        if self.zoom_idx < len(self.zoom_levels) - 1:
            self.set_zoom_index(self.zoom_idx + 1, screen_pos)

    def zoom_out_at(self, screen_pos: tuple[int, int]) -> None:
        """Zooms out at a specific screen position.

        Args:
            screen_pos (tuple[int, int]): The position in screen space to zoom out at.
        """
        if self.zoom_idx > 0:
            self.set_zoom_index(self.zoom_idx - 1, screen_pos)

    def get_zoom(self, zoom_idx: int) -> float:
        """Returns the zoom level for a given zoom index.

        Args:
            zoom_idx (int): The zoom index to get the zoom level for.

        Returns:
            float: The zoom level for the given zoom index.
        """
        return self.zoom_levels[zoom_idx] * self.factor

    def set_zoom_index(self, new_idx: int, screen_pos: tuple[int, int]) -> None:
        """Sets the zoom index to a new value, adjusting the camera position accordingly.

        Args:
            new_idx (int): The new zoom index.
            screen_pos (tuple[int, int]): The position in screen space to maintain the same world position.
        """
        old_zoom = self.zoom
        new_zoom = self.get_zoom(new_idx)
        sx, sy = screen_pos

        world_x = self.camx + sx / old_zoom
        world_y = self.camy + sy / old_zoom

        self.zoom_idx = new_idx
        self.zoom = new_zoom
        self.camx = world_x - sx / new_zoom
        self.camy = world_y - sy / new_zoom
        self.clamp_camera()

    def clamp_camera(self) -> None:
        """Clamps the camera position to the world boundaries."""
        max_camx = max(0.0, self.world_info.world_x - (self.size[0] / self.zoom))
        max_camy = max(0.0, self.world_info.world_y - (self.size[1] / self.zoom))
        if self.camx < 0.0:
            self.camx = 0.0
        if self.camy < 0.0:
            self.camy = 0.0
        if self.camx > max_camx:
            self.camx = max_camx
        if self.camy > max_camy:
            self.camy = max_camy

    def draw(self) -> None:
        """Draws the game world, including the terrain, cities, troops, vision, and borders,
        as well as any paths being drawn by the player and pause text if the game is paused.
        """
        self.screen.fill((255, 255, 255))
        self.update_draw_info()
        vision_grid, border_grid, troops, cities = self.draw_info
        vision_grid = np.array(vision_grid)
        border_grid = np.array(border_grid)
        z = self.zoom

        terrain_surf = self.terrain_by_zoom[z]
        offset_x = int(-self.camx * z)
        offset_y = int(-self.camy * z)
        self.screen.blit(terrain_surf, (offset_x, offset_y))

        dynamic = self.create_dynamic_surface(z)
        fog = self.create_fog_surface(z)

        self.city_paths_to_draw = []
        self.troop_paths_to_draw = []

        self.draw_cities(cities, dynamic, z)
        self.draw_city_paths(dynamic, z)
        self.draw_troops(troops, dynamic, z)
        self.draw_troop_paths(dynamic, z)

        self.draw_border(border_grid, fog, z)
        self.draw_vision(vision_grid, fog, z)

        if self.pause:
            self.draw_pause_text(fog)

        self.screen.blit(dynamic, (offset_x, offset_y))
        self.screen.blit(fog, (offset_x, offset_y))

    def update_draw_info(self) -> None:
        """Updates the draw_info attribute with data received from the client."""
        try:
            self.draw_info = orjson.loads(self.client.rcv())
        except Exception as e:
            print(f"error loading draw info: {e}")

    def create_dynamic_surface(self, z: float) -> pygame.Surface:
        """Creates a dynamic surface for drawing game elements scaled by zoom level.

        Args:
            z (float): The zoom level.

        Returns:
            pygame.Surface: The dynamic surface for drawing game elements at the given zoom level.
        """
        dyn_w = max(1, int(self.world_info.world_x * z))
        dyn_h = max(1, int(self.world_info.world_y * z))
        return pygame.Surface((dyn_w, dyn_h), pygame.SRCALPHA)

    def create_fog_surface(self, z: float) -> pygame.Surface:
        """Creates a fog surface for drawing fog of war effects scaled by zoom level.

        Args:
            z (float): The zoom level.

        Returns:
            pygame.Surface: The fog surface for drawing fog of war effects at the given zoom level.
        """
        dyn_w = max(1, int(self.world_info.world_x * z))
        dyn_h = max(1, int(self.world_info.world_y * z))
        return pygame.Surface((dyn_w, dyn_h), pygame.SRCALPHA)

    def draw_cities(self, cities: list, dynamic: pygame.Surface, z: float) -> None:
        """Draws cities on the dynamic surface.

        Args:
            cities (list): List of city data (position, cid, path, owner).
            dynamic (pygame.Surface): The dynamic surface to draw on.
            z (float): The zoom level.
        """
        for position, cid, path, owner in cities:
            if path and owner == self.player_num:
                path.insert(0, position)
                self.city_paths_to_draw.append(path)
            if owner >= 0:
                self.draw_city(COLORS[owner], position, dynamic, z)

    def draw_city(
        self, color: tuple, position: tuple, dynamic: pygame.Surface, z: float
    ) -> None:
        """Draws a city on the dynamic surface.

        Args:
            color (tuple): The color of the city.
            position (tuple): The position of the city.
            dynamic (pygame.Surface): The dynamic surface to draw on.
            z (float): The zoom level.
        """
        px = int(position[0] * z)
        py = int(position[1] * z)

        pole_bottom = (px, py)
        pole_top = (px, int(py - 30 * z))
        pygame.draw.line(
            dynamic, (80, 80, 80), pole_bottom, pole_top, max(1, int(3 * z))
        )

        flag_color = tuple(color) if isinstance(color, (list, tuple)) else color
        fw, fh = int(20 * z), int(TROOP_D * z)
        p1 = (pole_top[0], pole_top[1])
        p2 = (pole_top[0] + fw, pole_top[1] + fh // 2)
        p3 = (pole_top[0], pole_top[1] + fh)
        pygame.draw.polygon(dynamic, flag_color, [p1, p2, p3])
        pygame.draw.polygon(dynamic, (0, 0, 0), [p1, p2, p3], max(1, int(1 * z)))

    def draw_troops(self, troops: list, dynamic: pygame.Surface, z: float) -> None:
        """Draws troops on the dynamic surface.

        Args:
            troops (list): List of troop data (position, tid, owner, path, health).
            dynamic (pygame.Surface): The dynamic surface to draw on.
            z (float): The zoom level.
        """
        tids = [tid for tid, path in self.paths]
        for pos, tid, owner, path, health, attacking in troops:
            off_x, off_y = (0, 0)
            if attacking:
                off_x, off_y = dir_dis_to_xy(random.randrange(0, 360, 5), 1)
            px = int((pos[0] + off_x) * z)
            py = int((pos[1] + off_y) * z)
            r = max(1, int(TROOP_R * z))
            color = COLORS[owner]
            rgb = color

            if tid in tids:
                factor = 0.5
                rgb = [max(0, min(255, int(x * factor))) for x in color]
            if path and owner == self.player_num:
                path.insert(0, pos)
                self.troop_paths_to_draw.append(path)
            pygame.draw.rect(
                dynamic,
                (0, 255, 0),
                pygame.rect.Rect(
                    px - r,
                    (py - r) - max(1, int(3 * z)),
                    (r * 2) * (health / TROOP_HEALTH),
                    max(1, int(3 * z)),
                ),
            )
            pygame.draw.circle(dynamic, rgb, (px, py), r)

    def draw_city_paths(self, dynamic: pygame.Surface, z: float) -> None:
        """Draws city paths on the dynamic surface.

        Args:
            dynamic (pygame.Surface): The dynamic surface to draw on.
            z (float): The zoom level.
        """
        for path in self.city_paths_to_draw:
            for i, pos in enumerate(path):
                if not i == (len(path) - 1):
                    px = int(pos[0] * z)
                    py = int(pos[1] * z)
                    px2 = int(path[i + 1][0] * z)
                    py2 = int(path[i + 1][1] * z)
                    pygame.draw.line(
                        dynamic, (240, 180, 0), (px, py), (px2, py2), max(1, int(4 * z))
                    )
        for tid, path in self.city_paths:
            for i, pos in enumerate(path):
                if not i == (len(path) - 1):
                    px = int(pos[0] * z)
                    py = int(pos[1] * z)
                    px2 = int(path[i + 1][0] * z)
                    py2 = int(path[i + 1][1] * z)
                    pygame.draw.line(
                        dynamic, (0, 0, 0), (px, py), (px2, py2), max(1, int(2 * z))
                    )

    def draw_troop_paths(self, dynamic: pygame.Surface, z: float) -> None:
        """Draws troop paths on the dynamic surface.

        Args:
            dynamic (pygame.Surface): The dynamic surface to draw on.
            z (float): The zoom level.
        """
        for path in self.troop_paths_to_draw:
            for i, pos in enumerate(path):
                if not i == (len(path) - 1):
                    px = int(pos[0] * z)
                    py = int(pos[1] * z)
                    px2 = int(path[i + 1][0] * z)
                    py2 = int(path[i + 1][1] * z)
                    pygame.draw.line(
                        dynamic, self.color, (px, py), (px2, py2), max(1, int(2 * z))
                    )

        for tid, path in self.paths:
            for i, pos in enumerate(path):
                if not i == (len(path) - 1):
                    px = int(pos[0] * z)
                    py = int(pos[1] * z)
                    px2 = int(path[i + 1][0] * z)
                    py2 = int(path[i + 1][1] * z)
                    pygame.draw.line(
                        dynamic, (0, 0, 0), (px, py), (px2, py2), max(1, int(2 * z))
                    )

    def draw_border(
        self, border_grid: np.ndarray, fog: pygame.Surface, z: float
    ) -> None:
        """Draws the border on the fog surface.

        Args:
            border_grid (np.ndarray): The border grid data.
            fog (pygame.Surface): The fog surface to draw on.
            z (float): The zoom level.
        """
        for a, b in marching_squares(
            border_grid,
            CELL_SIZE,
            self.world_info.rows,
            self.world_info.cols,
            THRESHOLD,
        ):
            ax = int(a[0] * z)
            ay = int(a[1] * z)
            bx = int(b[0] * z)
            by = int(b[1] * z)
            pygame.draw.line(fog, (0, 0, 0), (ax, ay), (bx, by), max(1, int(3 * z)))

    def draw_vision(
        self, vision_grid: np.ndarray, fog: pygame.Surface, z: float
    ) -> None:
        """Draws the vision grid on the fog surface.

        Args:
            vision_grid (np.ndarray): The vision grid data.
            fog (pygame.Surface): The fog surface to draw on.
            z (float): The zoom level.
        """
        for poly in marching_squares_poly(
            vision_grid,
            CELL_SIZE,
            self.world_info.rows,
            self.world_info.cols,
            THRESHOLD,
        ):
            scaled = [(int(x * z), int(y * z)) for x, y in poly]
            pygame.draw.polygon(fog, (0, 0, 0, 150), scaled, 0)

    def draw_pause_text(self, fog: pygame.Surface) -> None:
        """Draws the pause text on the fog surface.

        Args:
            fog (pygame.Surface): The fog surface to draw on.
        """
        text_surface = self.font.render("Pause", False, (0, 0, 0))
        fog.blit(text_surface, (10, 10))


if __name__ == "__main__":
    while True:
        try:
            game_play = Game("WAR OF DOTS")
            game_play.run_game()
        except Exception as e:
            print(f"an error occurred: {e}")
            pygame.quit()
        input("game over, press enter to continue")
