# MLflow Plugin

Manages jobs automatically based on MLflow Model Registry models.

## CLI Usage

```bash
# From project root
.venv/bin/python -m plugins.mlflow_plugin.cli [OPTIONS]
```

### Parameters

| Flag                 | Required | Default          | Description                      |
| -------------------- | -------- | ---------------- | -------------------------------- |
| `--action`           | ✅       | -                | `start` or `stop`                |
| `--plugin-name`      | ✅       | -                | Target plugin package name       |
| `--model-identify`   | ✅       | -                | Model identity (e.g., `model:1`) |
| `--api-server`       | ❌       | `localhost:8000` | Job scheduler API URL            |
| `--model-tag`        | ❌       | `uat`            | `staging`, `production`, `uat`   |
| `--webhook-api`      | ✅\*     | -                | Webhook URL (\*for `start`)      |
| `--webhook-api-key`  | ✅\*     | -                | Webhook API key (\*for `start`)  |
| `--webhook-test-key` | ❌       | -                | Webhook test key                 |
| `--session-id`       | ❌       | `1`              | Session ID                       |
| `--delete`           | ❌       | -                | Delete job after stop            |
| `--force`            | ❌       | -                | Force stop even if webhook fails |

### Environment Variables

```bash
export MLFLOW_API_SERVER="http://localhost:8000"
export MLFLOW_WEBHOOK_API="http://webhook.example.com"
export MLFLOW_WEBHOOK_API_KEY="your-key"
```

## Examples

### Start a job

```bash
.venv/bin/python -m plugins.mlflow_plugin.cli \
    --action start \
    --api-server http://localhost:8000 \
    --plugin-name "alpha_miner.plugins.UatUserCustomConfigPlugin" \
    --model-identify "xgb_model:1" \
    --webhook-api http://webhook.example.com \
    --webhook-api-key "secret-key"
```

### Stop a job

```bash
.venv/bin/python -m plugins.mlflow_plugin.cli \
    --action stop \
    --api-server http://localhost:8000 \
    --plugin-name "alpha_miner.plugins.UatUserCustomConfigPlugin" \
    --model-identify "xgb_model:1"
```

### Stop and delete

```bash
.venv/bin/python -m plugins.mlflow_plugin.cli \
    --action stop \
    --plugin-name "alpha_miner.plugins.UatUserCustomConfigPlugin" \
    --model-identify "xgb_model:1" \
    --delete
```

### Force stop (bypass webhook failures)

```bash
.venv/bin/python -m plugins.mlflow_plugin.cli \
    --action stop \
    --plugin-name "alpha_miner.plugins.UatUserCustomConfigPlugin" \
    --model-identify "xgb_model:1" \
    --force \
    --delete
```

## Help

```bash
.venv/bin/python -m plugins.mlflow_plugin.cli --help
```
