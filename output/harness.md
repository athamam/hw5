# Harness — HW5: Campus Customs Multi-Agent Operations

Source data: `data/campus_customs.db` (original, never modified). Agents and tools work on `data/campus_customs_new.db`.

---

## Database tables

### desk
Fields: `date_today`, `notes`

Why it matters: `date_today` is the shop's "today" (2026-08-31), so every agent uses it to decide what is due or overdue.

### inventory
Fields: `sku`, `name`, `size`, `qty`, `location`

Why it matters: Inventory checks stock by SKU and size here to spot shortfalls before an order is promised.

### pricing
Fields: `sku`, `unit_cost`, `list_price`

Why it matters: Accounting uses cost against price to check margins, for example when deciding how deep a bulk discount can go.

### vendors
Fields: `id`, `name`, `specialty`, `lead_days`

Why it matters: Inventory matches a shortfall to the right vendor by specialty, and `lead_days` sets how soon restocked product can arrive.

### leases
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`

Why it matters: Facilities tracks rent amount and due date so the shop space is paid on time.

### cash_accounts
Fields: `name`, `balance`, `date`

Why it matters: Accounting checks the balance before any payment, and the pay tool refuses if it would go negative.

### payments
Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`

Why it matters: This is the audit trail. Every human-approved payment is recorded here with who approved it.

### invoices
Fields: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`

Why it matters: Accounting finds unpaid bills here, and an open invoice blocks that vendor from shipping new product.

### tickets
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`

Why it matters: This is the work board. Boss reads each open ticket, routes it to the right agents, and closes it when resolved.

### Workflow tables (added to the working copy only)

The MCP server creates these in `campus_customs_new.db` on start and after every reset. The original database never has them.

| Table | Fields | Why it matters |
|---|---|---|
| `ticket_updates` | `id`, `ticket_id`, `agent`, `note`, `created_at` | Agent notes and status changes on the board, so a human can see who found what |
| `approvals` | `id`, `kind` (payment / purchase_order / price_override), `ticket_id`, `ref_type`, `ref_id`, `amount`, `details`, `reason`, `requested_by`, `status`, `decided_by`, `decided_at`, `decision_note`, `created_at` | The human approval queue. Agents can only add *pending* rows; only a human decides them |
| `purchase_orders` | `id`, `vendor_id`, `sku`, `size`, `qty`, `unit_cost`, `total`, `ticket_id`, `status`, `expected_arrival`, `created_by`, `created_at` | Restock orders. Approving one moves no cash; the arrival date comes from `vendors.lead_days` |
| `drafts` | `id`, `ticket_id`, `recipient`, `subject`, `body`, `drafted_by`, `status` (always `draft`), `created_at` | Customer messages stay here and are never sent |

---

## MCP tools: the first three, tied to tickets (Problem 3)

Server: `mcp_server/server.py` (FastMCP), working on `data/campus_customs_new.db`.

| Tool | Table(s) read | Ticket it unlocks | Why it is the right tool for that ticket |
|---|---|---|---|
| `check_stock(sku, size)` | `inventory` | 101 | Tauhid wants one CC-TEE-WHITE in size S, and this tool shows that size S has qty 0, which tells the team the order cannot ship from the shelf and Inventory must restock it from a vendor. |
| `get_lease(lease_id)` | `leases`, `desk` | 102 | The landlord says rent is due in 2 days, and this tool confirms from lease 1 that the $2,400 rent is due 2026-09-02, exactly 2 days after desk.date_today, so Facilities can verify the notice before Accounting prepares the payment. |
| `get_pricing(sku, qty)` | `pricing` | 103 | The Yale AI Club wants a bulk discount on 20 CC-HOOD-NAVY hoodies, and this tool shows each costs $22 against a $58 list price, so Accounting knows the discount can go no lower than $22 a hoodie ($440 for 20) before the shop loses money. |

---

## Agent team (Problem 5)

