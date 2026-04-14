from datetime import datetime

from anagnosi.config import paths


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
