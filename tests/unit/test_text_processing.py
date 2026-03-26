from langchain_core.documents import Document

from anagnosi.rag.rag import clean_text, split_for_rag


class TestCleanText:
    def test_removes_excessive_newlines(self):
        assert clean_text("Line1\n\n\n\nLine2") == "Line1\n\nLine2"

    def test_strips_whitespace(self):
        assert clean_text("  content  \n\n") == "content"
        assert clean_text("  \t  \n\n  \t  ") is None

    def test_returns_none_for_empty(self):
        assert clean_text("") is None
        assert clean_text("   \n\n  ") is None
        assert clean_text("\r\n\r\n") is None

    def test_preserves_single_newlines(self):
        assert clean_text("Line1\nLine2") == "Line1\nLine2"
        assert clean_text("Para1\n\nPara2") == "Para1\n\nPara2"


class TestSplitForRag:
    def test_invalid_chunk_size_zero(self):
        result = split_for_rag("some text", chunk_size=0, chunk_overlap=10)
        assert isinstance(result, list)

    def test_negative_parameters(self):
        assert split_for_rag("text", chunk_size=-10, chunk_overlap=5) == []
        assert split_for_rag("text", chunk_size=100, chunk_overlap=-5) == []

    def test_splits_markdown_with_headers(self):
        text = "# Title\nContent here\n## Subheader\nMore content"
        chunks = split_for_rag(text, chunk_size=50, chunk_overlap=10)

        assert len(chunks) > 0
        assert all(isinstance(c, Document) for c in chunks)
        assert any("Title" in c.page_content for c in chunks)

    def test_respects_chunk_size(self):
        long_text = "word " * 100
        chunks = split_for_rag(long_text, chunk_size=100, chunk_overlap=20)

        assert all(len(c.page_content) <= 110 for c in chunks)

    def test_handles_empty_input_gracefully(self):
        assert split_for_rag("", chunk_size=100, chunk_overlap=10) == []
        assert split_for_rag(None, chunk_size=100, chunk_overlap=10) == []
