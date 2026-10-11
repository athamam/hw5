# Campus Customs Multi-Agent Operations (HW5)

An agent team that runs the Campus Customs (CC) shop's ticket board. Three pieces talk to each other:

1. **MCP server** (`mcp_server/`, FastMCP): the only way to read or change shop data in `data/campus_customs_new.db`.
2. **FastAPI backend with a five-agent PydanticAI team** (`backend/`): Boss, Inventory, Accounting, Facilities and Customer Service. Any agent can delegate to any other.
3. **React dashboard** (`frontend/`, Vite + TypeScript): a human watches the agents work, signs approvals, and watches the checking balance.

Every agent uses **`gpt-6-luna` through Portkey**, and no other model. The model is set in one place, `backend/config.py`.

## Shop rules the app enforces

- `desk.date_today` (2026-08-31) is "today" for deciding what's overdue. Vendor lead times come from `vendors.lead_days`.
- A vendor with an open (unpaid) invoice won't ship, so its purchase orders can't be approved until the invoice is paid.
- **Every payment needs a human.** Agents only *prepare* requests. A person approves on the board, and only then does `pay` move cash and update `payments`, `cash_accounts` and the invoice or lease.
- `pay` refuses if cash would go negative. Cash only goes out; there is no revenue in this app.
- No emails and no real vendor calls. Customer messages are saved as drafts on the board.
- Reset the database before every full run.

## Layout

```
hw5/
├── AI_prompts.md            # every prompt given to the AI coding assistant, by problem
├── requirements.txt         # Python dependencies (pinned)
├── .env.example             # copy to .env and add PORTKEY_API_KEY (real .env is git-ignored)
├── .mcp.json                # registers the campus-customs MCP server for the vibe coder
├── data/
│   ├── campus_customs.db        # ORIGINAL, never modified
│   └── campus_customs_new.db    # working copy the tools update (committed in its final, resolved state)
├── mcp_server/              # server.py (21 tools) + README.md
├── backend/                 # main.py (FastAPI), models.py, config.py, team.py, mcp_tools.py, audit.py
│   ├── agents/              # one file per agent + base.py (shared builder and delegate tool)
│   └── prompts/             # boss / inventory / accounting / facilities / customer_service.md + shop_rules.md
├── frontend/                # React + Vite + TypeScript board ("Pink Desk")
├── tests/mcp_smoke_test.py  # MCP smoke test -> output/mcp_smoke.json
└── output/                  # harness.md, mcp_smoke.json, desk_tickets.html, design.md,
                             # resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt
```

## Setup (once)

Requires Python 3.11+ and Node 20+.

**Windows (PowerShell or Git Bash)**
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
copy .env.example .env            # Git Bash: cp .env.example .env
cd frontend
npm install
cd ..
```

**macOS / Linux**
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
cd frontend && npm install && cd ..
```

Then open `.env` and put in your own `PORTKEY_API_KEY`. The backend reads it from `hw5/.env`, and falls back to a `.env` two folders up (the course folder).

**No key?** The app still runs in **read-only mode**. The board shows the tickets, cash, approvals and the recorded runs, and only the "run the agents" buttons are switched off (`/health` reports `"ai_ready": false`).

## 1. Copy the original DB to the working copy (clean run)

The original `data/campus_customs.db` is never written to. To start clean, copy it over the working copy:

```bash
# macOS / Linux / Git Bash
cp data/campus_customs.db data/campus_customs_new.db
```
```powershell
# Windows PowerShell
Copy-Item data/campus_customs.db data/campus_customs_new.db -Force
```

The same reset is available while the app is running: the **↺ Reset shop** button on the board, `POST /reset` on the backend, or the MCP tool `reset_database`. Each one copies the original and re-creates the four workflow tables (`ticket_updates`, `approvals`, `purchase_orders`, `drafts`).

## 2. Start the MCP server

```bash
.venv/Scripts/python mcp_server/server.py      # Windows
.venv/bin/python mcp_server/server.py          # macOS / Linux
```

