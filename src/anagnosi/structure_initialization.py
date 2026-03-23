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

            logger.debug("End of project structure initialization.")
            return True
        except Exception as e:
            logger.error(f"Error in initializing the project structure: {e}")
            return False