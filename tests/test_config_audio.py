import copy

import pytest

from jervis.config import DEFAULT_CONFIG, validate


def test_volume_bounds():
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["audio"]["jervis_volume"] = 2.0
    validate(config)
    config["audio"]["jervis_volume"] = 0.05
    validate(config)


@pytest.mark.parametrize("value", [0.0, 2.01, -1.0])
def test_invalid_volume_rejected(value):
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["audio"]["jervis_volume"] = value
    with pytest.raises(ValueError):
        validate(config)