Built with PydanticAI in `backend/`. Every agent uses **gpt-6-luna** through Portkey (`backend/config.py` is the only place the model is named). Prompts live in `backend/prompts/`, one file per agent, each loaded after the shared `shop_rules.md`. Data types live in `backend/models.py`.

**Full connectivity:** every agent has a `delegate(to_agent, task)` tool and can hand work to any other agent. The child agent runs its own loop and returns a structured report to the agent that asked.

| Agent | File | Prompt | Job | Output | MCP tools it can call |
|---|---|---|---|---|---|
| Boss | `backend/agents/boss.py` | `prompts/boss.md` | Reads each ticket, delegates, makes the final call, sets the ticket status | `BossDecision` | get_desk, get_ticket, list_tickets, list_approvals, get_cash_balance, add_ticket_note, update_ticket_status |
| Inventory | `backend/agents/inventory.py` | `prompts/inventory.md` | Stock by SKU and size, shortfalls, which vendor can restock and when | `AgentReport` | get_desk, get_ticket, check_stock, get_pricing, list_vendors, check_vendor_can_ship, list_invoices, add_ticket_note |
| Accounting | `backend/agents/accounting.py` | `prompts/accounting.md` | Cash, invoices, margins; prepares payments, POs and price overrides for human approval | `AgentReport` | get_desk, get_ticket, get_cash_balance, list_invoices, list_approvals, get_pricing, check_stock, list_vendors, check_vendor_can_ship, get_lease, request_payment, create_purchase_order, propose_price_override, add_ticket_note |
| Facilities | `backend/agents/facilities.py` | `prompts/facilities.md` | Leases, rent and the landlord | `AgentReport` | get_desk, get_ticket, get_lease, get_cash_balance, list_approvals, add_ticket_note |
| Customer Service | `backend/agents/customer_service.py` | `prompts/customer_service.md` | Drafts messages to customers and requesters (never sent) | `AgentReport` | get_desk, get_ticket, check_stock, get_pricing, list_approvals, draft_customer_message, add_ticket_note |

All five agents also have `delegate`.

**Agent loop:** `Team.run_agent` in `backend/team.py` steps through each agent with `agent.iter()`. Every node (user prompt, model request, tool calls, end, error) is appended to `output/audit_trail.json`.

**Audit trail fields:** timestamp, run_id, ticket_id, step, agent, depth, delegated_by, model, node, detail (the tool calls with arguments, the tool results, the text and the final output) and the cumulative token usage for the ticket. The file is append-only.

**How a ticket is worked:**
1. **Main run** (`POST /tickets/{id}/run`). The backend reads today's date and the ticket row from MCP (`get_desk`, `get_ticket`) once, and puts them in every agent's instructions so nobody wastes tool calls fetching them again.
2. The Boss delegates **one specialist at a time** (`delegate` is a sequential tool), calls Customer Service last with the confirmed facts, and sets the ticket to `waiting_on_human` while approvals are pending.
3. **Human step.** A person signs and approves or rejects each request on the dashboard. Only this step moves cash.
4. **Close-out run** (the same route again). The Boss sees the ticket is no longer `open`, checks what the human decided, asks Customer Service for one follow-up draft if the outcome changed, and sets `resolved`. The server refuses `resolved` while anything is still pending.

---

## All MCP tools (Problem 5)

Server: `mcp_server/server.py`, working on `data/campus_customs_new.db`. The working copy gets four extra workflow tables that are not in the original: `ticket_updates`, `approvals`, `purchase_orders` and `drafts`. They are created again after every reset.

