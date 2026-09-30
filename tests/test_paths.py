from jervis.paths import Paths


def test_jervis_home_override(monkeypatch, tmp_path):
    monkeypatch.setenv("JERVIS_HOME", str(tmp_path))
    paths = Paths.resolve()
    assert paths.root == tmp_path.resolve()
    assert paths.config == tmp_path.resolve() / "config"
    assert paths.data == tmp_path.resolve() / "data"
    paths.ensure()
    assert paths.logs.is_dir()
    assert paths.cache.is_dir()


def test_service_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("JERVIS_HOME", str(tmp_path))
    env = Paths.resolve().service_environment()
    assert set(env) == {
        "JERVIS_CONFIG_HOME",
        "JERVIS_DATA_HOME",
        "JERVIS_LOG_HOME",
        "JERVIS_CACHE_HOME",
    }
