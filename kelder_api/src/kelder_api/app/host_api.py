import logging
import os
import secrets
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

load_dotenv()

ADMIN_USER = os.getenv("HOST_API_USERNAME")
ADMIN_PASS = os.getenv("HOST_API_PASSWORD")


def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    print(
        f"The credentials recieved: \nusername: {credentials.username}\nPassword: {credentials.password}"
    )
    if not (correct_user and correct_pass):
        raise HTTPException(401, "Unauthorized")


app = FastAPI()

RESTART_SCRIPT = Path(__file__).resolve().parents[3] / "restart_compose.sh"


@app.post("/restart", response_class=PlainTextResponse)
def restart_services(_: HTTPBasicCredentials = Depends(check_auth)):
    if not RESTART_SCRIPT.exists():
        raise HTTPException(500, f"Restart script not found: {RESTART_SCRIPT}")

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
            raise HTTPException(500, "Restart script failed:\n" + output)
        logging.INFO("Restart successful")
        return "Restart triggered successfully.\n" + output

    except Exception as e:
        raise HTTPException(500, f"Unexpected error: {e}")
