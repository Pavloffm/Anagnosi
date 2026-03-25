from pathlib import Path

from pydantic_settings import BaseSettings

ENV_FILE = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    app_root_path: Path = Path.cwd()
    hf_token: str = ""


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

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()