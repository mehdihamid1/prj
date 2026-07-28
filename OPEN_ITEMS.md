# Open Items Before Submission

This file separates what is already verified locally from the work that still
requires an account, a live host, or human review. It prevents the deterministic
test run from being presented as evidence about the live LLM system.

## Blocking: run the LLM planner with a real API key

The tool-use loop is covered by stubbed tests, but no real OpenAI request has
been made. The committed default is `gpt-5.6-sol`; fund the API project and
confirm that the supplied `OPENAI_API_KEY` can use that model before starting
the app and exercising both demo tasks. Confirm in each response that `planner`
is `llm`, the trace contains the expected MCP tool calls, and citations support
the final answer.

Then run the local LLM evaluation and retrieval ablation:

```bash
python -m evaluation.run_eval --ablation
```

Then run the deployed HTTP evaluation separately:

```bash
python -m evaluation.run_eval --base-url https://your-service.example
```

Commit the resulting `evaluation/results.md`. The checked-in 100% metrics are
for the local deterministic/safety paths only and must not be described as
live-LLM-agent or deployed-host results.

## Blocking: deploy and measure the public service

Deploy one service to Render or Railway using `DEPLOYMENT_GUIDE.md`. Put the
public app URL and `/health` URL in `deployed.md`. Measure and record one cold
request after inactivity plus several warm requests. Use the 29-case
`--base-url` evaluator after deployment; it records client-observed HTTP status
and latency but does not claim deployed citation IDs resolve to the local index.

The MCP stdio subprocess is started once at service boot rather than per
request, so its ~0.6 s process-start cost is paid at startup and not on every
call. Measured locally: cold boot to a healthy `/health` is **1.7 s** against
Railway's 60 s `healthcheckTimeout`; warm `/health` is **~3 ms**. What is still
unmeasured in public is the host's wake-from-idle time and real LLM latency.

## Blocking: publish the current changes and share the repository

The enhanced corpus, LLM planner, evaluation harness, and latest MCP transport
fixes are currently local changes. Commit and push them before connecting a host
or asking a grader to inspect the repository. Share `mehdihamid1/prj` with the
GitHub account `quantic-grader`.

## Blocking: record the demo

Record the required 7–10 minute screen-share presentation. Use the live,
LLM-enabled deployed service. For each of two tasks, explain the tool names,
arguments, returned results, citations, and final answer or mock action. Also
show design, deployment, CI/CD, and measured evaluation results.

## Blocking: submit the project administratively

Use the course dashboard's **Submit Project** flow after the repository is
shared, deployed, and recorded. If this is a group submission, agree on one
member to submit, and upload the completed, signed final page of the Group
Project Agreement when the dashboard requests it. Do not upload credentials,
host screenshots containing secrets, or non-synthetic employee information.

## Should improve: replace the lexical index with a model-backed vector store

The current index is a deterministic sparse hash/IDF representation stored in
JSON. It is reproducible and tested, but it is lexical—not a semantic embedding
model or conventional vector database. The rubric explicitly names embedding
models and stores such as Chroma/FAISS. For the strongest compliance story,
replace this layer with a local small embedding model plus FAISS or Chroma, then
repeat the retrieval ablation and deployment smoke test. Do this only after
checking memory and cold-start cost on the chosen free host.

## Should improve: human-check groundedness

The harness proves that a citation resolves to an expected chunk; it does not
prove the answer faithfully represents that chunk. Manually review a documented
sample of the live-LLM answers, or add a clearly labelled LLM-as-judge review,
and record the method and score in `evaluation/results.md`.

## Verified locally

- 14 synthetic policy documents in Markdown, HTML, and TXT; roughly 15,969
  words (about 32 standard manuscript pages).
- Six FastMCP tools. The deployed agent uses a real stdio MCP handshake,
  discovery, and `call_tool` requests; CI runs an independent stdio check.
- 29 evaluation cases covering policy, multi-document, workflow, ambiguity,
  safety, confirmation, and out-of-scope requests.
- Local deterministic/safety evaluation: 29/29 answer rubrics, complete
  required citations/tools, workflow completions, confirmation checks, and the
  automatic groundedness proxy pass. Measured local p50/p95 latency is
  24.2/49.3 ms; this includes the stronger section-level evidence routing and
  excludes real LLM and public-host latency.
- `pytest`, `ruff`, the production Uvicorn smoke test, and the MCP protocol
  check pass.
