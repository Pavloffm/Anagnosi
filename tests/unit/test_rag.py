from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from anagnosi.rag import rag


class TestDiscoverNotes:
    def test_discovers_markdown_files(self, tmp_path):
        (tmp_path / "note1.md").write_text("content1")
        (tmp_path / "note2.md").write_text("content2")
        (tmp_path / "note.txt").write_text("not markdown")

        with patch.object(rag.paths, "project_path", tmp_path):
            files = rag.discover_notes()
            assert len(files) == 2
            assert all(f.suffix == ".md" for f in files)

    def test_ignores_directories(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.md").write_text("content")

        with patch.object(rag.paths, "project_path", tmp_path):
            files = rag.discover_notes()
            assert len(files) == 0


class TestReadingText:
    def test_reads_file_successfully(self, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("Hello World")

        result = rag.reading_text(test_file)
        assert result == "Hello World"

    def test_returns_none_on_missing_file(self, tmp_path):
        missing_file = tmp_path / "nonexistent.md"
        result = rag.reading_text(missing_file)
        assert result is None

    def test_returns_none_on_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")

        result = rag.reading_text(empty_file)
        assert result is None


class TestSplitForRag:
    def test_creates_documents_with_metadata(self):
        text = "# Header\nContent here"
        chunks = rag.split_for_rag(text, chunk_size=50, chunk_overlap=10)

        assert len(chunks) > 0
        assert all(isinstance(c, Document) for c in chunks)
        assert all(hasattr(c, "page_content") for c in chunks)

    def test_handles_long_text_chunking(self):
        long_text = "word " * 500
        chunks = rag.split_for_rag(long_text, chunk_size=100, chunk_overlap=20)

        assert len(chunks) > 1
        assert all(len(c.page_content) > 0 for c in chunks)

    def test_preserves_header_structure(self):
        text = "# Main Title\nSome content\n## Subtitle\nMore content"
        chunks = rag.split_for_rag(text, chunk_size=200, chunk_overlap=20)

        assert any("Main Title" in c.page_content or "Header 1" in str(c.metadata) for c in chunks)


class TestIngestDocuments:
    def test_ingests_empty_list(self):
        mock_collection = MagicMock()
        mock_embedder = MagicMock()

        count, ids = rag.ingest_documents([], mock_collection, mock_embedder, "test")
        assert count == 0
        assert ids == []

    def test_ingests_documents_successfully(self):
        mock_collection = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_documents.return_value = [[0.1, 0.2], [0.3, 0.4]]

        chunks = [
            Document(page_content="chunk 1", metadata={"source": "test"}),
            Document(page_content="chunk 2", metadata={"source": "test"}),
        ]

        count, ids = rag.ingest_documents(chunks, mock_collection, mock_embedder, "test")
        assert count == 2
        assert len(ids) == 2
        assert mock_collection.upsert.called

    def test_generates_unique_chunk_ids(self):
        mock_collection = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_documents.return_value = [[0.1, 0.2]]

        chunks = [Document(page_content="unique content", metadata={})]

        count, ids = rag.ingest_documents(chunks, mock_collection, mock_embedder, "test_source")

        assert ids[0].startswith("test_source_")


class TestRetrieveRelevantChunks:
    def test_returns_formatted_results(self):
        mock_collection = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1, 0.2]

        mock_collection.query.return_value = {
            "documents": [["content 1", "content 2"]],
            "metadatas": [[{"source": "note1", "chunk_index": 0}, {"source": "note2", "chunk_index": 1}]],
            "distances": [[0.1, 0.2]],
        }

        results = rag.retrieve_relevant_chunks("test query", mock_collection, mock_embedder, top_k=2)

        assert len(results) == 2
        assert results[0]["content"] == "content 1"
        assert results[0]["source"] == "note1"
        assert results[0]["chunk_index"] == 0
        assert "distance" in results[0]

    def test_handles_empty_results(self):
        mock_collection = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1, 0.2]

        mock_collection.query.return_value = {"documents": [], "metadatas": [], "distances": []}

        results = rag.retrieve_relevant_chunks("test query", mock_collection, mock_embedder)
        assert results == []

    def test_handles_collection_error(self):
        mock_collection = MagicMock()
        mock_embedder = MagicMock()
        mock_collection.query.side_effect = Exception("DB error")

        results = rag.retrieve_relevant_chunks("test query", mock_collection, mock_embedder)
        assert results == []


class TestDeleteSourceChunks:
    def test_deletes_existing_chunks(self):
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": ["id1", "id2", "id3"]}

        count = rag.delete_source_chunks(mock_collection, "test_source")
        assert count == 3
        assert mock_collection.delete.called

    def test_returns_zero_when_no_chunks(self):
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": []}

        count = rag.delete_source_chunks(mock_collection, "test_source")
        assert count == 0
