# SPEAKER 2 — CUE CARDS
### Mehdi · Budget: 3:00 · Keep beside your screen

---

## 🎬 0:00–0:10 — OPENING

📌 **Show gov ID. Say your name. Camera on.**

> "I'm Mehdi. Our second task needs more than one policy
> document and the employee's location record at the same
> time."

---

## 🌍 0:10–2:00 — AGENTIC TASK 2: INTERNATIONAL REMOTE WORK

**Screen → live deployed app**

1. Set employee ID → **E1003**
2. Type → **I am based in California and want to work from Portugal for six weeks. What approvals and security requirements apply?**
3. Submit

### Narrate the MCP tool calls panel (in order):

| # | Tool | Say |
|---|------|-----|
| 1 | `search_policy_documents` | Read the retrieval query + args aloud. Returns chunks from `remote_work_policy.md`, section **International Work** — requires written approval from People Operations, Security, Payroll, and the employee's VP. Six weeks triggers advance request + tax & permanent-establishment review |
| 2 | `get_policy_section` *(if it appears)* | Read args aloud. Pulls a targeted section after the initial search. Show it if it fires; don't pretend it did if it didn't |
| 3 | Data-security citation | Explain only what the response actually cites — company-managed equipment, encryption, MFA, VPN, no copies to personal cloud or email |
| 4 | `lookup_employee_profile` | Args: `{"employee_id": "E1003"}`. Returns synthetic record: California / San Francisco — this is what makes it a structured-data task as well as a retrieval task |

⚠️ **Read what actually appears.** If the LLM adds or skips a call, narrate the real trace.

### Close the task — point at both panels:

> "Multiple documents cited, each with its section and
> snippet, and the final answer ties the approval chain to
> this employee's actual location. It is reporting fictional
> policy — it is not making a legal, tax, or immigration
> determination, and approval is not guaranteed."

---

## 🛡️ 2:00–2:50 — SAFETY & CONFIRMATION GATE

**Screen → same live app. Confirmation checkbox OFF.**

### Step 1 — Safety gate (no checkbox)

Type → **My manager has been harassing me. Please create a mock HR ticket now.**

Submit, then say:

> "Conduct reports hit a deterministic safety gate **before**
> the model is consulted at all, so an escalation can never
> depend on a model judgement call. It routes to People
> Operations and the reporting channel."

Point at the trace:

> "Look at the trace — no `mock_action` was created, even
> though the user asked for one."

### Step 2 — Confirmation gate (checkbox ON)

Tick the confirmation checkbox. Resubmit the same prompt.

> "The UI flag becomes `confirm_mock_action`. Only then does
> the planner add `confirmed: true`, and
> `create_mock_hr_ticket` independently rejects an
> unconfirmed call at the MCP layer — two places, not one.
> The result comes back `mock_only: true` with
> `confirmation_obtained`. It is a draft. Nothing is filed,
> nothing is investigated, nothing is irreversible."

---

## 🤝 HANDOFF

> "_____ will show where this runs and how well it actually
> scores."

---

## ⛔ DO NOT

- Screen-share `.env`, real keys, or billing pages
- Force the trace to match this script — read what's there
- Go over 3:00
