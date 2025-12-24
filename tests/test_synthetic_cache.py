from fastapi.testclient import TestClient
import os

from app.main import app
from app import data


def test_loads_endpoint_stable_within_process():
    client = TestClient(app)
    r1 = client.get("/api/loads")
    assert r1.status_code == 200
    l1 = r1.json()["loads"]

    r2 = client.get("/api/loads")
    assert r2.status_code == 200
    l2 = r2.json()["loads"]

    assert len(l1) == len(l2)
    # sample first 20 loads (or fewer if not enough)
    n = min(20, len(l1))
    for a, b in zip(l1[:n], l2[:n]):
        assert a["id"] == b["id"]
        assert a["broker"]["rating"] == b["broker"]["rating"]


def test_get_synthetic_dataset_seed_reproducible():
    # Clear cache to simulate cold start
    data._SYNTH_CACHE.clear()

    d1 = data.get_synthetic_dataset(200, seed=12345)
    ids1 = [l.id for l in d1.loads]
    ratings1 = [l.broker.rating for l in d1.loads]

    # Clear and regenerate with same seed
    data._SYNTH_CACHE.clear()
    d2 = data.get_synthetic_dataset(200, seed=12345)
    ids2 = [l.id for l in d2.loads]
    ratings2 = [l.broker.rating for l in d2.loads]

    assert ids1 == ids2
    assert ratings1 == ratings2

    # Regenerate with a different seed and expect differences
    data._SYNTH_CACHE.clear()
    d3 = data.get_synthetic_dataset(200, seed=54321)
    ids3 = [l.id for l in d3.loads]
    assert ids1 != ids3
