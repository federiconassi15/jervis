from jervis.install_tx import InstallTransaction
from jervis.models import Health


class FakePlatform:
    def __init__(self, active=False):
        self.active = active
        self.removed = 0

    def service_health(self):
        return Health(self.active, "service", "test")

    def remove_service(self):
        self.removed += 1


def test_file_rollback(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("before", encoding="utf-8")
    platform = FakePlatform()

    try:
        with InstallTransaction(platform) as transaction:
            transaction.track_file(path)
            path.write_text("after", encoding="utf-8")
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert path.read_text(encoding="utf-8") == "before"


def test_new_service_removed_on_rollback():
    platform = FakePlatform(active=False)
    try:
        with InstallTransaction(platform) as transaction:
            transaction.mark_service_changed()
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert platform.removed == 1


def test_commit_keeps_changes(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("before", encoding="utf-8")
    platform = FakePlatform()

    with InstallTransaction(platform) as transaction:
        transaction.track_file(path)
        path.write_text("after", encoding="utf-8")
        transaction.commit()

    assert path.read_text(encoding="utf-8") == "after"
