# ClearHR: Agentic HR Policy Assistant

ClearHR is a synthetic, free-tier-friendly HR assistant built for the AI Engineering Techniques and Architectures project. An employee asks an HR question; the agent decides which tools it needs, retrieves the relevant company policy, looks up the employee's synthetic PTO or benefits record when the question calls for it, and answers with citations plus a trace of every tool call it made.

Every policy and every employee record in this repository is fictional.

**Deployed URL:** see [deployed.md](deployed.md).

## Architecture

```text
Browser /chat UI → FastAPI → agent orchestrator → MCP client
                                   │                  │
                              OpenAI API        ══ MCP boundary ══
                            (tool selection)           │
                                              ClearHR MCP server
                                                ↙            ↘
                                    policy RAG index    synthetic records
```

The orchestrator never reads the policy index or the employee records directly. Its only route to either is a tool call dispatched through the MCP layer. Full diagrams, tool schemas, and design rationale are in [design-and-evaluation.md](design-and-evaluation.md).

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; add OPENAI_API_KEY to enable the LLM planner
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` and try `E1001` with *"Can I take three days of PTO next week?"*.

| Endpoint | Purpose |
| --- | --- |
| `POST /chat` | Answer, citations, and tool-call trace |
| `GET /health` | App status and MCP connectivity |
| `GET /tools` | Live MCP tool schemas as discovered by the agent |

**Without an API key the app still runs.** It falls back to a deterministic rule-based planner over the same MCP tools, so every endpoint works and the test suite passes with no credentials. With `OPENAI_API_KEY` set, an LLM chooses the tools instead. In that mode, the user prompt and the tool schemas/results needed for the turn are sent to OpenAI; use this only with the repository's synthetic coursework data. Before recording the demo, use a real key and a model identifier accepted by your OpenAI account, then rerun the evaluation.

If a non-empty key produces `planner: "deterministic-fallback"`, the provider call failed after the fallback path was selected. Inspect the secure host log for the exact exception. For temporary local troubleshooting, set `EXPOSE_PLANNER_ERRORS=true`; the response then includes only the exception class, HTTP status, and provider error code—not raw provider text. Turn it off before a public demo or deployment.

## Corpus

14 synthetic policy documents, 15,969 words, in three formats — 11 Markdown, 2 HTML, 1 plain text — covering PTO, holidays, remote work, expenses, travel, equipment, benefits, leave, onboarding, data security, workplace conduct, compensation, performance, and health and safety. All three formats are parsed heading-aware so citations carry a real section name. The index is rebuilt deterministically at startup; there is no seed to set.

## MCP tools

Six tools: `search_policy_documents`, `get_policy_section`, `lookup_employee_profile`, `check_pto_balance`, `lookup_benefits_status`, and `create_mock_hr_ticket`. Two read the RAG index, four read or draft against synthetic records. Schemas are generated from type hints and served live at `/tools`. See [mcp/README.md](mcp/README.md).

The deployed web service starts the MCP server as a local subprocess and calls it over stdio. It remains one free-tier service, but tool execution still crosses a real MCP protocol boundary:

```bash
python -m app.mcp_server          # run as a real MCP process
python scripts/mcp_check.py       # CI proof: handshake, list_tools, two real tool calls
```

## Demo tasks

1. **PTO request** — `E1001`, *"Can I take three days of PTO next week?"* The agent calls `search_policy_documents`, `lookup_employee_profile`, and `check_pto_balance`, then reports the 40-hour balance, names the approving manager, and cites the five-calendar-day notice requirement.
2. **International remote work** — `E1003`, *"I am based in California and want to work from Portugal for six weeks. What approvals and security requirements apply?"* The agent combines policy retrieval with the synthetic employee profile, then cites the remote-work and data-security evidence.

A workplace-conduct report additionally demonstrates the safety gate and the confirmation-required mock ticket.

Use [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) when recording: it gives the exact screen sequence and the MCP evidence to narrate for each task.

## Testing and CI

```bash
python -m pytest -q                 # RAG, MCP, planner-loop, API, and evaluation tests
ruff check app tests evaluation scripts
python scripts/smoke_test.py        # boots the production command, checks /health
python scripts/mcp_check.py         # stdio MCP discovery and live tool call
```

GitHub Actions runs all of the above on push and pull request.

## Deployment: Render or Railway

Configured for either platform as a **single web service**, with no database and no persistent disk. Click-by-click instructions are in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

- **Render** — *New → Blueprint*, select this repository. [render.yaml](render.yaml) declares the runtime, build and start commands, free plan, and `/health` check.
- **Railway** — create a project from the repository. [railway.toml](railway.toml) configures Railpack, the same build command, and the health check. Generate a public domain after the first successful deploy.

Deployment is gated by the host build command, which runs `python -m pytest -q` — a failing test fails the build, and a failed build never replaces the running service. On Render, [render.yaml](render.yaml) additionally uses `autoDeployTrigger: checksPass`, so automatic deploys wait for GitHub checks; Railway uses the tested host build as its in-host gate. Set `OPENAI_API_KEY` and, if needed, `OPENAI_MODEL` in the host's environment-variable settings only; never commit them. The running app launches and calls its MCP server over stdio, even in the single-service deployment. `/health` returns HTTP 503 if that MCP connection is unavailable, so a broken tool service cannot appear healthy. Free-tier cold starts add latency because the service builds the policy index on first start.

`/chat` also has a small process-local cost guard by default (30 requests per client and 60 total per 60 seconds). It is suitable for a one-instance coursework demo, not a replacement for authentication, an edge rate limiter, or a production privacy review.

## Sharing with classmates safely

Use [COLLABORATION_GUIDE.md](COLLABORATION_GUIDE.md) before inviting collaborators or sharing a copy of the project. It covers safe local setup, which data is synthetic, GitHub access limitations, secret handling, and the response if a key is exposed.

## Evaluation

```bash
python -m evaluation.run_eval              # writes results.md and synthetic artifacts.json
python -m evaluation.run_eval --ablation   # local retrieval sweep: TOP_K = 1 / 2 / 4 / 6 / 8
python -m evaluation.run_eval --base-url https://your-service.example
```

29 cases span single-document policy questions, multi-document questions, tool-requiring workflows, ambiguous requests, safety escalation, both unconfirmed and confirmed mock actions, and out-of-scope refusals. The harness checks explicit answer rubrics, complete citation/tool coverage, action confirmation, a groundedness proxy, and p50/p95 latency. `--base-url` measures the deployed HTTP service and does not falsely claim its citation IDs resolve to the local index. It saves synthetic per-case answer/citation/trace evidence to [evaluation/artifacts.json](evaluation/artifacts.json) for human review. See [evaluation/results.md](evaluation/results.md).

## Submission checklist

- [ ] Deploy and fill in [deployed.md](deployed.md) with the live URL and `/health` URL
- [ ] Re-run the evaluation with `OPENAI_API_KEY` set and commit [evaluation/results.md](evaluation/results.md)
- [ ] Share the repository with the `quantic-grader` GitHub account
- [ ] Record the 7–10 minute demo: two agentic tasks end to end, narrating tool names, arguments, outputs, citations, and the final answer, then a walkthrough of design, deployment, CI/CD, and evaluation

Known gaps, unverified paths, and deliberate trade-offs are tracked in [OPEN_ITEMS.md](OPEN_ITEMS.md), including the still-required live LLM and deployed-host evaluations.

## AI assistance

Codex produced the initial scaffold; Claude Code did the second pass. Both are documented in [ai-tooling.md](ai-tooling.md).
