# RouteCast Architecture (Scaffold)

Dataflow (stubbed for now):

1. **Route**: API receives a `RouteRequest` and asks a routing provider (OSRM/Valhalla stub) for a `RouteResponse` containing a polyline and legs.
2. **Corridor**: The polyline is buffered into a corridor polygon (placeholder ring) to bound overlay queries.
3. **Fetch overlays**: Sources (NWS alerts, OSM restrictions, Open511 events) return overlays that intersect the corridor (currently empty stubs).
4. **Score**: A scoring stub computes a deterministic `ScoreBreakdown` from the route and overlays.
5. **UI render**: The API returns route, overlays, and score for the UI to visualize the path, risks, and summary.
