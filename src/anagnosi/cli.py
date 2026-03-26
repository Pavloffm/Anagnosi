import logging
import os
import sys

import typer
from loguru import logger
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status

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
from anagnosi.structure_initialization import StructureInitializer

if not settings.debug_mode:
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    os.environ["HF_DATASETS_VERBOSITY"] = "error"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers.SentenceTransformer").setLevel(logging.ERROR)
    logging.getLogger("torch").setLevel(logging.ERROR)

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", colorize=True, backtrace=True, diagnose=True,)

app = typer.Typer(name="anagnosi", help="Anagnosi: Personal knowledge base with RAG-powered AI assistant", no_args_is_help=True, add_completion=True,)

console = Console()


@app.command("init")
def cmd_init():
    with Status("Initializing Anagnosi...", spinner="dots"):
        initializer = StructureInitializer()
        success = initializer.init()

    if success:
        console.print(Panel("Project structure ready!", style="green"))
        console.print(f"Vault location: [bold cyan]{paths.project_path}[/]")
    else:
        console.print("Initialization failed", style="red")
        raise typer.Exit(1)


@app.command("sync")
def cmd_sync(force: bool = typer.Option(False, "--force", "-f", help="Force re-index all files"),):
    with Status("Syncing documents to vector database...", spinner="dots"):
        try:
            collection = get_collection()
            embedder = get_embedder()
            sync_documents_to_collection(collection, embedder, force_reindex=force)

            console.print(Panel("[green]Sync Complete![/]\n", style="green", title="Sync Results"))
        except Exception as e:
            console.print(Panel(f"Sync failed: {e}", style="red"))
            raise typer.Exit(1) from None

@app.command("ask")
def cmd_ask(query: str = typer.Argument(..., help="Your question"), top_k: int = typer.Option(5, "--top-k", "-k", min=1, max=20, help="Number of chunks to retrieve"), stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream response token-by-token"),):
    if not (paths.project_path / ".vector_db").exists():
        console.print("No vector index found. Run [bold]anagnosi sync[/] first.", style="yellow")
        raise typer.Exit(1)

    with Status("Retrieving context...", spinner="dots"):
        retrieved_chunks = get_rag_from_md_notes(query, top_k)

    if not retrieved_chunks:
        console.print(Panel("No relevant context found. Try:\n• Running [bold]anagnosi sync[/]\n• Rephrasing your question", style="yellow"))
        return

    console.print(f"\nFound {len(retrieved_chunks)} relevant chunk(s):", style="dim")
    for i, chunk in enumerate(retrieved_chunks, 1):
        console.print(f"   {i}. [cyan]{chunk['source']}.md[/] (Chunk #{chunk['chunk_index']}) • dist: {chunk['distance']:.3f}", style="dim")

    prompt_gen = PromptGenerator()
    prompt = prompt_gen.generate(query, retrieved_chunks)

    console.print("\nAnswer:", style="bold blue")
    llm = OllamaLLMClient(base_url=settings.ollama_base_url, model=settings.ollama_default_model, timeout=settings.ollama_default_timeout, temperature=settings.ollama_default_temperature, num_ctx=settings.ollama_default_num_ctx, )

    if stream:
        full_response = []
        with Live("", console=console, refresh_per_second=20, vertical_overflow="visible") as live:
            for token in llm.generate_stream(prompt):
                full_response.append(token)
                live.update(Panel(Markdown("".join(full_response)), title="Response (streaming)", border_style="blue"))
    else:
        with Status("Generating response...", spinner="dots"):
            response = llm.generate(prompt, stream=False)
        console.print(Panel(Markdown(response), title="Response", border_style="blue"))


@app.command("ask-local")
def cmd_ask_local_llm(query: str = typer.Argument(..., help="Your question"), top_k: int = typer.Option(5, "--top-k", "-k", min=1, max=20, help="Number of chunks to retrieve"), model: str = typer.Option("HuggingFaceTB/SmolLM2-135M-Instruct", "--model", "-m", help="Override default local LLM model"), device: str = typer.Option(None, "--device", "-d", help="Override device (cuda/cpu/auto)"),):
    if not (paths.project_path / ".vector_db").exists():
        console.print("No vector index found. Run [bold]anagnosi sync[/] first.", style="yellow")
        raise typer.Exit(1)

    with Status("Retrieving context...", spinner="dots"):
        retrieved_chunks = get_rag_from_md_notes(query, top_k)

    if not retrieved_chunks:
        console.print(Panel("No relevant context found. Try:\n• Running [bold]anagnosi sync[/]\n• Rephrasing your question", style="yellow"))
        return

    console.print(f"\nFound {len(retrieved_chunks)} relevant chunk(s):", style="dim")
    for i, chunk in enumerate(retrieved_chunks, 1):
        console.print(f"   {i}. [cyan]{chunk['source']}.md[/] (Chunk #{chunk['chunk_index']}) • dist: {chunk['distance']:.3f}", style="dim")

    prompt_gen = PromptGenerator()
    prompt = prompt_gen.generate(query, retrieved_chunks)

    console.print("\nAnswer:", style="bold blue")

    console.print("[dim]Loading generation model & generating response...[/dim]")
    try:
        llm = LocalTransformersLLM(model_name=model, device=device)
        response = llm.generate(prompt)
        console.print(Panel(Markdown(response), title="Response (Local LLM)", border_style="green"))

    except Exception as e:
        console.print(Panel(f"Local LLM failed: {e}", style="red"))
        console.print("\n[yellow]Tip: Ensure you have enough RAM/VRAM for the model.[/]")
        raise typer.Exit(1) from None

if __name__ == '__main__':
    app()
