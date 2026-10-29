"""Knowledge Vault privacy, bounds, and incremental retrieval."""
import pytest

from jervis.knowledge_vault import KnowledgeVault


def test_index_search_modify_and_delete(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    doc = root / "readme.md"
    doc.write_text("The Jervis Blue Terminal companion runs on Android.")
    with _open(tmp_path / "vault.sqlite3", root) as vault:
        assert vault.update() == {"updated": 1, "removed": 0, "indexed": 1}
        assert vault.update()["updated"] == 0
        assert vault.search("blue companion")[0].path == "readme.md"
        doc.write_text("The Jervis security protocol now requires pairing.")
        assert vault.update()["updated"] == 1
        assert vault.search("blue companion") == []
        assert vault.search("security pairing")
        doc.unlink()
        assert vault.update()["removed"] == 1
        assert vault.search("security pairing") == []


class _open:
    def __init__(self, db, root):
        self.vault = KnowledgeVault(db, root)

    def __enter__(self):
        return self.vault

    def __exit__(self, *_):
        self.vault.close()


def test_separate_root_and_symlink_avoidance(tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    private = tmp_path / "private"
    private.mkdir()
    (private / "secrets.md").write_text("PRIVATE-NEVER-INDEX")
    try:
        (root / "shortcut.md").symlink_to(private / "secrets.md")
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks unavailable")
    vault = KnowledgeVault(tmp_path / "vault.db", root)
    try:
        assert vault.update()["indexed"] == 0
        assert vault.search("PRIVATE-NEVER-INDEX") == []
    finally:
        vault.close()
    with pytest.raises(ValueError, match="different root"):
        KnowledgeVault(tmp_path / "vault.db", private)


def test_query_is_data_not_fts_program(tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    (root / "abc.txt").write_text("alpha and beta are separate words")
    vault = KnowledgeVault(tmp_path / "vault.db", root)
    try:
        vault.update()
        assert vault.search('alpha" OR secret') == []
        assert vault.search("alpha")[0].path == "abc.txt"
    finally:
        vault.close()



def test_knowledge_index_database_is_private(tmp_path):
    import os
    root = tmp_path / "docs"
    root.mkdir()
    database = tmp_path / "index.sqlite3"
    vault = KnowledgeVault(database, root)
    vault.close()
    if os.name != "nt":
        assert database.stat().st_mode & 0o077 == 0
