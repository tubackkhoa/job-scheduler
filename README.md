# Job Scheduler

A modular **job scheduling and plugin execution platform** built with
**Python, FastAPI, SQLAlchemy, and Alembic**.\
The system allows dynamic installation of plugins, scheduling jobs via
cron expressions, executing them asynchronously, and storing logs and
signals for monitoring.

---

# Features

- Plugin-based job execution
- Cron-based job scheduling
- WebSocket support for real-time communication
- Job logging and indexing
- Authentication and user management
- Template rendering system
- Signal messaging between components
- Database migrations with Alembic
- Test suite for core components

---

# Architecture Overview

The system consists of several main components:

---

Component Description

---

FastAPI API Layer REST endpoints for managing jobs,
plugins, logs, users, etc

Plugin Manager Dynamically loads and manages
external plugin packages

Job Scheduler Executes scheduled jobs based on
cron expressions

Log Service Handles log storage, indexing, and
retrieval

WebSocket Manager Handles real-time client
communication

Database Layer SQLAlchemy models with Alembic
migrations

---

---

# Project Structure

    job-scheduler
    │
    ├── alembic/                # Database migration scripts
    │   ├── env.py
    │   └── versions/
    │
    ├── app/                    # FastAPI application
    │   ├── main.py             # API entrypoint
    │   ├── deps.py             # Dependency injection
    │   └── routers/            # API endpoints
    │
    ├── models.py               # SQLAlchemy models
    ├── schemas.py              # Pydantic schemas
    ├── dao.py                  # Data access layer
    │
    ├── plugin_manager.py       # Plugin installation and lifecycle
    ├── template_plugin.py      # Template plugin base
    ├── renderer.py             # Template rendering engine
    │
    ├── log_service.py          # Log storage service
    ├── log_handler.py          # Job log processing
    ├── log_indexer.py          # Log indexing
    │
    ├── ws_manager.py           # WebSocket connection manager
    ├── server.py               # Server runtime entry
    │
    ├── helpers.py              # Utility helpers
    ├── auth.py                 # Authentication logic
    ├── enforcer.py             # Access enforcement
    │
    ├── package_downloader.py   # Download plugin packages
    │
    ├── scripts/                # Admin and migration utilities
    │
    ├── tests/                  # Test suite
    │
    └── README.md

---

# Database

Database migrations are managed using **Alembic**.

Key tables:

Table Purpose

---

plugins Stores installed plugin packages
jobs Stores scheduled jobs
users Application users
signals Event messaging system
logs Job execution logs

Run migrations:

```bash
alembic upgrade head
```

---

# Installation

### 1. Clone repository

```bash
git clone <repo>
cd job-scheduler
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file:

    DB_CONNECTION=postgresql://user:password@localhost:5432/jobs
    SECRET_KEY=your_secret

### 4. Run database migrations

```bash
alembic upgrade head
```

---

# Running the Server

Start the API server:

```bash
python server.py
```

Or using uvicorn:

```bash
uvicorn app.main:app --reload
```

---

# API Modules

Main API routers:

Router Description

---

/auth Authentication endpoints
/users User management
/plugins Plugin installation and management
/jobs Job scheduling
/logs Job logs
/signals Messaging between services
/stats System statistics
/templates Template management
/chatbot Chatbot interaction
/ws WebSocket communication

---

# Plugin System

Plugins are Python packages that define executable jobs.

Responsibilities:

- Provide job execution logic
- Define configuration schema
- Emit logs and signals

The **Plugin Manager** handles:

- Downloading plugin packages
- Loading them dynamically
- Registering plugin metadata

---

# Job Scheduling

Jobs are stored in the `jobs` table and executed using cron expressions.

Example cron expression:

    */5 * * * *

Meaning: **Run every 5 minutes**

Each job references:

- `plugin_id`
- `session_id`
- `cron_expr`
- configuration data

---

# Logging System

The logging subsystem consists of:

- `log_handler.py` -- job log processing
- `log_service.py` -- log storage
- `log_indexer.py` -- search indexing

Logs allow:

- monitoring job execution
- debugging plugin behavior
- building analytics

---

# WebSocket System

Real-time features are handled through:

    ws_manager.py

Capabilities:

- client connection management
- event broadcasting
- real-time log streaming

---

# Scripts

Utility scripts for maintenance:

Script Purpose

---

seed_admin.py Create admin user
deactivate_models.py Disable models
migrate_sql_to_value_versions.py Migration utility

---

# Testing

Run tests using:

```bash
pytest
```

Test coverage includes:

- job scheduler
- plugin manager
- logging
- WebSocket manager

---

# Technologies Used

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- WebSockets
- Pytest

---

# Future Improvements

- Distributed job execution
- Plugin sandboxing
- Job retry mechanisms
- Dashboard UI
- Advanced log analytics

---

# License

MIT License
