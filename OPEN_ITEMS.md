# Open Items Before Submission

This file separates verified evidence from work that still requires an account,
a live host, or human review. It prevents a local deterministic test run—or an
old public evaluation—from being presented as evidence about a newer planner
revision.

## Verified: live LLM planner and public HTTP evaluation

Render is the submitted host. Its `/health` endpoint and 29-case public HTTP
evaluation are recorded in `deployed.md`, `evaluation/results.md`, and
`evaluation/artifacts.json`. The artifacts show real `planner: "llm"` responses
alongside deterministic safety-gate responses; they are not a fallback-only
test. The report deliberately labels that mixture rather than calling every
case an LLM decision.

The committed default is `gpt-5.6-luna`. A response proves that an LLM planner
ran, but it does not by itself prove the exact host model override or deployed
commit. Keep the host variable and deployment revision in the presenter notes;
never expose the API key.

## Blocking: deploy each planner/safety revision and re-run the public evaluation

After a change to the planner, RAG, MCP tool policy, or safety gate, deploy the
revision and run both the retrieval ablation and the public HTTP evaluation:

```bash
python -m evaluation.run_eval --ablation
python -m evaluation.run_eval --base-url https://clearhr-agentic-hr-assistant.onrender.com
```

Commit the resulting `evaluation/results.md` and `evaluation/artifacts.json`.
The remote mode records HTTP status and client-observed latency but correctly
does not claim remote citation IDs resolve to the local index. Review failures;
do not weaken an answer rubric merely to inflate a score.

## Blocking: finish public-service measurement

The current report contains a warm 29-case public run. What remains is one
cold request after Render inactivity and a fresh post-deploy run after the
current guardrail revision. Record the cold observation in `deployed.md`.

The MCP stdio subprocess is started once at service boot rather than per
request, so its ~0.6 s process-start cost is paid at startup and not on every
call. Measured locally: cold boot to a healthy `/health` is **1.7 s** against
Railway's 60 s `healthcheckTimeout`; warm `/health` is **~3 ms**. What is still
unmeasured in public is the host's wake-from-idle time and real LLM latency.

## Blocking: share the repository with the grader

Share the exact `main` commit whose GitHub Actions checks are green with the
GitHub account `quantic-grader` before submission. This access change must be
performed by the repository owner and cannot be verified from the checked-in
source.

## Blocking: record the demo

Record the required 7–10 minute screen-share presentation. Use the live,
LLM-enabled deployed service. For each of two tasks, explain the tool names,
arguments, returned results, citations, and final answer or mock action. Also
show design, deployment, CI/CD, and measured evaluation results.

## Blocking: submit the project administratively

Use the course dashboard's **Submit Project** flow after the repository is
shared, deployed, and recorded. If this is a group submission, **only one
member submits** on behalf of the group, and that person uploads the completed,
signed final page of the Group Project Agreement when the dashboard requests
it. Do not upload credentials, host screenshots containing secrets, or
non-synthetic employee information.

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
