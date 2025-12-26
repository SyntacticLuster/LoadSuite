from pathlib import Path


def _read_app_js() -> str:
    return Path("static/app.js").read_text(encoding="utf-8")


def test_routecast_updates_do_not_force_full_render() -> None:
    js = _read_app_js()
    assert "updateRouteCastPanels" in js
    assert "if (!updateRouteCastPanels(id" in js


def test_map_rebuild_guard_present() -> None:
    js = _read_app_js()
    assert "shouldRebuildMapInstance" in js
    assert "container_detached" in js


def test_map_routed_geometry_fetch_present() -> None:
    js = _read_app_js()
    assert "/api/routes" in js
    assert "setLatLngs" in js


def test_map_uses_routed_geometry_when_available() -> None:
    js = _read_app_js()
    assert "fetchRouteGeometry" in js
    assert "normalizeRouteGeometry" in js
    assert "activePolyline" in js


def test_mini_route_preview_component_present() -> None:
    js = _read_app_js()
    assert "renderMiniRoutePreview" in js
    assert "buildMiniRouteSvg" in js
    assert "mini-route-preview" in js


def test_mini_route_preview_lazy_loads() -> None:
    js = _read_app_js()
    assert "IntersectionObserver" in js
    assert "observeMiniRoutePreview" in js


def test_mini_route_preview_fallback_present() -> None:
    js = _read_app_js()
    assert "Route unavailable" in js
    assert "stroke-dasharray" in js
