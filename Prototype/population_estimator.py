
import math
import random

from shapely.geometry import Point


def approximate_area_km2(geometry):
    """
    Approximate geometry area in km² using a local
    latitude-adjusted conversion from degrees.

    Suitable for a small demo area, not authoritative
    area calculations for large regions.
    """
    if geometry.is_empty:
        return 0.0

    latitude = geometry.centroid.y

    km_per_degree_lat = 111.32
    km_per_degree_lon = (
        111.32 * max(math.cos(math.radians(latitude)), 0.2)
    )

    area_km2 = (
        geometry.area
        * km_per_degree_lat
        * km_per_degree_lon
    )

    return max(0.0, area_km2)


def random_point_in_geometry(geometry, rng, max_attempts=500):
    """
    Generate a representative point inside the geometry.
    Handles polygons and multipolygons.
    """
    min_x, min_y, max_x, max_y = geometry.bounds

    for _ in range(max_attempts):
        point = Point(
            rng.uniform(min_x, max_x),
            rng.uniform(min_y, max_y),
        )

        if geometry.covers(point):
            return point

    # Guaranteed interior fallback for a nonempty geometry.
    return geometry.representative_point()


def estimate_population(
    geometry,
    density_per_km2,
    dot_scale=10,
    seed=42,
    max_dots_per_cell=300,
):
    """
    Estimate population independently of the user interface.

    Parameters
    ----------
    geometry:
        Shapely polygon or multipolygon for a clipped H3 cell.
    density_per_km2:
        Configurable demo population density.
    dot_scale:
        Approximate residents represented by one displayed dot.
    seed:
        Deterministic random seed for reproducible demos.
    max_dots_per_cell:
        Rendering safeguard for large population estimates.

    Returns
    -------
    Dictionary containing approximate area, estimated population,
    and representative (latitude, longitude) dot coordinates.
    """
    if density_per_km2 < 0:
        raise ValueError("Population density cannot be negative.")

    if dot_scale < 1:
        raise ValueError("dot_scale must be at least 1.")

    if geometry.is_empty:
        return {
            "area_km2": 0.0,
            "population": 0,
            "dots": [],
        }

    area_km2 = approximate_area_km2(geometry)

    population = max(
        0,
        round(area_km2 * density_per_km2),
    )

    # Keep the dot layer manageable during a classroom demo.
    number_of_dots = min(
        max_dots_per_cell,
        math.ceil(population / dot_scale),
    )

    rng = random.Random(seed)

    dots = []

    for _ in range(number_of_dots):
        point = random_point_in_geometry(geometry, rng)

        # App expects (latitude, longitude).
        dots.append((point.y, point.x))

    return {
        "area_km2": area_km2,
        "population": population,
        "dots": dots,
    }


def estimate_population_from_count(geometry, population, dot_scale=10, seed=42,
                                  max_dots_per_cell=300):
    """Generate synthetic map dots for a population count from WorldPop."""
    if dot_scale < 1:
        raise ValueError("dot_scale must be at least 1.")
    if geometry.is_empty:
        return {"area_km2": 0.0, "population": 0, "dots": []}
    area_km2 = approximate_area_km2(geometry)
    population = max(0, int(round(float(population))))
    number_of_dots = min(max_dots_per_cell, math.ceil(population / dot_scale))
    rng = random.Random(seed)
    dots = []
    for _ in range(number_of_dots):
        point = random_point_in_geometry(geometry, rng)
        dots.append((point.y, point.x))
    return {"area_km2": area_km2, "population": population, "dots": dots}


def fetch_worldpop_population(geojson_geometry, year=2020, resolution="100m",
                              timeout_seconds=120):
    """
    Query WorldPop Global2 API for population in a WGS84 GeoJSON polygon.
    Returns a modeled estimate, not a live headcount.
    """
    import time
    import requests

    api_url = "https://api.worldpop.org/v2"
    response = requests.post(
        f"{api_url}/population",
        json={"geojson": geojson_geometry, "year": int(year),
              "resolution": resolution},
        timeout=30,
    )
    response.raise_for_status()
    submitted = response.json()
    task_id = submitted.get("task_id") or submitted.get("taskid")

    if not task_id:
        result = submitted.get("result", submitted.get("data", {}))
        total = result.get("total_population") if isinstance(result, dict) else None
        if total is not None:
            return max(0, int(round(float(total))))
        raise RuntimeError(f"WorldPop did not return a task ID: {submitted}")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = requests.get(f"{api_url}/tasks/{task_id}", timeout=30)
        response.raise_for_status()
        task = response.json()
        status = str(task.get("status", "")).lower()

        if status in {"success", "finished", "completed"}:
            result = task.get("result", task.get("data", {}))
            total = result.get("total_population") if isinstance(result, dict) else None
            if total is None:
                raise RuntimeError(f"WorldPop result has no population total: {task}")
            return max(0, int(round(float(total))))

        if status in {"failure", "failed", "error"} or task.get("error") is True:
            raise RuntimeError(
                task.get("error_message") or task.get("error")
                or f"WorldPop task failed: {task}"
            )
        time.sleep(2)

    raise TimeoutError(f"WorldPop timed out after {timeout_seconds} seconds.")

