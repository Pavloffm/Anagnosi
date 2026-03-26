from pathlib import Path

from anagnosi.settings import settings


class PathConfig:
    def __init__(self):
        self.base_path = settings.app_root_path
        self.project_path = self.base_path / settings.project_dir

        self.source_templates_dir = Path(__file__).parent.parent.parent / "src" / "templates"

        self.home_dir = self.project_path / settings.home_dir
        self.inbox_dir = self.project_path / settings.inbox_dir
        self.calendar_dir = self.project_path / settings.calendar_dir
        self.sources_dir = self.project_path / settings.sources_dir
        self.templates_dir = self.project_path / settings.templates_dir
        self.attachments_dir = self.project_path / settings.attachments_dir
        self.peoples_dir = self.project_path / settings.peoples_dir
        self.archive_dir = self.project_path / settings.archive_dir

        self.daily_dir = self.calendar_dir / settings.daily_dir
        self.weekly_dir = self.calendar_dir / settings.weekly_dir
        self.monthly_dir = self.calendar_dir / settings.monthly_dir
        self.quarterly_dir = self.calendar_dir / settings.quarterly_dir
        self.yearly_dir = self.calendar_dir / settings.yearly_dir

        self.file_home = self.home_dir / settings.home_file

        self.all_directories = [self.project_path, self.home_dir, self.inbox_dir, self.calendar_dir, self.sources_dir, self.templates_dir, self.attachments_dir, self.peoples_dir, self.archive_dir, self.daily_dir, self.weekly_dir, self.monthly_dir, self.quarterly_dir, self.yearly_dir]
        self.all_files = [self.file_home]

paths = PathConfig()