This runs the `campus-customs` server over stdio. You normally **don't need to start it by hand**:

- **The backend starts its own copy** with the same Python that runs the backend, so it works on every OS.
- **A vibe coder** (Claude Code) opened in this folder picks it up from `.mcp.json`. That file points at the Windows virtual-environment Python (`.venv/Scripts/python.exe`). On macOS/Linux, change `"command"` to `.venv/bin/python`.

To check that all tools work against the database:

```bash
.venv/Scripts/python tests/mcp_smoke_test.py   # macOS / Linux: .venv/bin/python tests/mcp_smoke_test.py
```

## 3. Start the FastAPI backend

From the `backend/` folder:

```bash
cd backend
../.venv/Scripts/python -m uvicorn main:app --reload --port 8000    # Windows
../.venv/bin/python -m uvicorn main:app --reload --port 8000        # macOS / Linux
```

If the virtual environment is activated, this is simply `uvicorn main:app --reload --port 8000`.

The API is at http://localhost:8000, with docs at http://localhost:8000/docs. It allows the board's origin, `http://localhost:5173`. When you stop it, stop the whole process tree: uvicorn's reloader plus the MCP server child process.

| Route | What it does |
|---|---|
| `GET /health` | API status, model, and whether the AI key is set (`ai_ready`) |
| `GET /tickets` | all tickets, open or resolved |
| `POST /tickets/{id}/run` | run the agent team (Boss first) on one ticket |
| `GET /events?after=` | recent agent events: who said what and which tools they used |
| `GET /approvals` | requests waiting for a human |
| `POST /approvals/{id}/approve` | human approves; payments are paid here (the only route that changes cash) |
| `POST /approvals/{id}/reject` | human rejects |
| `GET /cash` | checking balance from `cash_accounts` |
| `POST /reset` | restore the working DB from the original |

## 4. Start the React board

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The board talks to http://localhost:8000. To use a different backend URL, set `VITE_API_URL` (see `frontend/.env.example`).

## 5. Full 3-ticket run (reset first!)

1. **Reset the database:** click **↺ Reset shop** on the board, or run `curl -X POST http://localhost:8000/reset`. Checking should read **$3,400.00** with tickets 101, 102 and 103 all open.
2. Type your name in **Signing as** in the approval tray.
3. For each ticket, **in order 101 → 102 → 103**:
   1. Click **▶ Start the crew**. The Boss delegates, the crew prepares requests, and the ticket stops at *Crew done · needs your OK*.
   2. Review each slip in **Needs your signature** and approve it. For ticket 101, pay invoice 501 *before* approving the PO; the PO is refused while 501 is unpaid.
   3. When every slip on the ticket is signed, its button turns green: click **✔ Close out**. The Boss checks what you decided and marks the ticket **Resolved ✓**.
4. Expected result: all three tickets resolved and checking at **$160.00**.
   - $3,400 − $840 (invoice 501, ticket 101) − $2,400 (rent, ticket 102) = $160.
   - Ticket 103's discount and the purchase orders don't move cash.

Command-line alternative for the agent part only (approvals still go through the board or API):

```bash
.venv/Scripts/python -m backend.team --all --reset    # macOS / Linux: .venv/bin/python -m backend.team --all --reset
```

Every agent step is appended to `output/audit_trail.json`. The file is never wiped.

## Results and write-ups

- `output/harness.md`: tables (and how the tickets link to them), MCP tools, agents, routes, dashboard, safety rules and token limits
- `output/desk_tickets.html`: Expected vs Actual per ticket, the itemized Cash tab and the Reflection (open by double-clicking)
- `output/resolved_tickets.json` and `output/resolved_board.html`: the final outcome and board screenshots for 101, 102 and 103
- `output/mcp_smoke.json`: MCP tool tests, checked against the database they ran on
- `output/design.md`: dashboard design choices
- `AI_prompts.md`: the prompt log
