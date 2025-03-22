FROM python:3.12-slim

WORKDIR /code

# RUN curl -sSL https://install.python-poetry.org | python3 -
RUN pip install poetry==2.1.0

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
COPY ./kelder_api/pyproject.toml /code/pyproject.toml
COPY ./kelder_api/README.md /code/README.md
COPY . /code

RUN poetry config virtualenvs.create false
RUN poetry install --no-root

#CMD ["fastapi", "run", "src/kelder_api/app/main.py", "--port", "80"]

EXPOSE 80

CMD ["poetry", "run", "uvicorn" ,"kelder_api.src.kelder_api.app.main:app","--reload", "--port", "80", "--proxy-headers", "--host", "0.0.0.0"]
#main:app --reload --port=8000 --host=0.0.0.0