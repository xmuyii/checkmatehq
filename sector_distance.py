import math
from datetime import datetime, timedelta, timezone

GRID_SIZE = 8  # 8x8 grid = 64 sectors

def sector_to_coords(sector_id: int) -> tuple[int, int]:
    """
    Maps sector_id (1 to 64) to (x, y) grid coordinates.
    Sector 1 is (0,0).
    """
    idx = sector_id - 1
    x = idx % GRID_SIZE
    y = idx // GRID_SIZE
    return x, y

def calculate_distance(from_sector: int, to_sector: int) -> float:
    """Calculates Euclidean distance between two sectors."""
    x1, y1 = sector_to_coords(from_sector)
    x2, y2 = sector_to_coords(to_sector)
    return math.hypot(x2 - x1, y2 - y1)

def calculate_travel_time(from_sector: int, to_sector: int, speed_per_unit: int = 45) -> int:
    """
    Calculates travel time in seconds for normal travel.
    Default: 45 seconds per grid distance unit.
    """
    if from_sector == to_sector:
        return 0
    dist = calculate_distance(from_sector, to_sector)
    return max(15, int(dist * speed_per_unit)) # Minimum 15s walk