from unittest.mock import patch

import pytest

from anagnosi.rag import metadata_store


class TestMetadataStore:
    @pytest.fixture
    def mock_db_path(self, tmp_path):
        db_file = tmp_path / "test_metadata.db"
        with patch.object(metadata_store, "DB_PATH", db_file):
            yield db_file

    def test_init_metadata_db_creates_table(self, mock_db_path):
        metadata_store.init_metadata_db()
        with metadata_store.get_db_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_index'")
            assert cursor.fetchone() is not None

    def test_upsert_new_file(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")

        success = metadata_store.upsert_file_metadata("note", test_file, "hash123", 5)
        assert success is True

        meta = metadata_store.get_file_metadata("note")
        assert meta["file_hash"] == "hash123"
        assert meta["chunk_count"] == 5

    def test_get_files_needing_sync_detects_changes(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")

        initial_hash = metadata_store.compute_file_hash(test_file)
        metadata_store.upsert_file_metadata("note", test_file, initial_hash, 5)

        current_files = {"note": test_file}
        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert len(needs_sync) == 0

        test_file.write_text("modified content")

        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert "note" in needs_sync

    def test_get_files_needing_sync_force_all_files(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")

        initial_hash = metadata_store.compute_file_hash(test_file)
        metadata_store.upsert_file_metadata("note", test_file, initial_hash, 5)

        current_files = {"note": test_file}

        needs_sync_no_force = metadata_store.get_files_needing_sync(current_files, force=False)
        assert len(needs_sync_no_force) == 0

        needs_sync_force = metadata_store.get_files_needing_sync(current_files, force=True)
        assert "note" in needs_sync_force

    def test_get_files_needing_sync_force_multiple_files(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()

        files = {}
        for i in range(3):
            test_file = tmp_path / f"note{i}.md"
            test_file.write_text(f"content{i}")
            file_hash = metadata_store.compute_file_hash(test_file)
            metadata_store.upsert_file_metadata(f"note{i}", test_file, file_hash, 5)
            files[f"note{i}"] = test_file

        needs_sync = metadata_store.get_files_needing_sync(files, force=True)
        assert len(needs_sync) == 3
        assert set(needs_sync) == {"note0", "note1", "note2"}

    def test_get_files_needing_sync_new_file_not_in_db(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "new_note.md"
        test_file.write_text("new content")

        current_files = {"new_note": test_file}

        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert "new_note" in needs_sync

    def test_get_files_needing_sync_mixed_new_and_existing(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()

        existing_file = tmp_path / "existing.md"
        existing_file.write_text("existing content")
        existing_hash = metadata_store.compute_file_hash(existing_file)
        metadata_store.upsert_file_metadata("existing", existing_file, existing_hash, 5)

        new_file = tmp_path / "new.md"
        new_file.write_text("new content")

        current_files = {"existing": existing_file, "new": new_file}

        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert "new" in needs_sync
        assert "existing" not in needs_sync

    def test_get_files_needing_sync_content_changed(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("original content")

        initial_hash = metadata_store.compute_file_hash(test_file)
        metadata_store.upsert_file_metadata("note", test_file, initial_hash, 5)

        test_file.write_text("modified content")

        current_files = {"note": test_file}
        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert "note" in needs_sync

    def test_get_files_needing_sync_file_moved(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")

        file_hash = metadata_store.compute_file_hash(test_file)
        metadata_store.upsert_file_metadata("note", test_file, file_hash, 5)

        moved_file = tmp_path / "subdir" / "note.md"
        moved_file.parent.mkdir()
        test_file.rename(moved_file)

        current_files = {"note": moved_file}
        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert "note" in needs_sync

    def test_get_files_needing_sync_mtime_changed(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")

        file_hash = metadata_store.compute_file_hash(test_file)
        metadata_store.upsert_file_metadata("note", test_file, file_hash, 5)

        import os
        os.utime(test_file, (test_file.stat().st_atime, test_file.stat().st_mtime + 1))

        current_files = {"note": test_file}
        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert "note" in needs_sync

    def test_get_files_needing_sync_unchanged_file(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")

        initial_hash = metadata_store.compute_file_hash(test_file)
        metadata_store.upsert_file_metadata("note", test_file, initial_hash, 5)

        current_files = {"note": test_file}
        needs_sync = metadata_store.get_files_needing_sync(current_files)
        assert len(needs_sync) == 0

    def test_get_files_needing_sync_empty_input(self, mock_db_path):
        metadata_store.init_metadata_db()
        needs_sync = metadata_store.get_files_needing_sync({})
        assert needs_sync == []

    def test_get_files_needing_sync_hash_computation_fails(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")

        initial_hash = metadata_store.compute_file_hash(test_file)
        metadata_store.upsert_file_metadata("note", test_file, initial_hash, 5)

        with patch.object(metadata_store, "compute_file_hash", return_value=None):
            current_files = {"note": test_file}
            needs_sync = metadata_store.get_files_needing_sync(current_files)
            assert "note" not in needs_sync

    def test_get_orphaned_sources_detects_deleted_files(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")
        file_hash = metadata_store.compute_file_hash(test_file)

        metadata_store.upsert_file_metadata("note", test_file, file_hash, 5)

        orphans = metadata_store.get_orphaned_sources(set())
        assert "note" in orphans

    def test_get_orphaned_sources_no_orphans(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")
        file_hash = metadata_store.compute_file_hash(test_file)

        metadata_store.upsert_file_metadata("note", test_file, file_hash, 5)

        orphans = metadata_store.get_orphaned_sources({"note"})
        assert len(orphans) == 0

    def test_delete_file_metadata_existing(self, mock_db_path, tmp_path):
        metadata_store.init_metadata_db()
        test_file = tmp_path / "note.md"
        test_file.write_text("content")
        file_hash = metadata_store.compute_file_hash(test_file)

        metadata_store.upsert_file_metadata("note", test_file, file_hash, 5)
        assert metadata_store.get_file_metadata("note") is not None

        deleted = metadata_store.delete_file_metadata("note")
        assert deleted is True
        assert metadata_store.get_file_metadata("note") is None

    def test_delete_file_metadata_nonexistent(self, mock_db_path):
        metadata_store.init_metadata_db()
        deleted = metadata_store.delete_file_metadata("nonexistent")
        assert deleted is False
