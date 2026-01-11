import logging
import os
import secrets
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# Configure logging to dedicated host_api log and aggregate logs
from src.kelder_api.configuration.logging_config import setup_logging  # noqa: E402

security = HTTPBasic()
load_dotenv()

ADMIN_USER = os.getenv("HOST_API_USERNAME")
ADMIN_PASS = os.getenv("HOST_API_PASSWORD")

RESTART_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "restart_compose.sh"
LOG_DIR = Path("/logs")


setup_logging("host_api", LOG_DIR)
logger = logging.getLogger("host_api")
logger.info("Host restart API initialised")
logger.info(f"\nuser_name: {ADMIN_USER}\npassword: {ADMIN_PASS}")


def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (correct_user and correct_pass):
        logger.info(f"{type(credentials.username)}")
        logger.warning(
            f"Unauthorized restart attempt with\n username: {credentials.username}\npassword: {credentials.password}"
        )
        raise HTTPException(401, "Unauthorized")
    logger.debug("Authentication succeeded")


app = FastAPI()


@app.post("/restart", response_class=PlainTextResponse)
def restart_services(_: HTTPBasicCredentials = Depends(check_auth)):
    logger.info("Restart request received")

    if not RESTART_SCRIPT.exists():
        msg = f"Restart script not found: {RESTART_SCRIPT}"
        logger.error(msg)
        raise HTTPException(500, msg)

    try:
        result = subprocess.run(
            [str(RESTART_SCRIPT)], capture_output=True, text=True, check=False
        )

        output = (
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}\n"
            f"RETURN CODE: {result.returncode}"
        )

        if result.returncode != 0:
            logger.error("Restart script failed with return code %s", result.returncode)
            logger.debug(output)
            raise HTTPException(500, "Restart script failed:\n" + output)
        logger.info("Restart successful")
        logger.debug(output)
        return "Restart triggered successfully.\n" + output

    except Exception as e:
        logger.exception("Unexpected error during restart")
        raise HTTPException(500, f"Unexpected error: {e}")