| Tool | Who can call it | Table(s) | What it does |
|---|---|---|---|
| `get_desk` | all agents | desk | Shop's "today" (desk.date_today) and desk notes |
| `list_tickets` | Boss | tickets | Tickets on the board, optionally by status |
| `get_ticket` | all agents | tickets, ticket_updates, approvals, purchase_orders, drafts | One ticket and everything done on it so far |
| `check_stock` | Inventory, Accounting, Customer Service | inventory | Qty on hand by SKU and size |
| `get_pricing` | Inventory, Accounting, Customer Service | pricing | Unit cost, list price, margin, totals for a qty |
| `list_vendors` | Inventory, Accounting | vendors | Vendors, specialty and lead_days |
| `check_vendor_can_ship` | Inventory, Accounting | vendors, invoices, desk | Blocked if the vendor has an open invoice; earliest arrival = today + lead_days |
| `list_invoices` | Inventory, Accounting | invoices, vendors, desk | Invoices with days overdue against desk.date_today |
| `get_lease` | Facilities, Accounting | leases, desk | Rent, landlord, next due date, days until due |
| `get_cash_balance` | Boss, Accounting, Facilities | cash_accounts, approvals | Cash now and projected after all pending payment requests |
| `list_approvals` | Boss, Accounting, Facilities, Customer Service | approvals | Requests waiting for or decided by a human |
| `add_ticket_note` | all agents | ticket_updates | Posts an agent's note on the board |
| `update_ticket_status` | Boss | tickets, ticket_updates, approvals | Changes ticket status; refuses `resolved` while approvals are pending |
| `request_payment` | Accounting | approvals, invoices, leases, cash_accounts | Pending payment request for human approval; amount taken from the database |
| `create_purchase_order` | Accounting | purchase_orders, approvals, vendors, inventory, pricing, invoices | Draft restock PO for human approval; flags a vendor blocked by an open invoice |
| `propose_price_override` | Accounting | approvals, pricing, tickets | Discount for human approval; refuses below unit cost |
| `draft_customer_message` | Customer Service | drafts, tickets | Saves a message as a draft; nothing is sent |
| `pay` | **human only** | approvals, cash_accounts, payments, invoices, leases | Pays an approved request; refuses if cash would go negative; marks the invoice paid or moves the rent due date forward |
| `approve_request` | **human only** | approvals, purchase_orders, invoices, vendors | Approves a PO or price override; refuses a PO while its vendor has an open invoice |
| `reject_request` | **human only** | approvals, purchase_orders | Rejects any pending request |
| `reset_database` | **human only** | whole working copy | Copies the original campus_customs.db over campus_customs_new.db |

---

## Safety and guardrails

What a real business would want before agents touch real customers and real money, and how this build covers it:

1. **A human approves every dollar.** Agents can only create *requests*. `pay`, `approve_request` and `reject_request` are never given to an agent (filtered out in `backend/mcp_tools.py`), a call to them is blocked even if a model tries it anyway, and the server refuses any approver whose name is an agent's.
2. **No negative cash.** `pay` checks the balance at the moment of payment and refuses if it would go below zero. `request_payment` and `get_cash_balance` warn early using the projected balance after all pending requests.
3. **Amounts come from the database, not the model.** Payment amounts come from the invoice or lease row, and PO costs from the pricing table, so a model cannot inflate or mistype an amount. Duplicate pending payment requests and duplicate purchase orders are refused.
4. **Margin floor.** `propose_price_override` refuses any price below unit cost, and every discount still needs a human.
5. **Vendor rule enforced in code.** A PO cannot be approved while the vendor has an open invoice.
6. **No outbound contact.** There is no email or vendor-calling tool at all. Customer messages are `drafts` rows for a human to review and send.
7. **Least privilege.** Each agent sees only the MCP tools its role needs. For example, only Boss can change ticket status and only Customer Service can draft messages.
8. **Identity cannot be faked.** The `agent` field on every write is filled in by the backend from the run, not by the model.
9. **One source of truth.** Agents read shop facts only through MCP tools that return database values or an error, and the prompts forbid inventing numbers.
10. **Full audit trail.** Every agent step, tool call, tool result and token count is appended to `output/audit_trail.json` and never wiped.
11. **Safe resets.** The original database is never written to. Full runs start with `reset_database`.
12. **No double work.** Delegation is sequential (one hand-off at a time), and the server refuses duplicate pending payment requests and duplicate pending POs. A test run in Problem 7 created two identical POs when agents worked in parallel, which is why this was added.
13. **Tickets close only when the human is done.** `update_ticket_status` refuses `resolved` while any approval on the ticket is pending, so the board can never show "resolved" with money still waiting on a decision.
14. **Watch commitments, not just cash.** Approved POs move no cash today but become vendor bills later. After the full run, POs worth $272 are committed against $160 in checking. A real business would add a check that compares open commitments with cash before approving a PO.

