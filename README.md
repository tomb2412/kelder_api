# Kelder API Overview

This repository contains the Kelder API and supporting worker process used for vessel sensing, calculations, and data serving. The API is built with FastAPI and relies on Redis for time-series sensor storage. A background orchestrator runs sensor reads and calculations on a schedule based on vessel state.

## Running

For run scripts and developer setup notes, see the API run guide: [kelder_api/README.md](kelder_api/README.md).

## Code Structure

- `kelder_api/src/kelder_api/components`: hardware interfaces and calculators.
- `kelder_api/src/kelder_api/routes`: FastAPI route modules serving sensor and calculation data.
- `kelder_api/src/kelder_api/app`: application entrypoints and dependency wiring.
- `kelder_api/tests/notebooks`: sensor and integration notebooks.

## Main App Entry Point

The main app entry point is managed via the scripts in `kelder_api/scripts/start_app.sh` and `kelder_api/scripts/stop_app.sh`:

- `start_app.sh` optionally builds the host restart API image, starts the `host_api` container, and brings up the Docker Compose stack.
- `stop_app.sh` stops and removes the `host_api` container, brings the Compose stack down, and can optionally prune Docker resources.

Required services (from the Docker Compose stack) are:

- `redis` for time-series storage.
- `kelder_api` for the FastAPI service.
- `worker` for the background orchestrator.
- `graph_db` (Neo4j) for graph-based workflows.

## FastAPI Entry Point (`main.py`)

The API entrypoint is `kelder_api/src/kelder_api/app/main.py`. It:

- Creates a FastAPI app with a lifespan hook that wires Redis, sensor interfaces, and calculators into `app.state`.
- Registers route modules from `/routes` for GPS, compass, velocity, log, redis, bilge depth, passage planning, tidal measurements, and inference.
- Configures CORS for local deployment origins.

Key dependencies created in the lifespan include `RedisClient`, `GPSInterface`, `CompassInterface`, `VelocityCalculator`, `LogTracker`, `DriftCalculator`, `DBManager`, and `AgentWorkflow`.

## Background Orchestrator (`background_orchestrator.py`)

The worker entrypoint is `kelder_api/src/kelder_api/app/background_orchestrator.py`, which instantiates `BackgroundTaskManager` and runs it as an asyncio loop. The orchestrator:

- Registers sensors and calculators (GPS, compass, bilge depth, velocity, log, drift) in `components/background_orchestrator/orchestrator.py`.
- Selects a vessel strategy based on Redis `VESSEL_STATE` and the speed-over-ground threshold.
- Uses two strategies in `components/background_orchestrator/`:
  - `UnderwayStrategy` executes GPS, compass, and bilge depth reads, then runs velocity, log, and drift calculators.
  - `StationaryStrategy` executes GPS and bilge depth reads, then runs the velocity calculator.

When simulator mode is enabled, the orchestrator swaps real sensors for the simulator in `components/background_orchestrator/simulator.py`.

## Redis

`components/redis_client/redis_client.py` wraps `redis.asyncio` with helpers for time-series storage. Sensor and calculator writes use sorted sets with keys like `sensor:ts:<set_name>`, storing JSON payloads as members and Unix timestamps as scores. In practice, the background orchestrator triggers sensor and calculator writes, while the FastAPI routes trigger reads for UI and API consumers.

## Sensors and Calculators

### GPS Interface (`components/gps_new/interface.py`)

The GPS interface opens a serial stream with `serial_asyncio`, parses GPRMC/GPGSA/GPGSV sentences, and writes a `GPSRedisData` record into Redis. It exposes helpers to read the latest, time-series, or length-bounded history and filters active fixes when requested. Notebook: `kelder_api/tests/notebooks/gps_interface.ipynb`.

### Compass Interface (`components/compass_new/interface.py`)

The compass interface reads the LIS2MDL magnetometer over I2C, normalizes the magnetic field vector, computes a heading, and writes `CompassRedisData` to Redis. It also exposes helper methods to pull recent or time-series headings for downstream calculators.

### Ultrasound Sensor (`components/ultrasound/service.py`)

The bilge depth sensor wraps `gpiozero.DistanceSensor`, takes a distance reading, and writes a `BilgeDepth` record into Redis. Notebook: `kelder_api/tests/notebooks/ultrasound.ipynb`.

### Velocity Calculator (`components/velocity/service.py`)

The velocity calculator reads recent GPS history and computes speed-over-ground and course-over-ground using haversine distance and bearing math, then writes `GPSVelocity` to Redis. It supports history windows based on a fixed length or a time interval.

### Drift Calculator (`components/drift_calculator/serivce.py`)

The drift calculator combines the latest velocity data and a short compass heading time-series to estimate drift angle and drift speed, then persists `DriftData` to Redis. It is used by the orchestrator in the underway strategy.

### Log Tracker (`components/log/service.py`)

The log tracker correlates GPS and velocity readings, tracks journey and leg state, appends decimal-degree track points, and writes journey/leg records into Redis. It can persist completed journeys into SQLite via the DB manager.

### DB Manager (`components/db_manager/service.py`)

The DB manager encapsulates SQLite access for journey history and provides helpers to insert, list, fetch, and delete trip records stored in `assets/journey_history.db`.

## Routes

API endpoints are grouped by module in `kelder_api/src/kelder_api/routes` and expose data from Redis-backed components:

- `/gps`, `/compass`, `/velocity`, `/bilge_depth`, `/log`, `/redis`, `/health`, `/ships_status`.
- `/tidal_measurements`, `/passage_plan`, `/inference` for additional services.
