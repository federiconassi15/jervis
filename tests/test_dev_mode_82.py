"""Dev Mode must not execute arbitrary shell or inspect unapproved repositories."""
import shutil
import subprocess

import pytest

from jervis.capabilities import CapabilityGrant, Principal
from jervis.dev_mode import inspect_git


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_read_only_inspection_requires_scope_and_does_not_mutate(tmp_path):
    repo = tmp_path / "my repo; do not run commands"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    readme = repo / "README.md"
    readme.write_text("some uncommitted changes")
    owner = Principal("user", "owner", True)
    grant = CapabilityGrant("user", "filesystem.read", str(repo.resolve()), 10**12)
    with pytest.raises(PermissionError):
        inspect_git(repo, "status", owner)
    result = inspect_git(repo, "status", owner, grants=(grant,))
    assert result.success
    assert "README.md" in result.output
    assert readme.read_text() == "some uncommitted changes"
    result = inspect_git(repo, "diff_check", owner, grants=(grant,))
    assert result.success
    with pytest.raises(ValueError):
        inspect_git(repo, "reset --hard", owner, grants=(grant,))


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_no_parent_repo_fallback_or_cross_device_grants(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    child = root / "child"
    child.mkdir()
    principal = Principal("owner", "owner", True)
    broad = CapabilityGrant("owner", "filesystem.read", str(root.resolve()), 10**12)
    with pytest.raises(ValueError, match="exact"):
        inspect_git(child, "status", principal, grants=(broad,))
    phone = Principal("owner", "owner", True, "remote-device")
    with pytest.raises(PermissionError):
        inspect_git(root, "status", phone, grants=(broad,))


def test_no_git_operation_when_unauthenticated(tmp_path):
    principal = Principal("owner", "owner", False)
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(PermissionError):
        inspect_git(root, "status", principal)
