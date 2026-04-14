from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore",)

    app_root_path: Path = Field(default=Path.cwd(), validation_alias="APP_ROOT_PATH")
    hf_token: str = Field(default="", validation_alias="HF_TOKEN")
    debug_mode: bool = Field(default=False, validation_alias="DEBUG_MODE")


    project_dir: str = "anagnosi_vault"
    home_dir: str = "0000_home"
    inbox_dir: str = "0001_inbox"
    calendar_dir: str = "0002_calendar"
    sources_dir: str = "0003_sources"
    templates_dir: str = "0004_templates"
    attachments_dir: str = "0005_attachments"
    peoples_dir: str = "0006_peoples"
    archive_dir: str = "9999_archive"

    daily_dir: str = "0000_daily"
    weekly_dir: str = "0001_weekly"
    monthly_dir: str = "0002_monthly"
    quarterly_dir: str = "0003_quarterly"
    yearly_dir: str = "0004_yearly"

    home_file: str = "0000_home.md"

    embedding_model_name: str = Field(default="BAAI/bge-small-en-v1.5", validation_alias="EMBEDDING_MODEL_NAME")
    rag_embedding_batch_size: int = Field(default=32, validation_alias="RAG_EMBEDDING_BATCH_SIZE")

    rag_chunk_size: int = Field(default=256, validation_alias="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(default=32, validation_alias="RAG_CHUNK_OVERLAP")

    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_default_model: str = Field(default="qwen3.5:4b", validation_alias="OLLAMA_DEFAULT_MODEL")

    ollama_default_timeout: int = Field(default=120, validation_alias="OLLAMA_DEFAULT_TIMEOUT")
    ollama_default_temperature: float = Field(default=0.1, validation_alias="OLLAMA_DEFAULT_TEMPERATURE")
    ollama_default_num_ctx: int = Field(default=4096, validation_alias="OLLAMA_DEFAULT_NUM_CTX")

    telegram_bot_token: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_user_ids: str = Field(default="", validation_alias="TELEGRAM_ALLOWED_USER_IDS")
    telegram_note_prefix: str = Field(default="!", validation_alias="TELEGRAM_NOTE_PREFIX")
    telegram_auto_title_words: int = Field(default=3, validation_alias="TELEGRAM_AUTO_TITLE_WORDS")

settings = Settings()
