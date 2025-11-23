import asyncio
import logging

from src.kelder_api.components.background_orchestrator.orchestrator import (
    BackgroundTaskManager,
)
from src.kelder_api.configuration.logging_config import setup_logging

setup_logging(component="background_orchestrator")
logger = logging.getLogger("background_orchestrator")

if __name__ == "__main__":
    logger.info("Starting background orchestrator worker")
    task_manager = BackgroundTaskManager()
    try:
        asyncio.run(task_manager.run())
    except Exception:
        logger.exception("Background orchestrator stopped unexpectedly")
        raise
