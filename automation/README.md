# Automation & Workflows

## Overview
This folder contains all automation-related content:
- **Workflow definitions** in `workflows/`
- **n8n configuration** and MCP setup
- **Automation documentation** and references

## Deployment
**All services (including n8n, API, Frontend, PostgreSQL, MCP) are now deployed from the root `docker-compose.yml`.**

### Start all services from root:
```bash
cd .. # Go to project root
docker-compose up -d
```

This merges:
- ✅ n8n workflow engine (port 5679)
- ✅ n8n MCP bridge (for AI integration)
- ✅ PostgreSQL database (shared)
- ✅ FastAPI backend (port 8000)
- ✅ Next.js frontend (port 3001)

## Configuration
Configuration is centralized in the root `.env`:
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (database)
- `N8N_ENCRYPTION_KEY` (n8n security)
- `N8N_API_KEY` (n8n API access)

Generate an encryption key with:
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

## MCP Bridge Setup
- **File**: `mcp-config.json` (for Claude, Cursor, or VS Code)
- **Requires**: n8n API enabled in web UI
- **Setup**:
  1. Open http://localhost:5679 (from root deployment)
  2. Go to `Settings -> API`
  3. Enable API and create a key
  4. Copy key to root `.env` as `N8N_API_KEY`

## Workflows
- **Location**: `workflows/` directory
- **Content**: JSON workflow definitions for n8n
- **Import**: Load these into n8n from the web UI or via API

## References
- See `docker-compose.yml` for legacy local-only setup (archived reference)
- See `REFERENCE.md` for additional documentation
4. Put that key into `automation/.env.automation` as `N8N_API_KEY=...`.
5. Start the MCP bridge:

```bash
docker compose --env-file .env.automation up -d n8n_mcp
```

Check logs if needed:

```bash
docker compose logs n8n_mcp
```

## Connect AI tools
Use the content of `mcp-config.json` in:
- Claude Desktop: `%APPDATA%\\Claude\\claude_desktop_config.json`
- Cursor: `%APPDATA%\\Cursor\\User\\globalStorage\\cursor.mcp\\mcp.json`
- VS Code Copilot: `settings.json` under `github.copilot.advanced.mcp.servers`

Restart the tool after updating its MCP config.

## Verify
Useful checks:

```bash
docker compose --env-file .env.automation ps
docker compose --env-file .env.automation logs n8n
docker compose --env-file .env.automation logs n8n_mcp
```

If MCP is connected correctly, your client should be able to call n8n through the running `n8n_mcp` container.

## Useful commands

```bash
docker compose --env-file .env.automation down
docker compose --env-file .env.automation restart n8n
docker compose --env-file .env.automation pull
docker compose --env-file .env.automation up -d
docker compose --env-file .env.automation logs -f n8n
```

## OpenRouter in n8n
OpenRouter is configured inside the n8n UI, not in this Docker stack:
1. In n8n, create a new OpenAI-compatible credential.
2. Set Base URL to `https://openrouter.ai/api/v1`.
3. Set your OpenRouter API key.
4. Use that credential in AI Agent or LLM nodes.

## Notes
- n8n is exposed directly on `localhost:5678`.
- `n8n_mcp` talks to `http://n8n:5678` over the Docker network.
- This folder is ready for local orchestration work, but it is not yet wired to `main.py` or your RH pipeline.

## Pipeline Automation (Template)
This folder includes a starter workflow you can import into n8n:

- `automation/workflows/pipeline_start_webhook.json`
- `automation/workflows/notify_matching_complete_slack.json`
- `automation/workflows/notify_final_complete_slack.json`
- `automation/workflows/notify_pipeline_events_slack.json`

It defines a minimal intake via Webhook and forwards the request to a pipeline API:
- `POST $PIPELINE_API_URL` (defaults to `http://host.docker.internal:8000/api/v1/jobs`)

### Import
1. Open n8n.
2. Import the workflow JSON.
3. Open the `Webhook Intake` node and copy the generated webhook URL.
4. Update the `Start Pipeline` node if your API URL differs.

For Slack notifications:
1. Import `notify_matching_complete_slack.json`.
2. Open the `Send Slack` node and set your Slack Incoming Webhook URL.
3. Open `Matching Complete Webhook` node and copy the webhook URL.
4. Set `N8N_MATCHING_WEBHOOK_URL` in your environment before starting the API:
   - `N8N_MATCHING_WEBHOOK_URL=<copied webhook URL>`

For final result notifications:
1. Import `notify_final_complete_slack.json`.
2. Open the `Send Slack` node and set your Slack Incoming Webhook URL.
3. Open `Final Complete Webhook` node and copy the webhook URL.
4. Set `N8N_FINAL_WEBHOOK_URL` in your environment before starting the API:
   - `N8N_FINAL_WEBHOOK_URL=<copied webhook URL>`

For a single webhook (recommended):
1. Import `notify_pipeline_events_slack.json`.
2. Open both `Send Slack` nodes and set your Slack Incoming Webhook URL.
3. Open `Pipeline Events Webhook` node and copy the webhook URL.
4. Set `N8N_PIPELINE_WEBHOOK_URL` in your environment before starting the API:
   - `N8N_PIPELINE_WEBHOOK_URL=<copied webhook URL>`
5. The workflow routes `matching_complete`, `final_complete`, and `format_complete` events.

### Expected API contract (V1)
`POST /api/v1/jobs` accepts `multipart/form-data`:
- `job_offer` (file)
- `cv_files` (multiple files)
- `archive` (boolean)

### Start the API (local)
From repo root:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r service/requirements.txt
uvicorn service.api:app --host 0.0.0.0 --port 8000
```

### Notes
- The current template forwards a single binary field (`job_offer`). Once the API exists, add `cv_files` as additional binary fields.
- If you want a no-code UI, replace the Webhook node with a `Form Trigger` node and map the uploaded files to the API request.
