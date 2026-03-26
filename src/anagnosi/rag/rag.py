import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path

import chromadb
import torch
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from loguru import logger

from anagnosi.config import paths
from anagnosi.rag.metadata_store import (
    compute_file_hash,
    delete_file_metadata,
    get_files_needing_sync,
    get_orphaned_sources,
    init_metadata_db,
    upsert_file_metadata,
)
from anagnosi.settings import settings


def discover_notes() -> list[Path]:
    md_files = [f for f in paths.project_path.glob("*.md") if f.is_file()]
    return md_files

def reading_text(file_path: Path) -> str | None:
    try:
        raw_text = file_path.read_text(encoding="utf-8")
        return clean_text(raw_text)
    except Exception as e:
        logger.error(f" Error reading {file_path}: {e}")
        return None

def clean_text(text: str) -> str | None:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text if text else None

def split_for_rag(text: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    if not text:
        return []

    try:
        headers_to_split_on = [("#", "Header 1"),("##", "Header 2"),("###", "Header 3"),("####", "Header 4"),]

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on,strip_headers=False)
        header_docs = markdown_splitter.split_text(text)

        if header_docs:
            recursive_splitter = _create_recursive_splitter(chunk_size, chunk_overlap)
            final_docs = []
            for doc in header_docs:
                if len(doc.page_content) > chunk_size:
                    sub_docs = recursive_splitter.split_documents([doc])
                    final_docs.extend(sub_docs)
                else:
                    final_docs.append(doc)

            return final_docs

        recursive_splitter = _create_recursive_splitter(chunk_size, chunk_overlap)
        return recursive_splitter.create_documents([text])
    except Exception as e:
        logger.error(f" Error splitting text for RAG: {e}")
        return []

def _create_recursive_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size,chunk_overlap=chunk_overlap,length_function=len,separators=["\n\n", "\n", " ", ""])

COLLECTION_NAME = "anagnosi_notes"
DB_PATH = paths.project_path / ".vector_db"

@lru_cache(maxsize=1)
def get_collection():
    DB_PATH.mkdir(exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return collection

@lru_cache(maxsize=1)
def get_embedder():
    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token
    return HuggingFaceEmbeddings(model_name=settings.embedding_model_name, model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"}, encode_kwargs={"normalize_embeddings": True, "batch_size": settings.rag_embedding_batch_size})


def _generate_chunk_id(source: str, content: str, chunk_index: int) -> str:
    hash_input = f"{source}:{chunk_index}:{content}"
    content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    return f"{source}_{content_hash}"

def ingest_documents(chunks: list[Document], collection, embedder: HuggingFaceEmbeddings, source: str) -> tuple[int, list[str]]:
    if not chunks:
        return 0, []

    ids = []
    contents = []
    metadatas = []

    for i, doc in enumerate(chunks):
        chunk_id = _generate_chunk_id(source, doc.page_content, i)
        ids.append(chunk_id)
        contents.append(doc.page_content)
        metadatas.append({"source": source, "chunk_index": i, "filename": f"{source}.md"})

    try:
        embeddings = embedder.embed_documents(contents)
        collection.upsert(ids=ids, embeddings=embeddings, documents=contents, metadatas=metadatas)
        logger.debug(f"Upserted {len(embeddings)} chunks from {source}")
        return len(embeddings), ids
    except Exception as e:
        logger.error(f"Failed to embed/upsert: {e}")
        return 0, []


def delete_source_chunks(collection, source: str) -> int:
    try:
        existing = collection.get(where={"source": source})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            logger.debug(f"Deleted {len(existing['ids'])} chunks for {source}")
            return len(existing["ids"])
        return 0
    except Exception as e:
        logger.error(f"Error deleting chunks for {source}: {e}")
        return 0


def sync_documents_to_collection(collection, embedder: HuggingFaceEmbeddings, force_reindex: bool = False):
    CHUNK_SIZE = settings.rag_chunk_size
    CHUNK_OVERLAP = settings.rag_chunk_overlap

    init_metadata_db()

    current_files: dict[str, Path] = {f.stem: f for f in discover_notes()}
    current_sources = set(current_files.keys())

    sources_to_sync = get_files_needing_sync(current_files, force_reindex)

    for source in sources_to_sync:
        file_path = current_files[source]
        file_hash = compute_file_hash(file_path)
        if not file_hash:
            continue

        text = reading_text(file_path)
        if not text:
            continue

        chunks_docs = split_for_rag(text, CHUNK_SIZE, CHUNK_OVERLAP)
        if not chunks_docs:
            continue

        delete_source_chunks(collection, source)
        count, _ = ingest_documents(chunks_docs, collection, embedder, source)
        if count > 0:
            upsert_file_metadata(source, file_path, file_hash, count)

    for source in get_orphaned_sources(current_sources):
        delete_source_chunks(collection, source)
        delete_file_metadata(source)
        logger.debug(f"Cleaned up orphaned file: {source}")

def retrieve_relevant_chunks(query: str, collection, embedder: HuggingFaceEmbeddings, top_k: int = 5) -> list[dict]:
    try:
        query_embedding = embedder.embed_query(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k, include=["documents", "metadatas", "distances"])

        formatted = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                formatted.append({"content": results["documents"][0][i], "source": results["metadatas"][0][i].get("source", "unknown"), "chunk_index": results["metadatas"][0][i].get("chunk_index", -1), "distance": results["distances"][0][i]})
        return formatted
    except Exception as e:
        logger.error(f"Error retrieving chunks: {e}")
        return []


def get_rag_from_md_notes(query: str, top_k: int):
    init_metadata_db()

    collection = get_collection()
    embedder = get_embedder()
    return retrieve_relevant_chunks(query, collection, embedder, top_k)
