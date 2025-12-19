from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .data import Dataset, detect_and_parse_import, generate_synthetic_loads, write_sample_files
from .filters import apply_filters, apply_sort
from .models import Load, LoadsQuery, RefreshRequest


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


app = FastAPI(title="Loadboard MVP (UI-first)", version="0.1.0")


_dataset: Dataset = generate_synthetic_loads(250)


@app.on_event("startup")
def _startup() -> None:
    # Ensure sample files exist for easy import testing.
    write_sample_files(BASE_DIR)


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "source": _dataset.source,
        "count": len(_dataset.loads),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/loads")
def list_loads(
    q: Optional[str] = None,
    equipment: Optional[str] = None,
    weight_min: Optional[int] = None,
    weight_max: Optional[int] = None,
    hazmat: Optional[bool] = None,
    pickup_start: Optional[datetime] = None,
    pickup_end: Optional[datetime] = None,
    delivery_start: Optional[datetime] = None,
    delivery_end: Optional[datetime] = None,
    deadhead_max: Optional[float] = None,
    rpm_min: Optional[float] = None,
    broker_rating_min: Optional[float] = None,
    detention: Optional[bool] = None,
    multi_stop: Optional[bool] = None,
    lane_history: Optional[bool] = None,
    sort: str = "composite",
) -> dict[str, Any]:
    query = LoadsQuery(
        q=q,
        equipment=equipment,
        weight_min=weight_min,
        weight_max=weight_max,
        hazmat=hazmat,
        pickup_start=pickup_start,
        pickup_end=pickup_end,
        delivery_start=delivery_start,
        delivery_end=delivery_end,
        deadhead_max=deadhead_max,
        rpm_min=rpm_min,
        broker_rating_min=broker_rating_min,
        detention=detention,
        multi_stop=multi_stop,
        lane_history=lane_history,
        sort=sort,  # validated by pydantic literal
    )
    now = datetime.now(timezone.utc)
    filtered = apply_filters(_dataset.loads, query)
    ranked = apply_sort(filtered, query, now)
    return {
        "total": len(ranked),
        "loads": [l.model_dump(mode="json") for l in ranked],
    }


@app.get("/api/loads/{load_id}")
def get_load(load_id: str) -> dict[str, Any]:
    for load in _dataset.loads:
        if load.id == load_id:
            return load.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Load not found")


@app.post("/api/refresh")
def refresh(req: RefreshRequest = RefreshRequest()) -> dict[str, Any]:
    global _dataset
    _dataset = generate_synthetic_loads(req.count)
    return {"ok": True, "source": _dataset.source, "count": len(_dataset.loads)}


@app.post("/api/import")
async def import_data(request: Request, filename: str) -> dict[str, Any]:
    global _dataset
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    content = await request.body()
    try:
        loads, kind = detect_and_parse_import(filename, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {e}")
    _dataset = Dataset(loads=loads, source=f"import:{kind}")
    return {"ok": True, "source": _dataset.source, "count": len(_dataset.loads)}


# Static UI
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))
