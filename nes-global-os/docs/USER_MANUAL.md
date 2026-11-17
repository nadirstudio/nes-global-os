# User Manual

Open NES GLOBAL OS in any browser (Chrome, Edge, Safari, Firefox). On phones use "Add to Home Screen" to install it as an app.

## Everyone

- **Sign in** with the email and temporary password your administrator gave you; change it in Settings → My security,
  and enable MFA (Google/Microsoft Authenticator).
- **Tasks & Approvals → Check in / Check out** at the start and end of the day (after 09:15 counts as late).
- **My tasks:** open a task to see details, set *In progress*, *Blocked* or *Done*, and add your result. If your task has a
  reviewer, *Done* goes to *Review* first.

## Managers and department heads

- **Command Centre:** your department(s) only.
- **Tasks:** create and assign tasks to people or AI agents; set complexity (beginners only get *basic*), estimated hours,
  required skills, impact and due date. After review, score quality and customer satisfaction (1–5) — these drive fair
  performance measurement.
- **Workforce intelligence tab:** utilisation this week, overdue work, training needs, and recommended assignments for
  unassigned tasks. Nothing is assigned until you press *Assign*.
- **Workforce:** mark attendance (present, late, remote, leave, absent).
- **AI agents in your department:** configure, test, activate or pause; *Run agent now* on an agent's task. Agent output
  always lands in *Review* for a human.

## CEO and directors

- **Command Centre:** whole group (directors: their companies). Refreshes every 30 s. Click a company in the network map.
- **Executive AI:** ask questions in plain language ("Which department is underperforming?"). Answers come from live data;
  with Claude connected you also get a written analysis. Generate or reread daily/weekly/monthly reports (CEO).
- **Organisation:** the live org map. Click any person or agent to open their profile and controls. Add companies,
  ventures and departments.
- **Approvals:** approve or reject what agents and staff request (customer messages, publishing, discounts, submissions,
  contracts, financial commitments, hiring).
- **CRM:** one pipeline per company; drag-free stage changes in the lead panel; log calls/WhatsApp/visits; *Mark won*
  creates a customer. Duplicate contacts are blocked automatically.
- **Projects:** launch departments, courses, stores or locations with manager, budget, deadline and milestones.
- **Finance:** record revenue (with service name) and expenses per company in any currency (enter the rate to PKR), issue
  invoices and record receipts. The system never moves money.
- **Settings → AI & costs (CEO):** API keys, model prices, budgets, usage by agent and model.
- **Settings → Audit log (CEO):** every sign-in, change, agent run and decision.

## Status words you'll see

| Status | Meaning |
|---|---|
| OPERATIONAL | Agent passed a live test, is active, provider connected, within budget |
| NOT CONNECTED | No API key for its provider |
| CONFIGURED (UNTESTED) | Key saved, no successful call yet |
| AUTHENTICATION REQUIRED | Provider rejected the key |
| QUOTA EXHAUSTED | Provider rate-limited or out of credit |
| BUDGET LIMIT | Your own NES budget for the group or agent is used up |
| DEGRADED (FALLBACK) | Main model unavailable; running on its fallback model |
| PAUSED | Paused by a manager |
