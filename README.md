## Overview

This project is a **plugin‑based job scheduler** with:

- **FastAPI backend** for job and plugin management, scheduling, and log streaming.
- **React + Vite frontend** (Material UI + React JSON Schema Form) for configuring jobs per user.
- A **pluggable extension system** (via `pluggy`) where each plugin defines:
  - a JSON schema for its configuration,
  - a Pydantic config model, and
  - an async `run` method that executes on a schedule.

Conceptually:

- The **`plugins` table** defines _what_ can run (Python plugin classes and their base interval).
- The **`jobs` table** defines _how_ each user runs a plugin (per‑user configs, one active at a time per (user, plugin)).
- **APScheduler** drives execution on an interval, and logs are streamed to the browser over **WebSockets**.

For a deeper dive on authoring plugins, see **[Plugin Development](./docs/PLUGIN_DEVELOPMENT.md)**.

---

## Project structure

- **Backend (FastAPI)**
  - `server.py` – creates the FastAPI app, configures the DB engine, starts/stops the `PluginManager`, and exposes:
    - `GET /plugins` – list all plugins.
    - `GET /schema/{user_id}/{plugin_id}` – plugin JSON schema + all saved configs for that user/plugin.
    - `POST /config/{job_id}` – create/update a job config.
    - `POST /activate/{job_id}/{activation}` – activate/deactivate a job.
    - `POST /delete/{job_id}` – delete a job.
    - `POST /reload/{package}` – hot‑reload a plugin class.
    - `GET /ws/logs/{plugin_id}/{user_id}` – WebSocket streaming of job logs.
  - `plugin_manager.py` – loads plugins from the DB, manages pluggy registration, sets up APScheduler jobs, activates/deactivates jobs, and forwards scheduler events to the logging system.
  - `models.py` – SQLAlchemy models:
    - `Plugin(id, package, interval, description)`
    - `Job(id, user_id, plugin_id, config, description, active)`
  - `ws_manager.py` – manages WebSocket connections keyed by `"{plugin_id}/{user_id}"` and broadcasts logs.
  - `create_data.py` – creates tables and seeds example plugins and jobs for demo/testing.
  - `scripts/database.sql` – raw schema for the `plugins` and `jobs` tables.

- **Plugins (Python)**
  - Located under `plugins/`, usually with versioned folders, for example:
    - `plugins/sample_plugin@v0_1_0/`
    - `plugins/sample_plugin@v0_2_0/`
    - `plugins/lab_plugin@v0_1_0/`
    - `plugins/stable_plugin@v0_1_0/`
    - `plugins/prod_plugin@v0_1_0/`
  - Each exposes a `Plugin`‑like class implementing the shared pluggy spec (`schema`, `config`, `run`).

- **Frontend (React + Vite)**
  - `frontend/src/App.jsx` – main UI:
    - Fetches plugins from `/plugins`.
    - Loads schema + configs from `/schema/{user_id}/{plugin_id}`.
    - Renders a JSON‑schema form for the selected job.
    - Lets you save, clone, activate, and delete jobs.
    - Shows live logs via `LogViewer`.
  - `frontend/src/LogViewer.jsx` – connects to `/ws/logs/{plugin_id}/{user_id}`, renders colored, streaming logs.
  - `frontend/src/api.ts` – small API wrapper around backend endpoints (see file for exact signatures).

---

## Prerequisites

- **Python** 3.10+ (recommended)
- **Node.js** 18+ and **yarn** (or npm) for the frontend
- A database supported by SQLAlchemy; examples include:
  - SQLite (easiest to start, including in‑memory)
  - PostgreSQL, MySQL, etc.

For in‑memory SQLite demos, set `DB_CONNECTION=sqlite:///:memory:` so `create_data.py` seeds sample data on startup.

---

## Running the application

### 1. Configure environment

Create a `.env` file in the project root (or export variables another way), for example:

```bash
DB_CONNECTION=sqlite:///./jobs.db
# Optional: allow PluginManager to import plugins from extra folders
MODULE_PATH=
# Optional: serve the built frontend from FastAPI
STATIC_FILES=./frontend/dist
```

The backend assumes `DB_CONNECTION` is set and will assert if it is missing.

### 2. Run the frontend (client)

From the `frontend` folder:

```bash
cd frontend
yarn
VITE_API_BASE_URL=http://localhost:8000 yarn dev

# build for backend
yarn build
```

By default Vite will start on `http://localhost:5173` (or the next available port).

### 3. Run the backend (server)

In the project root:

```bash
python server.py
```

This:

- Creates a SQLAlchemy engine from `DB_CONNECTION`.
- Seeds the DB with example plugins and jobs when using an in‑memory SQLite connection.
- Starts the `PluginManager` with an `AsyncIOScheduler`.
- Exposes the FastAPI app (you can point a process manager like `uvicorn` at `server:app` if preferred).

If you have already built the frontend (`yarn build`) and set `STATIC_FILES` to `frontend/dist`, the backend will also serve the compiled SPA at `/`.

---

## Developing and testing

- **Backend**: run `python server.py` directly for local development, or use:

```bash
uvicorn server:app --reload
```

- **Frontend**: run `yarn dev` in `frontend` and configure `API_BASE_URL` (in `frontend/src/api.ts`) to point at your backend (for example `http://localhost:8000` when using uvicorn defaults).

The default data seeding in `create_data.py` creates two example users and several example plugins with pre‑configured jobs so you can immediately see logs and form rendering.

---

## Horizontal scaling (multi‑node setup)

For true horizontal scaling across multiple nodes, use a shared persistent job store like **Redis** (or PostgreSQL/MySQL via `SQLAlchemyJobStore`). This allows multiple `PluginManager` instances to coordinate safely, ensuring jobs run only once even with redundant schedulers.

Example (conceptual) configuration:

```python
from apscheduler.jobstores.redis import RedisJobStore

plugin_manager = PluginManager(
    db_engine,  # your SQLAlchemy engine
    scheduler_kwargs={
        "jobstores": {
            "default": RedisJobStore(
                host="redis-host",
                port=6379,
                db=2,
            )
        },
        "job_defaults": {
            "coalesce": True,   # Merge missed runs into one
            "max_instances": 1  # Prevent duplicate executions across nodes
        },
    },
)

plugin_manager.start()
```

Each node shares the same job store; APScheduler ensures jobs respect `max_instances` across the cluster.

---

## Writing a new plugin (short version)

At a high level:

1. **Create a plugin package** under `plugins/`, e.g. `plugins/my_plugin@v0_1_0/`, with `__init__.py` and `plugin.py`.
2. In `plugin.py`, define:
   - a Pydantic `Config` model,
   - a `Plugin` class with `@hookimpl`‑decorated `schema`, `config`, and async `run` methods.
3. **Register the plugin** in the `plugins` table with:
   - `package` = the full import path to your `Plugin` class (for example, `plugins.my_plugin@v0_1_0.plugin.Plugin`),
   - `interval` = how often to run in seconds,
   - `description` = human‑readable description.
4. **Restart or reload**:
   - restart the backend, or
   - call `POST /reload/{package}` with the same `package` string to hot‑reload during development.
5. Use the **frontend UI** to:
   - select your plugin,
   - configure one or more jobs per user,
   - activate a job (only one active per (user, plugin) at a time),
   - watch logs in real time.

For a complete walkthrough (including example code and SQL), see **[Plugin Development](./docs/PLUGIN_DEVELOPMENT.md)**.


