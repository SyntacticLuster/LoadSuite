from app import data


def test_broker_rating_stable_per_broker():
    data._SYNTH_CACHE.clear()
    data._BROKER_PROFILES.clear()

    ds = data.get_synthetic_dataset(200, seed=9999)
    mapping = {}
    for l in ds.loads:
        name = l.broker.name
        rating = l.broker.rating
        if name in mapping:
            assert mapping[name] == rating
        else:
            mapping[name] = rating

    # Ensure at least a few broker names appear
    assert len(mapping) >= 3


def test_broker_rating_consistent_with_profiles():
    data._SYNTH_CACHE.clear()
    data._BROKER_PROFILES.clear()

    # Generate dataset which will populate profiles
    ds = data.get_synthetic_dataset(200, seed=1234)

    # Each broker in dataset should have a profile entry
    for l in ds.loads:
        assert l.broker.name in data._BROKER_PROFILES[1234]
        assert data._BROKER_PROFILES[1234][l.broker.name].rating_display == l.broker.rating
