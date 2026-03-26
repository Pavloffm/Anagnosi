from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore",)

    app_root_path: Path = Field(default=Path.cwd(), validation_alias="APP_ROOT_PATH")
    hf_token: str = Field(default="", validation_alias="HF_TOKEN")


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

    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_default_model: str = Field(default="qwen3.5:4b", validation_alias="OLLAMA_DEFAULT_MODEL")

    ollama_default_timeout: int = Field(default=120, validation_alias="OLLAMA_DEFAULT_TIMEOUT")
    ollama_default_temperature: float = Field(default=0.1, validation_alias="OLLAMA_DEFAULT_TEMPERATURE")
    ollama_default_num_ctx: int = Field(default=4096, validation_alias="OLLAMA_DEFAULT_NUM_CTX")

settings = Settings()
