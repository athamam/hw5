# AI Prompts Log — HW5: Campus Customs Multi-Agent Operations

Log of prompts given to the AI coding assistant, organized by problem.

---

## Problem 1: Vibe coder prompts

1. > /lecture-folder-joke hw5

2. > Delete the joke

3. > I will first give you context and some ground rules for you to understand and maintain throughout the hw assignment. Then we will begin each problem one by one.
   >
   > 1. Scenario
   >
   > Campus Customs ("CC") Multi-Agent Operations is the agentic team that runs the shop. Open tickets land on a board, including customer orders, rent, bills, discount requests, etc. I will build three pieces that talk to each other: an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so a human can watch the agents work and approve requests
   >
   > My agent team has full connectivity. Any agent may delegate tasks to any other agent. Later in the assignment i want to build these agents:
   >
   > * Boss - reads each ticket, decide who works on it and makes final calls
   > * Inventory - checks stock by SKU and size, spots shortfalls and figures out which vendor can restock
   > * Accounting - watches cash and invoices, checks margins and prepares payments or purchase orders for human approval
   > * Facilities - handles the shop space side (leases, rent, etc.)
   > * Customer service - drafts messages for customers
   >
   > 2. Data
   >
   > I've placed a data file in hw5 folder. This is the original shop database. Tools will update the database as tickets get resolved. I want you to make a copy of the database file called data/campus_customs_new.db and point the MCP server and backend later to work on that copy. I want you to keep the origina campus_customs.db file untouched so I can reset/restart if needed
   >
   > 3. Rules
   >
   > * The field desk.date_today is "today" for the shop. Use this date to determine what is overdue
   > * Vendor lead times come from the 'vendors' table
   > * A vendor will not ship new product while they still have an open unpaid invoice
   > * Human approval is required for any payment. This is crucial. If payment is made, make sure to update the relevant table
   > * If there is not enough cash, the pay tool must refuse. No negative balances
   > * Cash only goes out in this homework. No revenue/money comes in
   > * Before a full run to resolve tickets, make sure to reset the database to the original values
   > * Do NOT email customers or call real vendors. Drafts stay on the board
   >
   > Use my PORTKEY_API_KEY for AI calls. For this hw5, use ONLY gpt-6-luna through Portkey for every agent. This is very crucial, because points in my hw5 will be deducted if any other model shows up in my code or runs. Let me know if this is clear and ok or if you have any concerns.
   >
   > I will submit my hw via a public github repo and I will submit the link

4. > yes gpt-6-luna is correct, commit the copy, log prompts

5. > Starting with problem 1. Create AI_prompts.md and log everything I say
   >
   > Divide it up into one section per problem include problem number and title:
   >
   > * Problem 1: Vibe coder prompts
   > * Problem 2: Study the Campus Customs database
   > * Problem 3: Build the MCP server
   > * Problem 4: Add the MCP server to vibe coder and test each tool
   > * Problem 5: Build the agent team and grow the MCP tools
   > * Problem 6: Plan the three tickets
   > * Problem 7: Backend routes
   > * Problem 8: Agent dashboard
   > * Problem 9: Resolve the tickets
   > * Problem 10: Reflection
   > * Problem 11: Submit to GitHub

---

## Problem 2: Study the Campus Customs database

1. > Moving on to problem 2, open campus_customs.db for me so I can read it. Also copy it to data/campus_customs_new.db if you haven't already. We will update that new working copy
   >
   > Then start output/harndess.md. For each table, list the fields and one short line on why that table matters for the agents

---

## Problem 3: Build the MCP server

1. > Moving on to problem 3, build the MCP server. Write an MCP serve in mcp_server/ using FastMCP which will talk to data/campus_customs_new.db. We will not be connecting or running it now
   >
   > All the agents in this hw will use the tools in this MCP server, and we will add more tools later. For now write 3 tools that we will need for the tickets in the database. Keep the names clear, never invent data and only use information in the database
   >
   > In harness.md, list my 3 MCP tools, including which table it reads, which ticket it helps unlock (101, 102 or 103) and one sentence on why it is the right tool for that ticket. Make sure the sentence is not vague (e.g., "reads inventory"). Tie the tool to the ticket
   >
   > Also create mcp_serve/README.md that explains what the MCP server is for, which database file it uses, and the 3 tools it has

---

## Problem 4: Add the MCP server to vibe coder and test each tool

1. > Moving on to problem 4. Add the MCP server to this project so you can call the tools. Save the connection JSON text in .mcp.json at the project root (or however you save local MCP server lists).
   >
   > I want you to test each of the 3 MCP tools and save the evidence in output/mcp_smoke.json. For every tool:
   >
   > * Create and write down a prompt to ask a vibe coder for each test
   > * The tool name
   > * The tool output (must match values in data/campus_customs_new.db)

2. > Do it for me

3. > ok

---

## Problem 5: Build the agent team and grow the MCP tools

1. > Moving on to problem 5. Build the agentic team for CC using PydanticAI: Boss, Inventory, Accounting, Facilities and Customer. Include prompts, models and agent loops so they can delegate work to each other with full connectivity
   >
   > Put the agent prompts in backend/prompts/. One file per agent. Put data types in backend/models.py and the agent files under backend/. Use PORTKEY_API_KEY and only gpt-6-luna for every agent. Follow other rules as I mentioned previously:
   >
   > * The field desk.date_today is "today" for the shop. Use this date to determine what is overdue
   > * Vendor lead times come from the 'vendors' table
   > * A vendor will not ship new product while they still have an open unpaid invoice
   > * Human approval is required for any payment. This is crucial. If payment is made, make sure to update the relevant table
   > * If there is not enough cash, the pay tool must refuse. No negative balances
   > * Cash only goes out in this homework. No revenue/money comes in
   > * Before a full run to resolve tickets, make sure to reset the database to the original values
   > * Do NOT email customers or call real vendors. Drafts stay on the board
   >
   > Add tools the agents need to my MCP server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db. Do not invent a second shop-tools layer that bypasses MCP
   >
   > Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file - do not wipe it each run.
   >
   > In output/harness.md, list each agent and each MCP tool (including ones I add in this problem) along with which table the tool uses. Also add a safety section: the guardrails a real business would want when agents touch real customers and real money, plus add a limit that keep token use in check
   >
   > Update mcp_server/README.md so the tool list matches what I have now

