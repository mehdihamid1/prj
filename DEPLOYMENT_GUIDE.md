# Deploy ClearHR on Render or Railway

Choose **one** platform for the final project. Both options deploy the same single FastAPI service and use the configuration already in this repository.

Before starting, push this project to GitHub. Do not commit `.env` files or API keys. The current deterministic draft requires no secrets; if an LLM is added later, create its key as a host environment variable.

## Option A — Render

1. Sign in to [Render](https://dashboard.render.com/) and connect the GitHub account that contains this project.
2. Select **New** → **Blueprint**.
3. Select the ClearHR repository and the branch to deploy.
4. Render reads [render.yaml](render.yaml) automatically. Confirm that it creates one **Web Service** named `clearhr-agentic-hr-assistant`.
5. Confirm these values in the preview:

   | Setting | Value |
   | --- | --- |
   | Runtime | Python |
   | Plan | Free |
   | Build command | `pip install -r requirements.txt && python -m pytest -q` |
   | Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Health check | `/health` |

6. Click **Apply** / **Create Blueprint** and watch the deployment log. The build must finish with passing tests before Render starts the web service.
7. When the service is live, copy its public `https://...onrender.com` URL. Open `<service-url>/health`; it must return JSON with `"status": "ok"` and `"mcp_connected": true`.
8. Open the root URL and submit the PTO demo request: “Can I take three days of PTO next week?” with employee ID `E1001`.
9. Paste the public app and health URLs into [deployed.md](deployed.md). Note the time of the first request after inactivity as the cold-start observation.

If Render does not detect the Blueprint, create **New** → **Web Service** and enter the four values in the table manually. Keep the runtime as Python. The repository’s `.python-version` pins Python 3.11.

## Option B — Railway

1. Sign in to [Railway](https://railway.app/) and create a **New Project**.
2. Select **Deploy from GitHub repo**, authorize GitHub if prompted, and select the ClearHR repository and branch.
3. Railway reads [railway.toml](railway.toml). In the service’s deployment settings, confirm:

   | Setting | Value |
   | --- | --- |
   | Builder | Railpack |
   | Build command | `pip install -r requirements.txt && python -m pytest -q` |
   | Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Health check path | `/health` |
   | Health check timeout | 60 seconds |

4. Start the deployment and watch the logs. Do not change `PORT`; Railway supplies it automatically.
5. After a successful deployment, open the service’s **Settings** → **Networking** and choose **Generate Domain**.
6. Open `<railway-domain>/health`. It must return `"status": "ok"` and `"mcp_connected": true`.
7. Open the root URL and run the PTO demo with employee ID `E1001`.
8. Paste the public app and health URLs into [deployed.md](deployed.md), including any observed cold-start behavior.

## After either deployment

1. Record the public URLs in `deployed.md` and commit that update.
2. Run the full 20–30-question evaluation set against the public URL; record measured results in `evaluation/results.md`.
3. Confirm GitHub Actions is green on the deployed branch.
4. Share the repository with GitHub account `quantic-grader`.
5. Use the deployed URL in the recorded demo. For each task, show the returned MCP trace, tool arguments and outputs, citations, and final answer/action.

## If the deployment fails

- **Build failure:** confirm the log shows `pip install -r requirements.txt` followed by passing tests. Do not deploy around a failing test.
- **Health-check failure:** confirm the start command exactly matches this guide and that the check path is `/health`, not `/`.
- **Service is up but chat fails:** open `/health` first. If `mcp_connected` is false, inspect the platform logs and redeploy after fixing the logged error.
- **Slow first request:** this is expected on a free service after inactivity. Record it in `deployed.md` and measure it separately from warm latency.
