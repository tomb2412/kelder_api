FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    python3-gpiozero \
    python3-rpi.gpio \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# RUN curl -sSL https://install.python-poetry.org | python3 -
RUN pip install --no-cache-dir "poetry==2.1.0"

WORKDIR /code
COPY ./pyproject.toml /code/pyproject.toml

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # Poetry's configuration:
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local' \
    POETRY_VERSION=2.1.0

# Creating folders, and files for a project:
COPY ./README.md /code/README.md
COPY . /code

RUN poetry config virtualenvs.create false
RUN poetry install --no-root

EXPOSE 80

CMD ["poetry", "run", "uvicorn" ,"src.kelder_api.app.main:app","--reload", "--port", "80", "--proxy-headers", "--host", "0.0.0.0"]
