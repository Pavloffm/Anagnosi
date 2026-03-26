import hashlib
import re
from pathlib import Path
from typing import Optional, List, Dict

import chromadb
import torch
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from loguru import logger
from langchain_huggingface import HuggingFaceEmbeddings

from anagnosi.rag.metadata_store import init_metadata_db, delete_file_metadata, get_orphaned_sources, \
    upsert_file_metadata, get_file_metadata, compute_file_hash, get_files_needing_sync
from anagnosi.config import paths

load_dotenv()

def discover_notes() -> list[Path]:
    md_files = [f for f in paths.project_path.glob("*.md") if f.is_file()]
    return md_files

def reading_text(file_path: Path) -> Optional[str]:
    try:
        raw_text = file_path.read_text(encoding="utf-8")
        return clean_text(raw_text)
    except Exception as e:
        logger.error(f" Error reading {file_path}: {e}")
        return None

def clean_text(text: str) -> Optional[str]:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text if text else None

def split_for_rag(text: str, chunk_size: int, chunk_overlap: int) -> List[Document]:
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
def get_collection():
    DB_PATH.mkdir(exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return collection

def get_embedder():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32}
    )


def _generate_chunk_id(source: str, content: str, chunk_index: int) -> str:
    hash_input = f"{source}:{chunk_index}:{content}"
    content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    return f"{source}_{content_hash}"

def ingest_documents(chunks: List[Document], collection, embedder: HuggingFaceEmbeddings, source: str) -> tuple[int, List[str]]:
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
        logger.info(f"Upserted {len(embeddings)} chunks from {source}")
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


def sync_documents_to_collection(collection, embedder: HuggingFaceEmbeddings, force_reindex: bool = False) -> Dict[str, int]:
    CHUNK_SIZE = 256
    CHUNK_OVERLAP = 32

    init_metadata_db()

    current_files: Dict[str, Path] = {f.stem: f for f in discover_notes()}
    current_sources = set(current_files.keys())

    stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}

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

        old_count = delete_source_chunks(collection, source)
        if old_count > 0:
            stats["deleted"] += old_count

        count, _ = ingest_documents(chunks_docs, collection, embedder, source)
        if count > 0:
            upsert_file_metadata(source, file_path, file_hash, count)
            if get_file_metadata(source)["created_at"] == get_file_metadata(source)["last_synced"]:
                stats["added"] += count
            else:
                stats["updated"] += count
        else:
            stats["skipped"] += 1

    stats["skipped"] += len(current_files) - len(sources_to_sync)

    for source in get_orphaned_sources(current_sources):
        deleted = delete_source_chunks(collection, source)
        delete_file_metadata(source)
        stats["deleted"] += deleted
        logger.info(f"Cleaned up orphaned file: {source}")

    logger.info(f"Sync complete: +{stats['added']} updated:{stats['updated']} deleted:{stats['deleted']} "\
                  "skipped:{stats['skipped']}")
    return stats


def retrieve_relevant_chunks(query: str, collection, embedder: HuggingFaceEmbeddings, top_k: int = 5) -> List[dict]:
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


def get_rag_from_md_notes(query: str):
    init_metadata_db()

    collection = get_collection()
    embedder = get_embedder()
    return retrieve_relevant_chunks(query, collection, embedder, top_k=5)

if __name__ == '__main__':
    logger.info(get_rag_from_md_notes("What is cat?"))