from datetime import datetime

from loguru import logger

from anagnosi.config import paths
from anagnosi.rag.llm_client import LocalTransformersLLM, OllamaLLMClient
from anagnosi.rag.prompt_generator import PromptGenerator
from anagnosi.rag.rag import (
    get_collection,
    get_embedder,
    get_rag_from_md_notes,
    sync_documents_to_collection,
)
from anagnosi.settings import settings


async def add_to_inbox(content: str, title: str, source: str) -> dict:
    inbox = paths.inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip()
    filename = f"{ts}_{safe_title.replace(' ', '_')}.md"
    filepath = inbox / filename

    metadata = f"---\ntitle: {title}\ncreated: {datetime.now().isoformat()}\nsource: {source}\n---\n\n"
    filepath.write_text(metadata + content.strip() + "\n", encoding="utf-8")

    return {"filename": filename, "path": str(filepath)}


async def answer_on_question(question: str, top_k: int = 5) -> dict:
    collection = get_collection()
    embedder = get_embedder()
    sync_documents_to_collection(collection, embedder, force_reindex=False)

    retrieved_chunks = get_rag_from_md_notes(question, top_k)

    prompt_gen = PromptGenerator()
    prompt = prompt_gen.generate(question, retrieved_chunks)

    ollama_client = None
    try:
        ollama_client = OllamaLLMClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_default_model,
            timeout=settings.ollama_default_timeout,
            temperature=settings.ollama_default_temperature,
            num_ctx=settings.ollama_default_num_ctx,
        )
        ollama_available = ollama_client._health_check()
    except Exception:
        ollama_available = False
        logger.info("Ollama is unavailable")

    answer = ""
    if ollama_available:
        try:answer = ollama_client.generate(prompt, stream=False)
        except Exception:ollama_available = False

    if not ollama_available:
        try:
            local_llm = LocalTransformersLLM(model_name="HuggingFaceTB/SmolLM2-135M-Instruct")
            answer = local_llm.generate(prompt)
        except Exception as e:answer = f"Error: Could not generate response. {str(e)}"

    return {"answer": answer, "source_chunks": retrieved_chunks, "question": question,}


def generate_answer_response(question: str, answer: str, source_chunks: list[dict], max_citations: int = 5) -> str:
    citations = []
    seen_sources = set()

    answer = _escape_markdown_v2(answer)

    for chunk in source_chunks:
        if len(citations) >= max_citations: break
        source = chunk.get("source", "unknown")
        if source not in seen_sources:
            citations.append(f"`{source}.md`")
            seen_sources.add(source)

    citation_text = ""
    if citations:
        citation_sep = " • "
        citation_text = f"\n\n_Sources: {citation_sep.join(citations)}_"

    response_text = f"{answer}{citation_text}"

    return response_text


def _escape_markdown_v2(text: str) -> str:
    if not text: return text

    escape_chars = r'_*[]()~`>#+-=|{}.!\\'

    result = []
    for char in text:
        if char in escape_chars:result.append(f'\\{char}')
        else:result.append(char)

    return ''.join(result)
