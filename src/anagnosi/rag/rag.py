import re
from pathlib import Path
from typing import Optional, List
from xml.dom.minidom import Document

import chromadb
import torch
from dotenv import load_dotenv
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from loguru import logger
from transformers import AutoTokenizer, AutoModel

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


class SimpleEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        logger.info(f"Loading embedding model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()

    def _mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, dim=1)
        sum_mask = torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
        return sum_embeddings / sum_mask

    def encode(self, text: str) -> list[float]:
        encoded = self.tokenizer(text,padding=True,truncation=True,max_length=512,return_tensors="pt")
        with torch.no_grad():
            output = self.model(**encoded)
        embeddings = self._mean_pooling(output, encoded["attention_mask"])
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        return embeddings.cpu().tolist()[0]

COLLECTION_NAME = "anagnosi_notes"
DB_PATH = paths.project_path / ".vector_db"
def get_collection():
    DB_PATH.mkdir(exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return collection


def ingest_documents(chunks: List[str], collection, embedder: SimpleEmbedder, source: str = ""):
    if not chunks:
        return 0

    embeddings = []
    ids = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        try:
            embedding = embedder.encode(chunk)
            embeddings.append(embedding)
            ids.append(f"{source}_{i}")
            metadatas.append({"source": source, "chunk_index": i})
        except Exception as e:
            logger.warning(f"Failed to embed chunk {i}: {e}")

    if embeddings:
        collection.add(ids=ids,embeddings=embeddings,documents=chunks,metadatas=metadatas)
        logger.info(f"Ingested {len(embeddings)} chunks from {source}")
        return len(embeddings)

    return 0


def retrieve_relevant_chunks(query: str,collection,embedder: SimpleEmbedder,top_k: int = 5) -> List[dict]:
    try:
        query_embedding = embedder.encode(query)

        results = collection.query(query_embeddings=[query_embedding],n_results=top_k,include=["documents", "metadatas", "distances"])

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
    embedder = SimpleEmbedder(model_name="sentence-transformers/all-MiniLM-L6-v2")

    for file_path in files:
        text = reading_text(file_path)
        chunks_docs = split_for_rag(text, CHUNK_SIZE, CHUNK_OVERLAP)
        chunks = [doc.page_content for doc in chunks_docs]

        count = ingest_documents(chunks, collection, embedder, source=file_path.stem)
        logger.info(split_for_rag)

    return retrieve_relevant_chunks(query, collection, embedder, top_k=5)

if __name__ == '__main__':
    logger.info(get_rag_from_md_notes("What is cat?"))