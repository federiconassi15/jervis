import jervis.updater as updater


def test_version_tuple():
    assert updater._version_tuple("v7.1.4") == (7, 1, 4)
    assert updater._version_tuple("8.0") is None


def test_select_latest_same_minor_ignores_newer_minor(monkeypatch):
    monkeypatch.setattr(updater, "VERSION_INFO", (7, 1, 0))

    releases = [
        {
            "tag_name": "v7.2.0",
            "draft": False,
            "prerelease": False,
        },
        {
            "tag_name": "v7.1.9",
            "draft": False,
            "prerelease": False,
            "html_url": "https://example.invalid/7.1.9",
        },
        {
            "tag_name": "v7.1.8",
            "draft": False,
            "prerelease": False,
        },
    ]

    version, release = updater._select_latest_same_line(releases)

    assert version == (7, 1, 9)
    assert release["tag_name"] == "v7.1.9"
