from loguru import logger
import sys


logger.remove()

logger.add(
    sys.stdout,
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level:<8}</level> | "
        "<magenta>{name:<18}</magenta> | "
        "<cyan>{process.name:<12}</cyan> | "
        "<blue>{thread.name:<18}</blue> | "
        "{message}"
    ),
    colorize=True,
    enqueue=True,
)
