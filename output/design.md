# Pink Desk: dashboard design

The Campus Customs agent dashboard (`frontend/`, React + Vite + TypeScript). It talks to the FastAPI backend at `http://localhost:8000`, and the backend allows the Vite origin `http://localhost:5173` through CORS. Start it with `npm run dev` inside `frontend/`.

## The idea

A real shop's back office is a desk covered in paper: order tickets, a piggy bank, slips waiting for a signature. The dashboard keeps that feeling and puts a small crew of creatures on the desk doing the work. It should look professional enough to run a business from (clear numbers, statuses and an audit trail) and still feel friendly, because a human watching agents spend money needs to trust what they see and enjoy checking it.

The theme is pink, per the course rule for websites. It uses one pink family on white paper, a light dotted-grid background like a cutting mat, and one dark plum "ink" colour for text so everything stays readable.

## Layout

Three columns, read left to right like the work flows:

| Column | What it holds | Why there |
|---|---|---|
| **Left: Ticket rail** | The 3 tickets as paper tickets, each with its own **Start the crew** button | You pick work first, so it sits where the eye starts. It is sticky, so it never scrolls away. |
| **Centre: The crew, then Live chatter, then Shift report** | The five agents at their desks, the live transcript, and a summary card per agent after the run | The run is the main event, so it gets the widest column. The order matches time: who is working now, what they said, what they did. |
| **Right: Checking, then Needs your signature** | The piggy-bank balance, the receipt tape of payments, and the approval slips | Money and approvals sit together because approving a payment is what moves the balance. You see the cause and the effect side by side. |

A sticky top bar always shows whether the backend is live, the model (`gpt-6-luna`), how many requests are awaiting you, the cash balance, and **Reset shop**. Below 1250px wide the right column moves under the others, and on a phone everything stacks.

## How the agents read differently

Each agent is a small **Labubu-style creature built only from HTML and CSS** (no images, per the course rule for creatures): tall bunny ears, blush, and a toothy grin. They tell apart in four ways at once, so no one has to rely on colour alone:

| Agent | Nickname | Colour | Accessory | Voice in the feed |
|---|---|---|---|---|
| Boss | "Big Bun" | raspberry | gold crown | decisions, hand-offs, and the final call (🏁) |
| Inventory | "Shelfie" | coral pink | cardboard box | "Counting the shelves", "Asking if the vendor can ship" |
| Accounting | "Penny" | lilac | round glasses | "Peeking at the piggy bank", "Preparing a payment slip" |
| Facilities | "Keys" | peach | hard hat | "Pulling out the lease" |
| Customer Service | "Hello Kit" | orchid | headset with mic | "Writing a draft message" |

- **On the floor**, each creature sits at a desk tinted its colour, with a speech bubble showing its latest line.
  - The agent that is working **bounces, wiggles its ears, and gets a spotlight and typing dots**.
  - An agent that handed work off shows **"Waiting on a teammate"**.
  - A finished agent gets a **green check badge**.
  - An agent the Boss didn't need goes **grey and sleepy-eyed** with "Not needed". This is how you can see at a glance that the Boss did *not* send every specialist.
- **Hand-offs** appear as a trail of chips above the desks (`Boss ✈ Facilities`, `Facilities ✈ Accounting`) with a small paper plane, so the delegation path is visible without reading the transcript.
- **In the live feed**, every line has the agent's mini creature, its colour on the left edge, and the line is indented by delegation depth, so a sub-task sits visibly "inside" the task that asked for it. Tool calls show up as chips with a plain-English verb ("Counting the shelves") on top of the exact call (`check_stock(sku=CC-TEE-WHITE, size=S)`). Non-technical viewers read the verb, and the person grading reads the code.

## How tickets and "resolved" show up

- Tickets look like **paper raffle tickets**: a pink stub with the ticket number printed vertically and a dashed perforation with punched notches. Each has an icon for its type (👕 order, 🏠 rent, 🏷️ discount), the requester, the SKU, size and qty in monospace, and the original note in quotes.
- A status pill reads Open, In progress, **Waiting on you** (amber) or **Resolved** (green).
- When a run finishes, the ticket gets a **rubber stamp that slams down with a bounce**:
  - **"Resolved ✓"** in green when the Boss closes it. Pink hearts also float up the screen.
  - **"Crew done · needs your OK"** in amber when the crew has done its part but a human must still approve something.
- The ticket being worked **pulses**, and every Start button is disabled until the run ends, matching the backend's one-run-at-a-time lock.

## How cash shows up

- **A piggy bank** (also pure CSS) sits next to the checking balance. The balance **counts down** with an easing animation instead of jumping, and when a payment is approved **gold coins fall out of the piggy** and the number shakes. So you *feel* money leave, which is the point: this homework only has cash going out.
- **A runway bar** shows the balance against the opening $3,400, with a second, darker bar for the projected balance if every pending payment is approved. You can see whether the shop can afford everything on the tray before signing.
- **The receipt tape** is lined like till paper. It lists every paid item with who signed it, in monospace, with the amount in red.

## How approvals show up

- Each request is a **permission slip** with a perforated left edge, an icon (💸 payment, 📦 purchase order, 🏷️ discount), a one-line headline (for example "$840.00 to Bulldog Print Co"), the key facts, and the requesting agent's creature and reason.
- You type your name once in **"Signing as"**. It appears in handwriting on each slip's signature line and is saved for next time. The approve button stays disabled until a human name is there, which mirrors the backend rule that an agent can never approve.
- Slips that the backend refuses (for example a PO while the vendor still has an unpaid invoice, or a payment with not enough cash) show the backend's reason in a red toast. Approved items move to **Recently decided** with a small **PAID** or **OK** stamp.

## Shift report

After a run, each agent that worked hands in a card:
- what it found, in its own summary
- the records it created
- tags for approvals and drafts
- the exact MCP tools it used

The Boss's final call sits on top as **"Boss's call"**. Agents that sat out are named underneath ("Sat this one out: Inventory. The Boss didn't need them."). That line makes the Problem 6 comparison between expected and actual easy.

## Small things that make it feel special

- A **token guard** fuel bar in the crew header shows tokens used against the 200k per-ticket limit and model calls against the 40-call limit. It makes the cost guardrail visible while the crew works.
- A red **LIVE** tag and "the crew is thinking…" dots while the run is going. The feed auto-scrolls and uses `aria-live` so screen readers announce new lines.
- The Boss's creature is the logo in the top bar, and "Pink Desk" sits in a slightly tilted label.
- Everything respects `prefers-reduced-motion`: all bouncing, stamping and coin animation turns off for people who prefer it.
- Keyboard friendly: tickets are focusable and can be selected with Enter, and every button has a visible pink focus ring.

## Why these choices

- **Trust:** money moves only through a visible human signature, the balance animates so changes are noticed, and the receipt tape keeps a record of who signed what.
- **Clarity:** colour, accessory, nickname and indent together make it obvious which agent did what, even in a fast-moving feed.
- **Comparison:** "Not needed" agents, the hand-off trail and the shift report map directly onto the Expected plan in `output/desk_tickets.html`.
- **Delight:** the creatures, stamps, coins and hearts make a dull operations task (paying rent, approving a PO) feel like a small game, without hiding any of the real numbers.
