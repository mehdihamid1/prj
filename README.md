# ClearHR: Agentic HR Policy Assistant

ClearHR is a synthetic, free-tier-friendly HR assistant built for the AI Engineering Techniques and Architectures project. An employee asks an HR question; the assistant looks up the fictional company policies and, when needed, the employee's synthetic PTO or benefits record before giving a cited answer. It provides grounded policy answers, citations, operational tool traces, and safe mock HR workflows.

## Architecture

```text
Browser /chat UI → FastAPI orchestrator → MCP tool adapter → ClearHR MCP server
                                      ↘                ↙
                           local policy index       synthetic JSON records
```

Full architecture diagram, component walkthrough, tool schemas, and design rationale live in [design-and-evaluation.md](design-and-evaluation.md).

The app builds a persistent local index from heading-aware Markdown chunks at startup. The first draft uses deterministic 256-dimension feature-hash embeddings and cosine similarity, so it is reproducible and deployable without paid services. It records document, section, chunk ID, and snippet for citations. A later version can replace `app.rag.embed` with a sentence-transformer or hosted embedding model.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`, then use `E1001` for the PTO workflow. `GET /health` verifies the app and MCP discovery; `GET /tools` shows live MCP schemas. Run `python -m pytest -q` for the RAG and real MCP discovery tests.

## MCP tools and workflows

The server uses the MCP SDK and exposes six tools: `search_policy_documents`, `get_policy_section`, `lookup_employee_profile`, `check_pto_balance`, `lookup_benefits_status`, and `create_mock_hr_ticket`. In the single-service deployment, the agent discovers and dispatches through FastMCP's registered tool manager, never direct data functions. The same server is executable over stdio with `python -m app.mcp_server`, which is the clean next step if Claude separates it into its own service.

Demo 1: “Can E1001 take three days of PTO next week?” calls policy search, profile lookup, and PTO-balance lookup; the answer cites PTO policy and says that manager approval is required.

Demo 2: “Can I work from another country for six weeks?” calls policy search and returns cited Remote Work and Security requirements. A workplace-conduct report demonstrates the confirmation-required mock ticket safety guardrail.

## Deployment: Render or Railway

This repository is configured for either platform as a **single web service**. It needs no database, persistent disk, or environment variable for the deterministic first draft.

For click-by-click instructions, use [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

### Render

Push the repository, then choose **New → Blueprint** in Render and select this repository. [render.yaml](render.yaml) declares the Python runtime, build command, start command, free plan, and `/health` check. Render will only start a release after `python -m pytest -q` passes during the build. The service listens on the platform-provided `PORT`.

### Railway

Create a Railway project from the repository. [railway.toml](railway.toml) configures Railpack, the same tested build command, the Uvicorn start command, `/health` check, and restart policy. Generate a public domain in Railway after the first successful deployment. GitHub Actions also launches the exact Uvicorn command and checks `/health` before deployment is approved.

Both hosts use the pinned Python version in [.python-version](.python-version). If an LLM is added later, set its API key only in the host’s environment-variable settings; never commit it. Free-tier cold starts can add latency because the service builds/loads the local policy index on startup.

## Evaluation

`evaluation/evaluation_set.json` starts the required evaluation set. Expand it to 20–30 items before submission, then record groundedness, citation accuracy, tool-selection accuracy, workflow-completion rate, safety pass rate, and p50/p95 warm/cold latency. Compare retrieval `TOP_K=4` against 2 and 6 as the required ablation.

## Submission checklist

Before submitting, deploy the application and update [deployed.md](deployed.md); measure and record results in [evaluation/results.md](evaluation/results.md); and share the GitHub repository with the `quantic-grader` account. The required design/evaluation detail is in [design-and-evaluation.md](design-and-evaluation.md), and the AI-tool disclosure is in [ai-tooling.md](ai-tooling.md). During the video, show each task’s returned MCP trace and explicitly explain tool names, arguments, outputs, citations, and final answer/action, followed by a short walkthrough of design, deployment, CI/CD, and evaluation results.

## AI assistance

Codex produced this initial scaffold, policy corpus, synthetic data, test setup, and documentation. Review, test, and revise all generated material before submission; Claude can be used for the next refinement pass.
