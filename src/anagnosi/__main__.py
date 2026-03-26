from loguru import logger
from anagnosi.structure_initialization import StructureInitializer


def main():
    initializer = StructureInitializer()
    if not initializer.init():
        logger.error("Failed to initialize project structure")
        return


if __name__ == "__main__":
    main()