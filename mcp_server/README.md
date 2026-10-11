# Campus Customs MCP Server

## What it is for

This MCP server is the shared toolbox and the single source of shop facts for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents never query the database directly. They call these tools, so every agent sees the same facts and nothing is made up: each tool returns what is stored in the database, or an error if the record does not exist.

The shop's rules are enforced in the tools themselves, not only in the agent prompts:

- "Today" is `desk.date_today`, never the computer's clock.
- Vendor lead times come from `vendors.lead_days`.
- A vendor with an open (unpaid) invoice will not ship, so its purchase orders cannot be approved until the invoice is paid.
- Money only moves through `pay`, which needs a pending payment request and a human approver, and refuses if cash would go negative.
- Cash only goes out. No tool adds money.
- Customer messages are saved as drafts. Nothing is ever sent.

## Database

- **Uses:** `data/campus_customs_new.db` (the working copy that tickets update)
- **Never writes to:** `data/campus_customs.db` (the original, kept for resets)

The path is resolved relative to this folder, so the server works from any directory. On start (and after every reset) the server adds four workflow tables to the working copy: `ticket_updates`, `approvals`, `purchase_orders` and `drafts`.

## Tools (21)

### Read

| Tool | Inputs | Table(s) | Returns |
|---|---|---|---|
| `get_desk` | none | desk | Shop's today (`date_today`) and desk notes |
| `list_tickets` | optional `status` | tickets | Tickets on the board |
| `get_ticket` | `ticket_id` | tickets, ticket_updates, approvals, purchase_orders, drafts | One ticket and everything done on it |
| `check_stock` | `sku`, optional `size` | inventory | Qty on hand, aisle, in stock or not |
| `get_pricing` | `sku`, optional `qty` | pricing | Unit cost, list price, margin, totals |
| `list_vendors` | optional `specialty` | vendors | Vendors with specialty and lead days |
| `check_vendor_can_ship` | `vendor_id` | vendors, invoices, desk | Whether the vendor will ship, blocking invoices, earliest arrival |
| `list_invoices` | optional `status`, `vendor_id` | invoices, vendors, desk | Invoices with days overdue |
| `get_lease` | `lease_id` | leases, desk | Rent, landlord, next due, days until due |
| `get_cash_balance` | none | cash_accounts, approvals | Balance now and projected after pending payments |
| `list_approvals` | optional `status` | approvals | Requests waiting for or decided by a human |

### Write (agents; nothing here moves money or contacts anyone)

| Tool | Inputs | Table(s) | Does |
|---|---|---|---|
| `add_ticket_note` | `ticket_id`, `agent`, `note` | ticket_updates | Posts a note on the board |
| `update_ticket_status` | `ticket_id`, `status`, `agent`, `resolution` | tickets, ticket_updates | Changes status; refuses `resolved` while approvals are pending |
| `request_payment` | `kind` (invoice or rent), `ref_id`, `reason`, `agent`, optional `ticket_id` | approvals | Pending payment request; amount comes from the database |
| `create_purchase_order` | `vendor_id`, `sku`, `size`, `qty`, `reason`, `agent`, optional `ticket_id` | purchase_orders, approvals | Draft restock PO for approval; warns if the vendor is blocked |
| `propose_price_override` | `ticket_id`, `sku`, `qty`, `unit_price`, `reason`, `agent` | approvals | Discount for approval; refuses below unit cost |
| `draft_customer_message` | `ticket_id`, `recipient`, `subject`, `body`, `agent` | drafts | Saves a draft; never sent |

### Human only (the backend never gives these to an agent)

| Tool | Inputs | Table(s) | Does |
|---|---|---|---|
| `pay` | `approval_id`, `approved_by` | approvals, cash_accounts, payments, invoices, leases | Pays a pending payment request; refuses if cash would go negative; marks the invoice paid or moves the lease's next due date forward one month |
| `approve_request` | `approval_id`, `approved_by`, optional `note` | approvals, purchase_orders | Approves a PO or price override; refuses a PO while the vendor has an open invoice |
| `reject_request` | `approval_id`, `rejected_by`, `reason` | approvals, purchase_orders | Rejects any pending request |
| `reset_database` | none | whole working copy | Copies the original database over the working copy |

These tools also refuse approver names that belong to an agent.

## Running

The server is registered in `.mcp.json` at the hw5 root as `campus-customs`. The agent backend starts it from that same file.

```bash
.venv/Scripts/python mcp_server/server.py
```

Requires the `fastmcp` package (see `requirements.txt`).
