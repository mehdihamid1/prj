# SPEAKER 1 — CUE CARDS
### Hamid · Budget: 3:00 · Keep beside your screen

---

## 🎬 0:00–0:25 — OPENING (say close to verbatim)

> "Good morning. I'm Hamid, with me are _____ and _____,
> and this is ClearHR — an agentic HR assistant for a
> fictional company, Northwind Systems. It answers employee
> HR questions by retrieving from a synthetic policy corpus
> and reading synthetic employee records, and every answer
> it gives is cited and traceable.
>
> I'll cover the design and run our first agentic task;
> _____ takes the second task and our safety controls;
> _____ closes with deployment, CI/CD, and our measured
> evaluation."

📌 **Show gov ID. Say your name. Camera on.**

---

## 🏗️ 0:25–1:25 — DESIGN WALKTHROUGH

**Screen → architecture diagram from `design-and-evaluation.md`**
Point at each block as you say it.

### Block 1 — Corpus & RAG
- 14 synthetic policy documents, ~15,969 words
- 3 formats: 11 Markdown, 2 HTML, 1 plain text
- Heading-aware parsing → 142 chunks, each carries document + section
- Dense retrieval: FastEmbed `BAAI/bge-small-en-v1.5`, 384 dims, cosine, top-k 4
- Citations carry document ID, section, and snippet

### Block 2 — MCP boundary ⚠️ SAY THIS EXPLICITLY
- 7 FastMCP tools: 2 read RAG index, 4 read/draft against synthetic records, 1 health-only diagnostic (model never allowed to call it)
- Agent does **NOT** call Python functions directly
- At startup → launches FastMCP as local stdio subprocess → real MCP handshake → discovers tool schemas → sends `call_tool` via JSON-RPC
- Schemas served live at `GET /tools`

### Block 3 — Orchestration
- Every request → deterministic safety gate first
- Then clarification + scope gates
- Then LLM planner (bounded tool-use loop on `gpt-5.6-luna`)
- Rule-based planner as fallback if no key or provider fails
- LLM chooses *which* tool; MCP is *how* the call travels — separate concerns

### Trade-off one-liner:
> "It's one free-tier service, so the MCP server runs as a
> local subprocess rather than a second hosted service —
> the protocol boundary is real either way."

---

## 🖥️ 1:25–2:55 — AGENTIC TASK 1: PTO REQUEST

**Screen → live deployed app**

1. Set employee ID → **E1001**
2. Type → **Can I take three days of PTO next week?**
3. Submit

While running, say:
> "This is the live deployed service, and the response will
> report planner: llm."

### Narrate the MCP tool calls panel (in order):

| # | Tool | Say |
|---|------|-----|
| 1 | `search_policy_documents` | Read the retrieval query + `limit`. Returns chunks from `pto_policy.md`, section **Request and Approval** — planned PTO needs ≥5 calendar days' notice + manager approval |
| 2 | `lookup_employee_profile` | Args: `{"employee_id": "E1001"}`. Returns synthetic profile: manager **Morgan Lee**, New York office |
| 3 | `check_pto_balance` | Args: `{"employee_id": "E1001"}`. Returns **40 available hours** (= 5 eight-hour days) |

⚠️ **Read what actually appears.** If the LLM adds a call or words things differently, narrate the real trace.

### Point at the panels:

**Citations →**
> "`pto_policy.md`, section *Request and Approval*, with the
> snippet the answer relied on — document, section, and text,
> not just a filename."

**Final answer →**
> "It combines the policy rule with this employee's record —
> three days fits the 40-hour balance, but next week is inside
> the five-day notice window, so it tells the employee what
> approval is required. And it submits nothing. No real PTO
> request exists after this call."

---

## 🤝 HANDOFF

> "_____ will take the second task, which is a harder
> multi-policy one."

---

## ⛔ DO NOT

- Screen-share `.env`, real keys, or billing pages
- Force the trace to match this script — read what's there
- Go over 3:00
