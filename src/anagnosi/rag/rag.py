import re
from pathlib import Path
from typing import Optional, List

import chromadb
import torch
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from loguru import logger
from langchain_huggingface import HuggingFaceEmbeddings

from src.anagnosi.config import paths

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

def ingest_documents(chunks: List[str], collection, embedder: HuggingFaceEmbeddings, source: str = ""):
    if not chunks:
        return 0

    ids = [f"{source}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source, "chunk_index": i} for i in range(len(chunks))]

    try:
        embeddings = embedder.embed_documents(chunks)

        collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        logger.info(f"Ingested {len(embeddings)} chunks from {source}")
        return len(embeddings)
    except Exception as e:
        logger.error(f"Failed to embed documents: {e}")
        return 0


def retrieve_relevant_chunks(query: str, collection, embedder: HuggingFaceEmbeddings, top_k: int = 5) -> List[dict]:
    try:
        query_embedding = embedder.embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        formatted = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                formatted.append({
                    "content": results["documents"][0][i],
                    "source": results["metadatas"][0][i].get("source", "unknown"),
                    "chunk_index": results["metadatas"][0][i].get("chunk_index", -1),
                    "distance": results["distances"][0][i]
                })
            logger.info(f"Retrieved {len(formatted)} chunks for query: '{query[:50]}...'")

        return formatted

    except Exception as e:
        logger.error(f"Error retrieving chunks: {e}")
        return []

def get_rag_from_md_notes(query: str):
    CHUNK_SIZE = 256
    CHUNK_OVERLAP = 32

    files = discover_notes()
    collection = get_collection()
    embedder = get_embedder()

    for file_path in files:
        text = reading_text(file_path)
        chunks_docs = split_for_rag(text, CHUNK_SIZE, CHUNK_OVERLAP)
        chunks = [doc.page_content for doc in chunks_docs]

        count = ingest_documents(chunks, collection, embedder, source=file_path.stem)

    return retrieve_relevant_chunks(query, collection, embedder, top_k=5)

if __name__ == '__main__':
    logger.info(get_rag_from_md_notes("What is cat?"))