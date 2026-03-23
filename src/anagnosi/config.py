from pathlib import Path

from src.anagnosi.settings import settings


class PathConfig:
    def __init__(self):
        self.base_path = settings.app_root_path
        self.project_path = self.base_path / settings.dir_project

        self.inbox = self.project_path / settings.dir_inbox
        self.calendar = self.project_path / settings.dir_calendar
        self.sources = self.project_path / settings.dir_sources
        self.archive = self.project_path / settings.dir_archive
        self.logs = self.base_path / "logs"

        self.daily = self.calendar / settings.daily_dir
        self.weekly = self.calendar / settings.weekly_dir
        self.monthly = self.calendar / settings.monthly_dir
        self.quarterly = self.calendar / settings.quarterly_dir
        self.yearly = self.calendar / settings.yearly_dir

        self.all_directories = [self.project_path,self.inbox,self.calendar,self.sources,self.archive,self.logs,self.daily,self.weekly,self.monthly,self.quarterly,self.yearly]

paths = PathConfig()