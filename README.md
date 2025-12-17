## Running the Application

### 1. Run the Frontend (Client)

```bash
cd alpha-miner-ui
yarn
yarn dev
```

### 2. Run the Backend (Server)

```bash
# Optional: Create initial database and sample data (only needed the first time or to reset)
python create_data.py

# Start the server
python server.py
```

## Horizontal Scaling (Multi-Node Setup)

For true horizontal scaling across multiple nodes, use a shared persistent job store like **Redis** (or PostgreSQL/MySQL via SQLAlchemyJobStore). This allows multiple `PluginManager` instances to coordinate safely, ensuring jobs run only once even with redundant schedulers.

```python
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

# Advanced: Use Redis for true multi-node scaling
plugin_manager = PluginManager(
    db_connection="postgresql://user:pass@host/db",  # Optional: for other DB needs
    scheduler_kwargs={
        'jobstores': {
            'default': RedisJobStore(
                host='redis-host',     # Or 'host': 'redis-host'
                port=6379,
                db=2                   # Redis database index
            )
        },
        # enforces safe defaults automatically
        'job_defaults': {
            'coalesce': True,      # Merge missed runs into one
            'max_instances': 1     # Prevent duplicate executions across nodes
        }
    }
)

plugin_manager.start()

```
