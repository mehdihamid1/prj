# Deployment Record

## URLs

- Application URL: https://clearhr-agentic-hr-assistant.onrender.com
- Health endpoint URL: https://clearhr-agentic-hr-assistant.onrender.com/health

**Host: Render.** This is the submitted deployment. Verified on 2026-07-28:
`/health` returned HTTP 200 in 402 ms with `status: ok`, `mcp_connected: true`,
and `mcp_tool_count: 6`, and `/chat` reported `planner: "llm"` — the live
LLM planner, not the deterministic fallback.

The 29-case evaluation in `evaluation/results.md` was run against this URL over
HTTP and recorded 29/29 HTTP success. Its client-observed p50/p95 latency lives
in that generated report so a later re-run cannot leave duplicate deployment
numbers out of sync; the figures include real provider time.

Treat those figures as evidence for the deployed revision that produced them,
not for later source changes. After any planner, RAG, MCP-tool-policy, or
safety change is deployed, re-run the public evaluation and replace the report
and artifacts before presenting the result.

### Dense-RAG status

The public Render service above is the lexical-RAG baseline. The repository now
contains an opt-in FastEmbed/BGE dense backend and a local retriever comparison
in [evaluation/dense_rag_comparison.md](evaluation/dense_rag_comparison.md), but
it is **not yet deployed or represented by the public LLM metrics**. A local
Python-3.11 dense process measured 292,932 KB maximum RSS; because the service also has a
FastAPI parent, dense must complete the host-memory and cold-start trial in
[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) before `RAG_BACKEND=dense` is used
for the submitted host. `RAG_BACKEND=lexical` remains the immediate rollback.

A Railway service exists from earlier testing and is **not** part of the
submission. It has no API key configured and answers on the deterministic
fallback, so it must not be used to demonstrate agentic behaviour.

### Cold start

Render's free instance sleeps after roughly 15 minutes of inactivity. The
latency above is warm. Wake the service before recording the demo, and record
one measured cold request here:

- Cold request after inactivity: **not yet measured**

## Deployment configuration

The repository includes `render.yaml` and `railway.toml`. Either creates one web service with a build command that creates the selected RAG index, runs tests, then uses the `uvicorn` start command and `/health` health check. Use only one host for the final submission, then paste its public URLs above. A healthy deployment returns HTTP 200 with `status: ok` and `mcp_connected: true`; HTTP 503 means the local MCP subprocess is unavailable and must be fixed before recording.

Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for step-by-step Render and Railway instructions.

## Free-tier notes

The first request after inactivity may be slower because the host wakes the service and starts the MCP subprocess. A dense trial additionally warms the local model in that child. Record one cold-start observation here and the 29-case warm HTTP evaluation in `evaluation/results.md` after deployment. Do not enter `OPENAI_API_KEY` or any other secret in this file.
