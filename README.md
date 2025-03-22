# kelder_api
API to serve Kelder sensing features and ship controlfas


# Installation

1. Install wsl Ubuntu 24.04 and the update kernel
2. Install Docker Desktop and activat for wsl 2
3. Clone repo
4. Install pyenv, and create `virtualenv` and activate a new enviroment
    - 4.1. `vim basch file`
    - 4.2. `i` - insert mode. `esc` - escape. `:wq` - save and exit.
    - 4.3 Paste in export prompts
5. Install pipx with:
    `sudo apt update`
    `sudo apt install pipx`
    `pipx ensurepath`
    `sudo pipx ensurepath`
6. Install poetry: `pipx install poetry` `pipx upgrade poetry`
7. Build docker image: `docker build -t kelder_api .`
8. Free excess memory consumption `wsl --shutdown` 


# Run local 
- from the app directory, poetry install and virtual enviroment:
`poetry run uvicorn main:app --reload --port=8000 --host=0.0.0.0`
- run the docker container `docker run -p 8000:80 kelder_api`

- Docs are available at: http://localhost:8000/docs#/