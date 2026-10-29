# Floodsafe — single-map evacuation studio

This revision replaces the multi-map Streamlit interface with a Flask app and one persistent Leaflet map. Run it with Python, not `streamlit run`.

## Start on Windows

Install Python 3.11 or newer. Extract this ZIP, open `floodsafe-package`, and double-click `START_WINDOWS.bat`. The launcher creates a local environment, installs requirements, starts the app, and opens http://127.0.0.1:8502. Keep the terminal open. Close it to stop the app.

Or, from the extracted folder:

```
python -m pip install -r Prototype/requirements.txt
python Prototype/app.py
```

Press **Try Udaipur example · real roads** for an immediate playback using the bundled real road snapshot, two demo shelters, a test flood zone, and explicitly assumed population. All inputs remain editable.

## One-map workflow

1. Pan or zoom around Udaipur. Press **Use the centre of this map as my area**, or **Area** and drag a rectangle. Real H3 cells appear, clipped to your boundary.
2. Press **Shelter** and click locations on the map. Click each numbered marker to change capacity or remove it. Drag markers to relocate shelters.
3. Press **Flood**, click polygon corners, and click the first point to finish. Click a flood polygon to change its depth. You can add multiple zones, edit their shapes with the map pencil tool, or remove them.
4. Press **Calculate & play routes**. The server downloads real OpenStreetMap drivable roads, applies your flood conditions, and assigns each hexagon's population to reachable shelter capacity. Groups move along the resulting roads on the same map.
5. Pause, replay, or scrub the timeline. Click a hexagon to highlight its routes and inspect destinations and unassigned demand. Click **Show all routes** to restore every route.
6. Change a shelter or flood zone, then calculate again. The old playback stops immediately, so it cannot be mistaken for the updated scenario. A new run restarts all demand at its hexagon origins and reports changed route assignments; it does not preserve in-transit people.
7. Save/load scenarios as JSON or export allocations to CSV.

## Data and modelling assumptions

- Roads: real OpenStreetMap drive network, respecting road directions. The graph includes a 1.2 km buffer so a route can leave the selected population boundary. The default Udaipur area includes an attributed real OSM road snapshot captured on 2026-10-29 (2,521 nodes, 6,424 directed edges). Other areas require an internet download and are cached for subsequent runs. The snapshot metadata is in Prototype/data/udaipur.json. Basemap tiles still require internet.
- Population: initially calculated from an explicitly labelled density assumption. Click each hexagon to enter your own count. These are not live WorldPop or census counts. The earlier population_estimator.py is retained as reference, but remote population queries do not block this UI.
- Shelters: user-placed scenario locations and capacities, not verified relief sites. Shelters inside flood zones at/above closure depth are disabled.
- Routes: shortest weighted travel time for each origin/shelter pair, with higher-demand hexagons allocated first. Demand may be split across shelters. This greedy allocation is not a globally optimal flow solution.
- Floods: user-defined polygons and depths. Intersecting road edges close at the threshold; shallower depths add travel cost. These are not hydraulic flood predictions.
- Access: cell interior points and shelters snap to mapped nodes within 300 m. Dashed access connectors are illustrative, not verified access paths. More distant origins remain unassigned.
- Playback: each dot represents an allocated group, moving along the full road geometry. Departures are staggered by your chosen interval. The full schedule plays in about 45 seconds at 1×. The displayed clock is simulated time. Traffic, vehicles, congestion, queues, and road throughput are not simulated.
- Road fetching failure is reported explicitly. The app never substitutes a synthetic road network.

## Put it on Mayank

Copy the new `Prototype` folder, `START_WINDOWS.bat`, and this README into your local Flood-Management checkout on branch Mayank. Commit those files and push Mayank. Do not upload `.venv`, caches, or the ZIP. The Siya branch does not need changes.

This Python server needs a Python hosting environment when published; the existing static Vercel overview can link to it separately.

## Validation

The included unit tests cover tiny-area H3 selection, capacity conservation, routing around closed edges, exclusion of flooded shelters, full road geometry, and unreachable demand. Run from the package root:

```
cd Prototype
python -m unittest discover -s tests
```

Browser checks also exercise area selection, shelter placement, drawing a flood zone, calculation, animation, pause, and recalculation. The synthetic road fixture used in unit tests is never used by the delivered app.

## Place search and workflow guards

Enter a city, village, or mapped place in **Find a place** and press Enter or Search. Choose one of the results. Searching alone preserves the current scenario. Selecting a result or using a location preset asks for confirmation when an area, shelters, floods, or routes exist. Accepting clears every map layer, selection, schedule, playback, and prior result before moving. Cancel keeps the current scenario. Pending search responses are discarded after a reset or changed query.

Area selection is available immediately. Shelters and flood zones require a successfully generated grid. Route calculation requires positive population and at least one shelter with available capacity. Flood zones are optional, allowing a dry baseline. Export, save, and clear controls are enabled only when relevant data exists. Replacing an area with dependent shelters/floods or loading another scenario also asks before clearing it.

Search uses Photon with OpenStreetMap data, with an Open-Meteo/GeoNames city lookup fallback when Photon is unavailable. Internet access is required. Requests are explicit, cached and throttled; there is no keystroke autocomplete. Empty/long queries, no matches, invalid service responses, rate limits and timeouts have visible messages. A search failure preserves the scenario and map. The primary endpoint can be configured through `FLOODSAFE_GEOCODER_URL` for a compatible Photon instance. This setup is for a small noncommercial prototype; review provider terms before deploying publicly at scale.

Provider information: https://github.com/komoot/photon and https://open-meteo.com/en/docs/geocoding-api. Search availability and coverage depend on the providers. Coordinates outside the web map's supported latitude range are rejected.

Validation for this revision: 14 backend tests plus browser checks for the area/shelter/flood/route workflow, search result selection, cancellation, complete location reset, failed search, and prerequisites. Live search providers timed out in the development environment; success and error parsing were verified with controlled provider responses. Real Udaipur road routing remains verified with the bundled OSM snapshot.

## India search and bottom-panel update

Search now sits at the bottom of the map, above the timeline when playback is visible. Its button has a fixed minimum width and results are scrollable. Search results are restricted to records explicitly marked as India; the city fallback also uses countryCode=IN. Unknown-country and international records are excluded.

“Techno NJR”, “Techno India NJR” and “TINJR” resolve locally to a verified named campus access road at 24.5179096, 73.7518783. This is a campus navigation point, not a surveyed boundary. Source: https://www.openstreetmap.org/way/1205398059. College identity/location reference: https://www.technonjr.org/about/campus-at-glance/.

The package does not use Google Places. Google's actual suggestions require your Google Maps Platform API key with Places API enabled and billing configured. Google's policy requires Places results displayed on a map to use a Google map, so activating that also requires migrating the current Leaflet/OpenStreetMap interface. No Google key has been supplied and no Google billing or service has been activated. Policies: https://developers.google.com/maps/documentation/places/web-service/policies and https://developers.google.com/maps/documentation/places/web-service/usage-and-billing/.
