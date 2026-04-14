import re
from datetime import datetime

from loguru import logger
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from anagnosi.connections.manager import ConnectionManager
from anagnosi.connections.operations import add_to_inbox
from anagnosi.settings import settings


def _is_allowed_user(update: Update) -> bool:
    allowed_ids = getattr(settings, 'telegram_allowed_user_ids', [])
    user = update.effective_user
    if not user: return False
    return str(user.id) in allowed_ids

def _generate_auto_title(content: str, max_words: int = 3) -> str:
    clean = re.sub(r'[^\w\s\u0400-\u04FF\u00C0-\u024F]', ' ', content)
    words = clean.strip().split()
    if not words: return f"note_{datetime.now().strftime('%H%M%S')}"
    title = " ".join(words[:max_words])
    return title[:50] + ("..." if len(title) > 50 else "")


def _extract_content(text: str) -> str | None:
    prefix = getattr(settings, 'telegram_note_prefix', '!').strip()
    if not text or not text.strip(): return None
    stripped = text.strip()
    if stripped.startswith(prefix):
        content = stripped[len(prefix):].strip()
        return content if content else None
    return None


async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed_user(update):
        logger.warning(f"Unauthorized access attempt from user_id={update.effective_user.id}")
        return

    content = _extract_content(update.message.text)
    if not content: return

    status = await update.message.reply_text("⏳")

    try:
        manager = ConnectionManager()
        await manager.start()
        try:
            title = _generate_auto_title(content, getattr(settings, 'telegram_auto_title_words', 3))
            result = await manager.run(add_to_inbox, content=content, title=title, source="telegram")
            preview = content[:80] + ("…" if len(content) > 80 else "")
            await status.edit_text(f"<code>{result['filename']}</code>\n<i>{preview}</i>", parse_mode="HTML")
            logger.info(f"Telegram note saved: {result['filename']}")
        finally:
            await manager.stop()
    except Exception as e:
        logger.error(f"Telegram save failed: {e}")
        await status.edit_text(f"{str(e)}")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)


def main() -> None:
    if not getattr(settings, 'telegram_bot_token', None):
        logger.info("Set TELEGRAM_BOT_TOKEN in .env")
        return

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note))

    logger.info(f"Bot running (prefix: '{getattr(settings, 'telegram_note_prefix', '!')}')")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
