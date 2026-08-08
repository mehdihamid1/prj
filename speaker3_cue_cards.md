# SPEAKER 3 — CUE CARDS
### _____ · Budget: 3:00 · Keep beside your screen

---

## 🎬 0:00 — OPEN

📌 **Show gov ID. Say your name. Camera on.**

---

## 🚀 0:00–0:50 — DEPLOYMENT

**Screen → Render dashboard, then `deployed.md`, then `/health`**

> "One free-tier Render web service,
> `clearhr-agentic-hr-assistant.onrender.com`, with the
> FastAPI app and the MCP subprocess in the same service."

Open `/health` live, point at each field:

> "This is child-owned evidence, not the parent process
> guessing: `rag_status_source: mcp_child`,
> `rag_backend: dense` matching
> `configured_rag_backend: dense`,
> `dense_encoder_loaded: true`, and the deployed commit.
> `mcp_connected: true` means the stdio handshake succeeded."

Show host environment-variable screen **with values hidden**:

> "The API key only ever exists in the host's environment
> settings."

Free-tier honesty:

> "The instance sleeps after about 15 minutes. We measured
> the wake-from-idle request at **42.5 seconds**, against
> 0.24 seconds warm. That is why we warmed the service before
> recording, and it is written down in `deployed.md` rather
> than hidden. `RAG_BACKEND=lexical` is a one-variable
> rollback if the 512 MB host ever can't sustain the dense
> encoder."

---

## ⚙️ 0:50–1:30 — CI/CD

**Screen → `.github/workflows/ci.yml` + a green Actions run**

> "Every push runs ruff, an import check, a lexical index
> build, the pytest suite, a production Uvicorn app-start
> and health smoke test, and — separately — `mcp_check.py`,
> which does an independent MCP stdio discovery and a live
> tool call. That last one is what proves the MCP layer works
> outside our own app."

> "Render is gated on `autoDeployTrigger: checksPass`, so a
> red GitHub check means no deploy. The host build creates
> the dense index instead of re-running the suite, and
> `/health` reports the deployed commit so we can always tell
> which revision is live."

---

## 📊 1:30–2:35 — EVALUATION RESULTS

**Screen → `evaluation/evaluation_set.json`, then `evaluation/results.md`**

> "29 evaluation cases — policy, multi-document, workflow,
> ambiguity, safety, confirmation, and out-of-scope. Every
> question and its expected answer or rubric is in
> `design-and-evaluation.md`."

> "These numbers are three complete sequential runs against
> the **public deployed URL**, with a dense MCP child verified
> before the first case. We report the median and the observed
> range — we did not pick our best run."

### Read the table:

| Metric | Median | Range |
|--------|--------|-------|
| Behaviour accuracy | 97% | 97–100% |
| End-to-end pass rate | 76% | 66–76% |
| Answer rubric accuracy | 76% | 69–79% |
| Citation doc precision / recall | 86% / 89% | 83–87% / 89–96% |
| Citation structure valid | 100% | every run |
| Required-tool recall & coverage | 97% | 90–97% |
| Workflow completion | 61% | 44–61% |
| Confirmation / action contract | 100% | every run |
| Groundedness (auto proxy) | 90% | 90–97% |
| HTTP success | 100% | every run |
| Latency p50 / p95 (warm) | 2.76 s / 7.17 s | p95 6.1–7.4 s |

### Three things to say out loud ⚠️ graders listen for these:

**1 — The ablation:**
> "We ablated the retrieval representation. On the 20
> retrieval-labelled cases, dense retrieval reached 82%
> expected-document recall and 80% complete required-document
> coverage against lexical's 64% and 60%, with MRR .875
> versus .775. That is a retriever measurement, not a claim
> that every end-to-end answer improved."

**2 — The limitation we are not hiding:**
> "Groundedness there is an automatic proxy — it proves a
> citation resolves to an expected chunk, not that the
> sentence faithfully represents it. Human or LLM-judge
> review is recorded as open work."

**3 — The weakest number, owned:**
> "Workflow completion at 61% median is our weakest metric
> and it's the honest one to point at. Action safety and
> citation structure were 100% in every run — the system
> fails by being incomplete, not by being unsafe or by
> inventing a source."

---

## 🏁 2:35–3:00 — AI TOOLING & CLOSE

**Screen → `ai-tooling.md` briefly**

> "On tooling: Codex wrote the first draft, Claude did a
> second pass and the verification work, and `ai-tooling.md`
> records what each was good at and where it was wrong — the
> retrieval representation that collapsed on the full corpus,
> and an environment variable that silently wasn't reaching
> the MCP subprocess, are both written up there."

### Closing line:

> "To summarise: a real MCP boundary with seven discovered
> tools, cited dense retrieval over 14 synthetic policy
> documents, two multi-step workflows you saw end to end,
> mock-only confirmed actions, CI-gated deployment on a free
> tier, and 29 evaluation cases measured three times against
> the live URL. Thank you."

---

## ⛔ DO NOT

- Screen-share `.env` values or billing pages
- Skip any of the three "say out loud" eval points
- Go over 3:00
