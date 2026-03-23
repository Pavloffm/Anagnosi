from pathlib import Path

from pydantic_settings import BaseSettings

from src.anagnosi.constants import ENV_FILE


class Settings(BaseSettings):
    app_root_path: Path = Path.cwd()

    dir_project: str = "vault"
    dir_inbox: str = "0000_inbox"
    dir_calendar: str = "0001_calendar"
    dir_sources: str = "0002_sources"
    dir_archive: str = "9999_archive"

    daily_dir: str = "0000_daily"
    weekly_dir: str = "0001_weekly"
    monthly_dir: str = "0002_monthly"
    quarterly_dir: str = "0003_quarterly"
    yearly_dir: str = "0004_yearly"

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()