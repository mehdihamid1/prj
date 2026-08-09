# SPEAKER 1 — CUE CARDS

### Hamid · Budget: 3:00 · Keep beside your screen

Read left to right: the **ON SCREEN** column is what your viewer should be
looking at while you say the <span style="color:#15803d">**green SAY**</span>
column. Never say a line whose screen is not up yet.

> 🟢 Open this in the **VS Code markdown preview** (`Ctrl+Shift+V`) or a browser —
> that's where the green shows. GitHub strips the colour and it reads as plain
> text, which is fine but harder to scan while recording.

---

## 🎬 0:00–0:25 — OPENING

| ON SCREEN | SAY |
| --- | --- |
| 📌 Camera on. Gov ID held up. Title slide or the app landing page. | <span style="color:#15803d">*(close to verbatim)* "Good morning. I'm Hamid, with me are \_\_\_\_\_ and \_\_\_\_\_, and this is ClearHR — an agentic HR assistant for a fictional company, Northwind Systems. It answers employee HR questions by retrieving from a synthetic policy corpus and reading synthetic employee records, and every answer it gives is cited and traceable."</span> |
| Same. | <span style="color:#15803d">"I'll cover the design and run our first agentic task; \_\_\_\_\_ takes the second task and our safety controls; \_\_\_\_\_ closes with deployment, CI/CD, and our measured evaluation."</span> |

---

## 🏗️ 0:25–1:25 — DESIGN WALKTHROUGH

**Screen for this whole beat → architecture diagram in `design-and-evaluation.md`.**
Point your cursor at the block named in the left column as you speak.

| ON SCREEN — point here | SAY |
| --- | --- |
| **Corpus & RAG block** | <span style="color:#15803d">14 synthetic policy documents, ~15,969 words, in 3 formats — 11 Markdown, 2 HTML, 1 plain text. Heading-aware parsing, so all 142 chunks carry their document and section.</span> |
| Still the RAG block; trace the arrow into the index | <span style="color:#15803d">Retrieval is dense: FastEmbed `BAAI/bge-small-en-v1.5`, 384 dimensions, cosine, top-k of 4. Citations carry document ID, section, and snippet.</span> |
| **MCP boundary block** ⚠️ the rubric's hard line — say it explicitly | <span style="color:#15803d">Seven FastMCP tools: two read the RAG index, four read or draft against synthetic records, and one is a health-only retrieval diagnostic the model is never allowed to call.</span> |
| Trace the parent → subprocess arrow | <span style="color:#15803d">The agent does **not** call Python functions directly. At startup the service launches the FastMCP server as a local stdio subprocess, completes a real MCP handshake, discovers the tool schemas, and sends `call_tool` requests over JSON-RPC.</span> |
| *(optional)* flip to `GET /tools` if you have the tab ready | <span style="color:#15803d">Schemas are served live at `GET /tools`.</span> |
| **Orchestration block**, left to right through the gates | <span style="color:#15803d">Every request passes a deterministic safety gate first, then clarification and scope gates, then the LLM planner — a bounded tool-use loop on `gpt-5.6-luna` — with a deterministic rule-based planner as fallback if there's no key or the provider fails.</span> |
| Point at planner and MCP boundary in turn | <span style="color:#15803d">The LLM chooses *which* tool; MCP is *how* the call travels. Those are separate concerns by design.</span> |
| Whole diagram, then start switching tabs | <span style="color:#15803d">"It's one free-tier service, so the MCP server runs as a local subprocess rather than a second hosted service — the protocol boundary is real either way."</span> |

---

## 🖥️ 1:25–2:55 — AGENTIC TASK 1: PTO REQUEST

| ON SCREEN — do this | SAY |
| --- | --- |
| Live deployed app → **Quick-start scenarios** → click the green **Demo 1** row. It fills the question and sets **E1001** for you — no typing. | <span style="color:#15803d">"This is the live deployed service…"</span> |
| Check the box reads *Can I take three days of PTO next week?*, then click **Ask ClearHR** | <span style="color:#15803d">"…and the response will report `planner: llm`."</span> |
| **MCP tool calls** panel, call 1 → `search_policy_documents` | <span style="color:#15803d">Read the retrieval query and the returned `limit` aloud. "Returns citable chunks from `pto_policy.md`, section **Request and Approval** — planned PTO needs at least five calendar days' notice and manager approval."</span> |
| Call 2 → `lookup_employee_profile` | <span style="color:#15803d">Read `{"employee_id": "E1001"}` aloud. "Synthetic profile: manager **Morgan Lee**, New York office."</span> |
| Call 3 → `check_pto_balance` | <span style="color:#15803d">Read `{"employee_id": "E1001"}` aloud. "Synthetic balance: **40 available hours** — five eight-hour days."</span> |
| **Retrieved citations** panel | <span style="color:#15803d">"`pto_policy.md`, section *Request and Approval*, with the snippet the answer relied on — document, section, and text, not just a filename."</span> |
| **Final answer** panel | <span style="color:#15803d">"It combines the policy rule with this employee's record — three days fits the 40-hour balance, but next week is inside the five-day notice window, so it tells the employee what approval is required. And it submits nothing. No real PTO request exists after this call."</span> |

⚠️ **Read the trace that actually appears.** A live LLM may phrase the query
differently or add a call. Narrate what's on screen — never the card.

---

## 🤝 HANDOFF

| ON SCREEN | SAY |
| --- | --- |
| Leave both panels expanded; stop sharing or hand over | <span style="color:#15803d">"\_\_\_\_\_ will take the second task, which is a harder multi-policy one."</span> |

---

## ⛔ DO NOT

- Screen-share `.env`, real keys, or billing pages
- Force the trace to match this card — read what's there
- Go over 3:00
