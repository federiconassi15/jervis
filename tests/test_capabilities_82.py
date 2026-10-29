"""8.2 capability boundary tests: no implicit authority for a connected client."""
from jervis.capabilities import (
    CapabilityGrant, Principal, authorize,
)


def test_local_read_is_not_remote_read():
    owner = Principal("person", "owner", True)
    phone = Principal("person", "owner", True, "phone-1")
    assert authorize(owner, "system.status.read").permitted
    assert not authorize(phone, "system.status.read").permitted
    grant = CapabilityGrant("person", "system.status.read", "host", 200, "phone-1")
    assert authorize(phone, "system.status.read", scope="host", grants=(grant,),
                     now=100).permitted
    assert not authorize(phone, "system.status.read", scope="host", grants=(grant,),
                         now=201).permitted


def test_privileged_actions_need_fresh_auth_and_scope(tmp_path):
    owner = Principal("person", "owner", True)
    grant = CapabilityGrant("person", "filesystem.write", str(tmp_path), 1000)
    assert not authorize(owner, "filesystem.write", scope=str(tmp_path / "x"),
                         grants=(grant,), now=100).permitted
    assert authorize(owner, "filesystem.write", scope=str(tmp_path / "x"),
                     grants=(grant,), now=100, fresh_auth=True).permitted
    assert not authorize(owner, "filesystem.write", scope=str(tmp_path / "../escape"),
                         grants=(grant,), now=100, fresh_auth=True).permitted


def test_unknown_identity_capability_and_cross_device_grants():
    guest = Principal("user", "guest", True)
    assert not authorize(guest, "process.execute", scope="tool", fresh_auth=True).permitted
    assert not authorize(Principal("user", "owner", False), "system.status.read").permitted
    assert not authorize(Principal("user", "owner", True), "fictional.root").permitted
    phone = Principal("user", "owner", True, "phone-2")
    wrong = CapabilityGrant("user", "logs.read", "host", 1000, "phone-1")
    assert not authorize(phone, "logs.read", scope="host", grants=(wrong,),
                         now=100).permitted
