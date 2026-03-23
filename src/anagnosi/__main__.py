from loguru import logger

from src.anagnosi.structure_initialization import StructureInitializer


def main():
    initializer = StructureInitializer()
    if not initializer.init():
        logger.error("Error while initializing structure!")
        return

if __name__ == "__main__":
    main()