# Deployment Record

## URLs

- Application URL: https://web-production-32831.up.railway.app
- Health endpoint URL: https://web-production-32831.up.railway.app/health

Host: Railway. Verified on 2026-07-28: `/health` returned HTTP 200 in 274 ms
with `status: ok`, `mcp_connected: true`, and `mcp_tool_count: 6`.

The service currently runs the deterministic planner; `ANTHROPIC_API_KEY` is not
yet set in the host variables, so `/chat` reports `planner: "deterministic"`.
Re-verify and update this note once the key is added.

## Deployment configuration

The repository includes `render.yaml` and `railway.toml`. Either creates one web service with the tested build command, `uvicorn` start command, and `/health` health check. Use only one host for the final submission, then paste its public URLs above. A healthy deployment returns HTTP 200 with `status: ok` and `mcp_connected: true`; HTTP 503 means the local MCP subprocess is unavailable and must be fixed before recording.

Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for step-by-step Render and Railway instructions.

## Free-tier notes

The first request after inactivity may be slower because the host wakes the service and builds/loads the local policy index. Record one cold-start observation here and the 29-case warm HTTP evaluation in `evaluation/results.md` after deployment. Do not enter `ANTHROPIC_API_KEY` or any other secret in this file.
