from jervis.updater import _version_tuple


def test_version_tuple():
    assert _version_tuple("v7.1.4") == (7, 1, 4)
    assert _version_tuple("7.1.0") == (7, 1, 0)
    assert _version_tuple("8.0") is None
    assert _version_tuple("banana") is None
