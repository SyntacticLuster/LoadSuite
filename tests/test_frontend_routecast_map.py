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
