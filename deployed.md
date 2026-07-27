# Deployment Record

## URLs

- Application URL: **Not deployed yet**
- Health endpoint URL: **Not deployed yet**

Replace both values after deployment. Example: `https://clearhr.example.com` and `https://clearhr.example.com/health`.

## Deployment configuration

The repository includes `render.yaml` and `railway.toml`. Either creates one web service with the tested build command, `uvicorn` start command, and `/health` health check. Use only one host for the final submission, then paste its public URLs above.

Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for step-by-step Render and Railway instructions.

## Free-tier notes

The first request after inactivity may be slower because the host wakes the service and builds/loads the local policy index. Record measured cold- and warm-start latency in `evaluation/results.md` after deployment.