---

## Problem 6: Plan the three tickets

1. > Moving on to problem 6. Before wiring the backend, write some stuff on what we can expect the team to do on each open ticket. Build out/desk_tickets.html, a page that someone can double click with one tab per ticket (101, 102, 103). Also add empty Cash and Reflection tabs for later problems (leave them blank for now)
   >
   > On each ticket tab, fill an Expected section only (leave room for an 'Actual' section which we will fill after we run the agents)
   >
   > For each ticket's Expected section, write up:
   >
   > * Who the boss should call first and why
   > * All the agents delegations we expect. Not "Boss calls everyone"
   > * Which MCP tools we expect that run to use
   >
   >
   > I do not want plans that send every specialist on every ticket. We will compare what actually happens when the agent resolves the 3 tickets

2. > desck_tickets.html should be in output/

---

## Problem 7: Backend routes

1. > Moving on to problem 7, backend routes. In backend/main.py use FastAPI and add routes that do the following:
   >
   > * Return the 3 tickets and whether each is open or resolved
   > * Take a ticket id and run the agent team on that ticket
   > * Return recent agent events, what each agent said and which tools they used, so the board can refresh
   > * Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
   > * Return the current checking balance from cash_accounts
   > * Reset the database to the original values when I want to try a fresh run
   >
   >
   > From the backend/ folder, start the server (uvicorn main:app --reload --port 8000) to turn on the backend at http://localhost:8000
   >
   > In harness file, list each route in one line (what URL/what it does)

---

## Problem 8: Agent dashboard

1. > Wait till later. For now moving on to problem 8. Build the frontend dashboard in frontend/ with React+Vite+TypeScript. This page should call the routes built in the previous problem. At minimum the board should:
   >
   > 1. List all 3 tickets
   > 2. Let me pick 1 ticket and start the agent team on it
   > 3. Show each agent and what they are saying/doing will the ticket runs
   > 4. Mark a ticket resolved when the run finishes
   > 5. Show a short summary of what each agent did on that ticket
   > 6. Let a human approve a pay or purchase when asked
   > 7. Show the checking balance (it should drop after an approved pay)
   >
   >
   > Make the dashboard look good, so that people enjoy looking at and working on it. Make it professional but fun & interesting and unique. Put extra effort for this
   >
   > Tell the front end to talk to the backend at http://localhost:8000. On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes. Start the board with : npm run dev
   >
   > Write output/design.md with what was chosen for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why, including the creative choices that make it feel special

---

## Problem 9: Resolve the tickets

1. > Moving on to problem 9. Before testing the agents on a full run, reset the working database data/campus_customs_new.db again so we start clean. Note the starting checking balance, the run all 3 tickets on the board until each is resolved
   >
   > Open output/desk_tickets.html. On each ticket tab, fill the 'Actual' section from this run, which agents worked, what they delegated and which tools they used. Keep the Expected section so we can compare. On the Cash tab of the same output/desk_tickets.html, itemize the money:
   >
   > * Starting checking balance (after the reset)
   > * For each ticket: how cash changed when that ticket resolved, and why (which pay/purchase, dollar amount)
   > * Ending checking balance, it must match cash_accounts in the working database
   >
   >
   > This is important: wrong cash math loses points for this assignment even if the board shows every ticket resolved. So keep an eye out for this
   >
   > Also save:
   >
   > * output/resolved_tickets.json, for each ticket: id, final status, short outcome, what each agent contributed and any human approvals
   > * output/resolved_board.html, a page i can double click with a  screenshot of my React board for each resolved ticket (101, 102, 103)
   >
   >
   > Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard and safety rules

---

## Problem 10: Reflection

1. > Moving on to problem 10, reflection. Open output.desk_tickets.html and fill the Reflection tab for me, write it in my style/vibe. Be detailed and thorough:
   >
   > * How I would evalute the performance of the agents on each ticket and why
   > * For each ticket how did Actual compare to the Expected plan I had written earlier
   > * What would have been simpler as one agent with tools and why
   > * Describe 3 new problems CC might face that this agent team could solve with the tools we have
   > * Describe 3 new problems CC might face that this agent team could NOT solve, and explain what tools and agents would be needed to solve them
   >
   >
   > Tie every answer to this app and the 3 tickets ran. use the ticket tabs and cash tab on the same page as evidence. Every answer and writeup must be related to Campus Customs, this is important.

---

## Problem 11: Submit to GitHub

1. > Moving on to problem 11, submit to GitHub. Push my code to a public GitHub repo so graders can clone it. I will submit the repo URL to Canvas. Put it also in output/github_url.txt
   >
   > Do not push real .env to the GitHub repo. Do include both databse files under data/
   >
   > README should explain: copy original DB to the working copy when I need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full 3 ticket run
   >
   > This is the expected layout *(screenshot of the expected hw5/ folder tree: AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/ with both databases, mcp_server/ with server.py and README.md, frontend/, backend/ with main.py, models.py and prompts/ (boss, inventory, accounting, facilities, customer_service), output/ with harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt)*
