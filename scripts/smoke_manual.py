#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


def _truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: bytes
    content_type: str | None


def _http(
    *,
    method: str,
    base_url: str,
    path: str,
    query: dict[str, str] | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    api_key: str | None = None,
    include_key: bool = False,
    timeout_s: float = 15.0,
) -> HttpResult:
    base_url = base_url.rstrip("/") + "/"
    url = urljoin(base_url, path.lstrip("/"))
    if query:
        url = url + ("?" + urlencode(query))

    headers: dict[str, str] = {
        "User-Agent": "LoadSuiteSmokeManual/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type

    if include_key and api_key:
        # Server accepts either Bearer or X-API-Key. Bearer is more standard.
        headers["Authorization"] = f"Bearer {api_key}"

    req = Request(url=url, data=body, method=method.upper(), headers=headers)

    try:
        with urlopen(req, timeout=timeout_s) as resp:
            resp_body = resp.read() or b""
            return HttpResult(
                status=int(getattr(resp, "status", 0) or 0),
                body=resp_body,
                content_type=resp.headers.get("content-type"),
            )
    except HTTPError as e:
        # HTTPError is also a file-like response.
        try:
            data = e.read() or b""
        except Exception:
            data = b""
        return HttpResult(
            status=int(getattr(e, "code", 0) or 0),
            body=data,
            content_type=getattr(e, "headers", {}).get("content-type") if getattr(e, "headers", None) else None,
        )


def _json_loads_for_import() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    pickup_start = now + timedelta(hours=1)
    pickup_end = pickup_start + timedelta(hours=2)
    delivery_start = pickup_end + timedelta(hours=18)
    delivery_end = delivery_start + timedelta(hours=3)

    def mk(load_id: str, origin_city: str, origin_state: str, dest_city: str, dest_state: str, miles: float, rate: float) -> dict[str, Any]:
        rpm = round(rate / max(miles, 1.0), 4)
        return {
            "id": load_id,
            "origin": {"city": origin_city, "state": origin_state},
            "destination": {"city": dest_city, "state": dest_state},
            "pickup_start": pickup_start.isoformat(),
            "pickup_end": pickup_end.isoformat(),
            "delivery_start": delivery_start.isoformat(),
            "delivery_end": delivery_end.isoformat(),
            "equipment": "Dry Van",
            "weight_lbs": 42000,
            "hazmat": False,
            "distance_miles": miles,
            "deadhead_miles": 25.0,
            "rate_total_usd": rate,
            "rpm": rpm,
            "broker": {"name": "SmokeBroker", "rating": 4.0},
            "detention": False,
            "multi_stop": False,
            "lane_history": False,
            "commodity": "General",
            "posted_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    return [
        mk("SMOKE-1", "Chicago", "IL", "Dallas", "TX", miles=925.0, rate=2550.0),
        mk("SMOKE-2", "Atlanta", "GA", "Charlotte", "NC", miles=245.0, rate=725.0),
    ]


def _csv_payload_for_import() -> bytes:
    now = datetime.now(timezone.utc)
    pickup_start = now + timedelta(hours=2)
    pickup_end = pickup_start + timedelta(hours=2)
    delivery_start = pickup_end + timedelta(hours=10)
    delivery_end = delivery_start + timedelta(hours=2)

    # Must satisfy required columns in app.data.loads_from_csv_bytes
    headers = [
        "id",
        "origin_city",
        "origin_state",
        "destination_city",
        "destination_state",
        "pickup_start",
        "pickup_end",
        "delivery_start",
        "delivery_end",
        "equipment",
        "weight_lbs",
        "distance_miles",
        "deadhead_miles",
        "rate_total_usd",
        "rpm",
        "posted_at",
        "updated_at",
        # optional:
        "hazmat",
        "broker_name",
        "broker_rating",
        "detention",
        "multi_stop",
        "lane_history",
        "commodity",
    ]

    def row(
        load_id: str,
        o_city: str,
        o_state: str,
        d_city: str,
        d_state: str,
        miles: float,
        rate: float,
    ) -> list[str]:
        rpm = rate / max(miles, 1.0)
        return [
            load_id,
            o_city,
            o_state,
            d_city,
            d_state,
            pickup_start.isoformat(),
            pickup_end.isoformat(),
            delivery_start.isoformat(),
            delivery_end.isoformat(),
            "Dry Van",
            "38000",
            f"{miles}",
            "15",
            f"{rate}",
            f"{rpm}",
            now.isoformat(),
            now.isoformat(),
            "false",
            "SmokeBroker",
            "4.0",
            "false",
            "false",
            "false",
            "General",
        ]

    def csv_escape(value: str) -> str:
        if any(c in value for c in [",", "\"", "\n", "\r"]):
            return '"' + value.replace('"', '""') + '"'
        return value

    lines: list[str] = []
    lines.append(",".join(headers))
    for r in [
        row("SMOKE-C1", "Houston", "TX", "Austin", "TX", miles=165.0, rate=500.0),
        row("SMOKE-C2", "Seattle", "WA", "Portland", "OR", miles=175.0, rate=525.0),
    ]:
        lines.append(",".join(csv_escape(v) for v in r))

    return ("\n".join(lines) + "\n").encode("utf-8")


def _parse_json_maybe(data: bytes) -> Any:
    try:
        return json.loads((data or b"").decode("utf-8"))
    except Exception:
        return None


def _looks_like_loads_list(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    loads = payload.get("loads")
    if not isinstance(loads, list):
        return False
    return True


def _looks_like_scored_loads(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    loads = payload.get("loads")
    if not isinstance(loads, list):
        return False
    if not loads:
        return True
    first = loads[0]
    if not isinstance(first, dict):
        return False
    # app.api_models.ScoredLoadModel structure includes score + load
    return ("score" in first) and ("load" in first)


class Reporter:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def pass_(self, label: str, detail: str = "") -> None:
        if detail:
            print(f"PASS: {label} — {detail}")
        else:
            print(f"PASS: {label}")

    def fail(self, label: str, detail: str = "") -> None:
        self.failures.append(label)
        if detail:
            print(f"FAIL: {label} — {detail}")
        else:
            print(f"FAIL: {label}")

    def note(self, label: str, detail: str = "") -> None:
        if detail:
            print(f"NOTE: {label} — {detail}")
        else:
            print(f"NOTE: {label}")


def _expect_status(
    r: Reporter,
    *,
    label: str,
    result: HttpResult,
    expected: Iterable[int],
    extra_ok: str | None = None,
) -> bool:
    if result.status in set(expected):
        r.pass_(label, f"HTTP {result.status}" + (f" ({extra_ok})" if extra_ok else ""))
        return True
    body_preview = (result.body or b"")[:300].decode("utf-8", errors="replace")
    r.fail(label, f"expected {sorted(set(expected))}, got HTTP {result.status}; body={body_preview!r}")
    return False


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Manual smoke checks against a running LoadSuite server")
    p.add_argument("--base-url", default="http://localhost:8000", help="Server base URL")
    p.add_argument("--key", default=None, help="Admin API key (also reads ADMIN_API_KEY env var)")
    p.add_argument("--auth", action="store_true", help="Force auth boundary checks")
    p.add_argument("--skip-import", action="store_true", help="Skip import steps")
    p.add_argument("--skip-ingestion", action="store_true", help="Skip ingestion run step")

    args = p.parse_args(argv)

    # Prefer explicit CLI key; fall back to ADMIN_API_KEY env var.
    api_key = args.key
    if api_key is None:
        import os

        api_key = (os.environ.get("ADMIN_API_KEY") or "").strip() or None

    do_auth_checks = bool(args.auth)
    if not do_auth_checks:
        import os

        do_auth_checks = _truthy_env(os.environ.get("AUTH_ENABLED"))

    r = Reporter()

    # Basic health must always be reachable (auth is not applied here).
    try:
        res = _http(method="GET", base_url=args.base_url, path="/api/health")
    except URLError as e:
        r.fail("GET /api/health", f"connection failed: {e}")
        return 2

    _expect_status(r, label="GET /api/health", result=res, expected=[200])

    protected = [
        ("POST", "/api/import", {"filename": "smoke.json"}),
        ("POST", "/api/ingestion/run", None),
        ("GET", "/api/ingestion/sources", None),
    ]

    public = [
        ("GET", "/api/loads", None),
        ("GET", "/api/loads/scored", None),
        ("GET", "/api/health", None),
    ]

    if do_auth_checks:
        # 1) Protected endpoints must reject anonymous.
        for method, path, query in protected:
            body = None
            ctype = None
            if path == "/api/import":
                body = json.dumps(_json_loads_for_import()).encode("utf-8")
                ctype = "application/json"
            res = _http(method=method, base_url=args.base_url, path=path, query=query or None, body=body, content_type=ctype)
            _expect_status(r, label=f"Auth required: {method} {path} (no key)", result=res, expected=[401])

        # 2) Public endpoints should remain accessible without key.
        for method, path, query in public:
            res = _http(method=method, base_url=args.base_url, path=path, query=query or None)
            _expect_status(r, label=f"Public: {method} {path} (no key)", result=res, expected=[200])

        # 3) With key, protected endpoints must succeed.
        if not api_key:
            r.fail("Auth-enabled mode requires a key", "provide --key or set ADMIN_API_KEY")
        else:
            # Connector sources
            res = _http(method="GET", base_url=args.base_url, path="/api/ingestion/sources", api_key=api_key, include_key=True)
            _expect_status(r, label="Auth ok: GET /api/ingestion/sources (with key)", result=res, expected=[200])

            if not args.skip_import:
                # JSON import
                json_body = json.dumps(_json_loads_for_import()).encode("utf-8")
                res = _http(
                    method="POST",
                    base_url=args.base_url,
                    path="/api/import",
                    query={"filename": "smoke.json"},
                    body=json_body,
                    content_type="application/json",
                    api_key=api_key,
                    include_key=True,
                )
                ok = _expect_status(r, label="Auth ok: POST /api/import?filename=smoke.json", result=res, expected=[200])
                if ok:
                    payload = _parse_json_maybe(res.body)
                    if isinstance(payload, dict) and payload.get("count") in (2, "2"):
                        r.pass_("JSON import count", "count=2")
                    elif isinstance(payload, dict) and payload.get("ok") is True:
                        r.pass_("JSON import response shape", "ok=true")
                    else:
                        r.fail("JSON import response shape", f"unexpected payload: {payload!r}")

                # CSV import
                csv_body = _csv_payload_for_import()
                res = _http(
                    method="POST",
                    base_url=args.base_url,
                    path="/api/import",
                    query={"filename": "smoke.csv"},
                    body=csv_body,
                    content_type="text/csv",
                    api_key=api_key,
                    include_key=True,
                )
                _expect_status(r, label="Auth ok: POST /api/import?filename=smoke.csv", result=res, expected=[200])
            else:
                r.note("Import", "skipped (--skip-import)")

            if not args.skip_ingestion:
                res = _http(
                    method="POST",
                    base_url=args.base_url,
                    path="/api/ingestion/run",
                    api_key=api_key,
                    include_key=True,
                )
                if res.status == 409:
                    r.note("POST /api/ingestion/run", "ingestion not enabled (HTTP 409)")
                else:
                    _expect_status(r, label="Auth ok: POST /api/ingestion/run", result=res, expected=[200])
            else:
                r.note("Ingestion run", "skipped (--skip-ingestion)")

    else:
        # Not in auth-check mode: do the normal smoke path (works with auth disabled, or with a key).
        if not args.skip_import:
            json_body = json.dumps(_json_loads_for_import()).encode("utf-8")
            res = _http(
                method="POST",
                base_url=args.base_url,
                path="/api/import",
                query={"filename": "smoke.json"},
                body=json_body,
                content_type="application/json",
                api_key=api_key,
                include_key=bool(api_key),
            )
            _expect_status(r, label="POST /api/import?filename=smoke.json", result=res, expected=[200])

            csv_body = _csv_payload_for_import()
            res = _http(
                method="POST",
                base_url=args.base_url,
                path="/api/import",
                query={"filename": "smoke.csv"},
                body=csv_body,
                content_type="text/csv",
                api_key=api_key,
                include_key=bool(api_key),
            )
            _expect_status(r, label="POST /api/import?filename=smoke.csv", result=res, expected=[200])
        else:
            r.note("Import", "skipped (--skip-import)")

        if not args.skip_ingestion:
            res = _http(
                method="POST",
                base_url=args.base_url,
                path="/api/ingestion/run",
                api_key=api_key,
                include_key=bool(api_key),
            )
            if res.status == 401 and not api_key:
                r.fail("POST /api/ingestion/run", "401 Unauthorized (server auth is enabled; rerun with --auth and/or --key)")
            elif res.status == 409:
                r.note("POST /api/ingestion/run", "ingestion not enabled (HTTP 409)")
            elif res.status == 404:
                r.note("POST /api/ingestion/run", "endpoint not present (HTTP 404)")
            else:
                _expect_status(r, label="POST /api/ingestion/run", result=res, expected=[200])
        else:
            r.note("Ingestion run", "skipped (--skip-ingestion)")

    # Fetch loads (public)
    res = _http(method="GET", base_url=args.base_url, path="/api/loads")
    ok = _expect_status(r, label="GET /api/loads", result=res, expected=[200])
    if ok:
        payload = _parse_json_maybe(res.body)
        if _looks_like_loads_list(payload):
            loads = payload.get("loads", [])
            r.pass_("Loads response shape", f"loads={len(loads)}")
        else:
            r.fail("Loads response shape", f"unexpected payload: {payload!r}")

    res = _http(method="GET", base_url=args.base_url, path="/api/loads/scored")
    ok = _expect_status(r, label="GET /api/loads/scored", result=res, expected=[200])
    if ok:
        payload = _parse_json_maybe(res.body)
        if _looks_like_scored_loads(payload):
            loads = payload.get("loads", [])
            if loads:
                r.pass_("Scored loads include score fields", "found {score, load}")
            else:
                r.note("Scored loads", "empty list (still valid shape)")
        else:
            r.fail("Scored loads response shape", f"unexpected payload: {payload!r}")

    if r.failures:
        print(f"\nFAILED ({len(r.failures)}): " + ", ".join(r.failures))
        return 1

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
