# Deployment Record

## URLs

- Application URL: https://clearhr-agentic-hr-assistant.onrender.com
- Health endpoint URL: https://clearhr-agentic-hr-assistant.onrender.com/health

**Host: Render.** This is the submitted deployment. Verified on 2026-07-28:
`/health` returned HTTP 200 in 402 ms with `status: ok`, `mcp_connected: true`,
and `mcp_tool_count: 6`, and `/chat` reported `planner: "llm"` — the live
LLM planner, not the deterministic fallback.

The 29-case evaluation in `evaluation/results.md` was run against this URL over
HTTP. It recorded 29/29 HTTP success with client-observed latency of
**2671 ms p50 and 4960 ms p95**, which includes real provider time.

A Railway service exists from earlier testing and is **not** part of the
submission. It has no API key configured and answers on the deterministic
fallback, so it must not be used to demonstrate agentic behaviour.

### Cold start

Render's free instance sleeps after roughly 15 minutes of inactivity. The
latency above is warm. Wake the service before recording the demo, and record
one measured cold request here:

- Cold request after inactivity: **not yet measured**

## Deployment configuration

The repository includes `render.yaml` and `railway.toml`. Either creates one web service with the tested build command, `uvicorn` start command, and `/health` health check. Use only one host for the final submission, then paste its public URLs above. A healthy deployment returns HTTP 200 with `status: ok` and `mcp_connected: true`; HTTP 503 means the local MCP subprocess is unavailable and must be fixed before recording.

Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for step-by-step Render and Railway instructions.

## Free-tier notes

The first request after inactivity may be slower because the host wakes the service and builds/loads the local policy index. Record one cold-start observation here and the 29-case warm HTTP evaluation in `evaluation/results.md` after deployment. Do not enter `OPENAI_API_KEY` or any other secret in this file.
