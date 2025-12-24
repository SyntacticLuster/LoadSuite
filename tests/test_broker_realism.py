import os
from app import data


def test_broker_flags_and_ratings_correlated():
    data._SYNTH_CACHE.clear()
    data._BROKER_PROFILES.clear()

    ds = data.get_synthetic_dataset(300, seed=123)

    # Per-broker consistency checks
    mapping = {}
    flags = {}
    for l in ds.loads:
        name = l.broker.name
        rating = l.broker.rating
        lane = l.lane_history
        det = l.detention
        if name in mapping:
            assert mapping[name] == rating
            assert flags[name][0] == lane
            assert flags[name][1] == det
        else:
            mapping[name] = rating
            flags[name] = (lane, det)

    # Aggregate expectation: higher-rated brokers should have more lane_history
    # Compare average lane_history for brokers with rating >=4.0 vs <=3.0
    groups = {"high": [], "low": []}
    for name, rating in mapping.items():
        if rating >= 4.0:
            groups["high"].append(flags[name][0])
        if rating <= 3.0:
            groups["low"].append(flags[name][0])

    # Need at least some brokers in each group to make an aggregate check meaningful
    if groups["high"] and groups["low"]:
        avg_high = sum(1 for v in groups["high"] if v) / len(groups["high"])
        avg_low = sum(1 for v in groups["low"] if v) / len(groups["low"])
        assert avg_high >= avg_low
