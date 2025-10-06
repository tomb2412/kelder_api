import asyncio
import logging

from src.kelder_api.components.background_orchestrator.orchestrator import (
    BackgroundTaskManager,
)


logger = logging.getLogger(__name__)
logging.basicConfig(
    # filename=(
    #     f"/app/logs/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_kelder_api.log"
    # ),
    encoding="utf-8",
    format="WORKER - {levelname} - {asctime} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

if __name__ == "__main__":
    task_manager = BackgroundTaskManager()
    asyncio.run(task_manager.run())
