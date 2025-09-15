# kelder_api
API to serve Kelder sensing features and ship controlfas


# Installation

1. Install wsl Ubuntu 24.04 and the update kernel
2. Install Docker Desktop and activat for wsl 2
3. Clone repo
4. Install pyenv `curl https://pyenv.run | bash`, and create `virtualenv` and activate a new enviroment
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
`poetry run uvicorn src.kelder_api.app.main:app --reload --port=8000 --host=0.0.0.0`

# Run Docker
- build docker container `sudo docker build -t kelder_api .`
- run the docker container `sudo docker run --rm --privileged --tty --volume /dev:/dev -p 8000:80 kelder_api`
- usefull docker commands `sudo docker ps`, `sudo docker kill container name`, `sudo docker exec -it <container name> bash`, logs: `cd /app/logs`

- docker compose `docker compose up --build`
- To see the keys `docker compose exec redis redis-cli`  and then `KEYS *`. GPS history: `docker compose exec redis redis-cli LRANGE gps:History 0 10`

w- Docs are available at: http://localhost:8000/docs#/ or http://raspberrypi.local:8000/docs#/ or http://192.168.1.167:8000/docs#/


# Connecting to the Pi

- SSH ip address: `ssh tom@192.168.1.167` password: tom
- Activate virtual enviroment: `pyenv activate kelder_api_env`

# Packages

- docker `sudo apt install docker.io`


# Troubleshooting
- poetry hangs. Run command verbose -vvv. For keyring `poetry config keyring.enabled false`


# The GPS Module

- Component NEO-6M GPS [data sheet](https://components101.com/sites/default/files/component_datasheet/NEO6MV2%20GPS%20Module%20Datasheet.pdf)
- NMEA GPRMB data: [GPRMB structure](https://aprs.gids.nl/nmea/#rmc)
- pynmea2 parsing data: [git hub](https://github.com/Knio/pynmea2)
- Minicom command to see serial stream: 
    - to see which divice: `ls /dev/ttyAMA* /dev/ttyS* /dev/ttyUSB*`
    - `sudo minicom -b 9600 -o -D /dev/ttyAMA0`

# The Ultasound
 - [Wiring guide](https://gpiozero.readthedocs.io/en/stable/recipes.html#distance-sensor)
 - [Module docs](https://gpiozero.readthedocs.io/en/stable/api_input.html#distancesensor-hc-sr04)
 - install package: `sudo apt install python3-gpiozero python3-rpi.gpio`
 - Enable gpio through the interface options `sudo raspi-config` -> Go to Interface Options -> Enable GPIO
 - Resistor guide:
    - 


 # The Compass
 - [wiring documentation](https://learn.adafruit.com/lsm303-accelerometer-slash-compass-breakout/python-circuitpython)
 - [datasheet](https://www.mouser.com/datasheet/2/389/lsm303agr-954987.pdf)
 - Ensure the sensor is correctly wired with `sudo i2cdetect -y 1`

 # The Wind Sensor

 - [RS458 Wind sensor](https://www.aliexpress.com/w/wholesale-wind-sensor-rs485.html)
 

 # The Cellular Modem

 - [Clipper HAT Mini](https://learn.pimoroni.com/article/getting-started-with-clipper-hat)