### Limits that keep token use in check

Set in `backend/config.py`. They apply per ticket and are shared across every agent working on it, because delegated runs share one usage counter.

| Limit | Value | What happens when hit |
|---|---|---|
| Model requests per ticket | 40 | Run stops with `UsageLimitExceeded`, which is logged |
| Total tokens per ticket (input + output) | 200,000 | Run stops, logged |
| Tool calls per ticket | 60 | Run stops, logged |
| Max output tokens per model response | 4,000 | The response is capped |
| Delegation depth | 3 | `delegate` refuses and the agent must finish with what it has |
| Delegations per ticket | 10 | `delegate` refuses |
| No self-delegation, and no bounce-back to the agent that asked | n/a | `delegate` refuses, which prevents ping-pong loops |
| Retries per agent | 2 | Bad tool calls or invalid outputs stop after two retries |
| Audit text trimmed | 2,000 characters | Keeps the audit file readable |

On the full run (Problem 9) the busiest single run, ticket 101's main run, used 19 of 40 model requests and 54,269 of 200,000 tokens. Close-out runs used about 7 requests and 17,500–20,700 tokens each. All six runs together used 74 model requests and 202,247 tokens. No limit was hit.

---

## Backend routes (Problem 7)

`backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000`, then open http://localhost:8000 (interactive docs at http://localhost:8000/docs). Every route reads or writes through the MCP server.

- `GET /health`: confirms the API is up, shows the model (gpt-6-luna) and which ticket the team is working on, if any.
- `GET /tickets`: returns every ticket with its status and whether it is open or resolved.
- `GET /tickets/{id}`: returns one ticket with its notes, approval requests, purchase orders and customer drafts.
- `POST /tickets/{id}/run`: runs the agent team on that ticket (Boss first) and returns the Boss's decision and token usage. Only one run at a time.
- `GET /events?limit=&ticket_id=&after=`: returns recent agent events from the audit trail (who said what and which tools they called), with `after` for polling so the board can refresh.
- `GET /approvals?status=pending`: lists requests waiting for a human (`approved`, `rejected` or `all` also work).
- `POST /approvals/{id}/approve` `{"approved_by": "<human name>"}`: a human clicks Approve. Payments are paid here, the only route that changes cash; purchase orders and price overrides are approved. Refused if cash would go negative, if the vendor still has an open invoice, or if the approver is an agent.
- `POST /approvals/{id}/reject` `{"rejected_by": "...", "reason": "..."}`: a human rejects a request. No money moves.
- `GET /cash`: returns the current checking balance from cash_accounts, plus pending payment requests and the projected balance.
- `POST /reset`: restores `data/campus_customs_new.db` from the original `campus_customs.db` for a fresh run. The audit trail is kept.

---

## Dashboard (Problem 8)

