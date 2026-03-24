import shutil

from loguru import logger

from src.anagnosi.config import paths


class StructureInitializer:
    def init(self) -> bool:
        try:
            logger.debug("Start of project structure initialization.")
            for path in paths.all_directories:
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"Create unexist folder: {path.relative_to(paths.base_path)}")

            for file_path in paths.all_files:
                if not file_path.exists():
                    file_path.write_text("")
                    logger.debug(f"Create unexist file: {file_path.relative_to(paths.base_path)}")

            self._copy_templates()

            logger.debug("End of project structure initialization.")
            return True
        except Exception as e:
            logger.error(f"Error in initializing the project structure: {e}")
            return False

    def _copy_templates(self) -> None:
        source_templates_dir = paths.source_templates_dir
        dest_templates_dir = paths.templates_dir

        if not source_templates_dir.exists():
            logger.error(f"Source templates directory not found: {source_templates_dir}")
            return

        for src_file in source_templates_dir.glob("*.md"):
            dest_file = dest_templates_dir / src_file.name

            if not dest_file.exists():
                shutil.copy2(src_file, dest_file)
                logger.info(f"Copied template: {src_file.name}")
            else:
                logger.debug(f"Template already exists, skipping: {src_file.name}")