`frontend/` uses React + Vite + TypeScript and is started with `npm run dev` (http://localhost:5173). It talks to the backend at `http://localhost:8000` (set in `frontend/src/api.ts`, overridable with `VITE_API_URL`), and the backend allows the Vite origin through CORS. Full design notes are in `output/design.md`.

| Board area | What it shows | Routes it calls |
|---|---|---|
| Ticket rail | The 3 tickets as paper tickets with a status pill, a **Start the crew / Run again** button, and a rubber stamp when a run finishes (**Resolved ✓** or **Crew done · needs your OK**) | `GET /tickets`, `POST /tickets/{id}/run` |
| The crew | The five agents as HTML/CSS creatures at desks. Whoever is working bounces and shows what it is saying; agents not needed are greyed out. Hand-off trail and a token-guard bar | `GET /events?after=` (polled every 1.2 s during a run) |
| Live chatter | Every agent turn: what it said, each MCP tool call as a chip (plain-English verb plus the exact call), hand-offs, and final reports, indented by delegation depth | `GET /events` |
| Shift report | One card per agent after the run: summary, records created, approvals, drafts, tools used; the Boss's call on top | `GET /events` (final agent outputs) |
| Checking | Piggy bank with the checking balance (animates down on a payment), projected balance bar, and a receipt tape of paid items with the signer | `GET /cash`, `GET /approvals` |
| Needs your signature | Approval slips (payment, PO, discount) with facts and the requesting agent. The human signs with their name and approves or rejects; refusals from the backend show as toasts | `GET /approvals`, `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject` |
| Top bar | Backend status, model, pending count, balance, **Reset shop** | `GET /health`, `POST /reset` |

---

## Full run results (Problem 9)

The database was reset first (`POST /reset`), so the run started at **$3,400.00** with 3 open tickets, then ran 101 → 102 → 103 on the board. Details are in `output/desk_tickets.html` (Expected vs Actual, and Cash), `output/resolved_tickets.json`, `output/resolved_board.html`, and the appended `output/audit_trail.json`.

| Ticket | Delegations (main run) | Human approvals | Cash | Final status |
|---|---|---|---|---|
| 101 | Boss → Inventory, Boss → Accounting, Boss → Customer Service | #1 pay invoice 501 $840 · #2 PO 1 tee $8 | −$840.00 → $2,560.00 | resolved |
| 102 | Boss → Facilities → Accounting, Boss → Customer Service | #3 pay rent lease 1 $2,400 | −$2,400.00 → $160.00 | resolved |
| 103 | Boss → Inventory, Boss → Accounting, Boss → Customer Service | #4 discount 10% ($52.20 × 20) · #5 PO 12 hoodies $264 | $0.00 → $160.00 | resolved |

**Cash check:** $3,400.00 − $840.00 − $2,400.00 = **$160.00**, which equals `cash_accounts.checking` in `data/campus_customs_new.db`. The `payments` table has exactly two rows ($840 invoice 501 and $2,400 rent), both approved by a human. Each ticket also had one close-out run (Boss → Customer Service follow-up draft → resolved).

---

## File map

| Path | What it is |
|---|---|
| `data/campus_customs.db` | Original database (never modified) |
| `data/campus_customs_new.db` | Working copy the MCP server and backend update |
| `.mcp.json` | Registers the `campus-customs` MCP server for the vibe coder and the backend |
| `mcp_server/server.py`, `mcp_server/README.md` | MCP server (21 tools) and its docs |
| `backend/config.py` | Model (`gpt-6-luna`), Portkey URL, paths, token limits |
| `backend/models.py` | Data types (deps, AgentReport, BossDecision, AuditStep, TicketRunResult) |
| `backend/prompts/` | `shop_rules.md` plus one prompt per agent |
| `backend/agents/` | One file per agent plus `base.py` (shared builder and the `delegate` tool) |
| `backend/mcp_tools.py` | MCP connection, per-agent tool filters, human-only block, agent-name stamping |
| `backend/team.py` | The team, the agent loop, and a CLI (`python -m backend.team --ticket 101`) |
| `backend/audit.py` | Append-only writer for `output/audit_trail.json` |
| `backend/main.py` | FastAPI routes |
| `frontend/` | React dashboard |
| `tests/mcp_smoke_test.py` | MCP smoke test → `output/mcp_smoke.json` |
| `output/` | harness.md, mcp_smoke.json, audit_trail.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, screenshots/ |
