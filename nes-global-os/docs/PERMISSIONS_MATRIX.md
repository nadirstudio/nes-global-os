# Permissions Matrix

_Generated from `backend/app/permissions.py` — the code is the source of truth._

## Human roles

| Action | CEO | Director | Department Head | Manager | Employee | Intern | Freelancer |
|---|---|---|---|---|---|---|---|
| `dashboard.view` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `company.manage` | ✅ | — | — | — | — | — | — |
| `department.manage` | ✅ | ✅ | — | — | — | — | — |
| `people.view` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `people.manage` | ✅ | ✅ | ✅ | — | — | — | — |
| `users.manage` | ✅ | — | — | — | — | — | — |
| `agents.view` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `agents.manage` | ✅ | ✅ | ✅ | — | — | — | — |
| `agents.run` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `tasks.view` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `tasks.create` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `tasks.update_own` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `tasks.review` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `approvals.view` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `approvals.decide` | ✅ | ✅ | ✅ | — | — | — | — |
| `crm.view` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| `crm.manage` | ✅ | ✅ | ✅ | ✅ | ✅ | — | — |
| `projects.view` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `projects.manage` | ✅ | ✅ | ✅ | — | — | — | — |
| `finance.view` | ✅ | ✅ | — | — | — | — | — |
| `finance.manage` | ✅ | ✅ | — | — | — | — | — |
| `ai.settings` | ✅ | — | — | — | — | — | — |
| `ai.usage.view` | ✅ | ✅ | — | — | — | — | — |
| `integrations.view` | ✅ | ✅ | — | — | — | — | — |
| `integrations.manage` | ✅ | — | — | — | — | — | — |
| `audit.view` | ✅ | — | — | — | — | — | — |
| `assistant.use` | ✅ | ✅ | — | — | — | — | — |
| `reports.view` | ✅ | — | — | — | — | — | — |
| `workforce.intelligence` | ✅ | ✅ | ✅ | ✅ | — | — | — |
| `attendance.manage` | ✅ | ✅ | ✅ | ✅ | — | — | — |

## Data scope (multi-company isolation)

| Role | Sees |
|---|---|
| CEO | Everything, all companies |
| Director | Own company + companies explicitly granted (user_company_access) |
| Department Head / Manager | Own department(s) inside their company (and departments they head) |
| Employee / Intern / Freelancer | Only their own tasks, leads they own, projects they are members of |

Scope is enforced server-side on every query (`deps.ensure_company / ensure_department`, `Scope`), never in the UI.
Interns and supervised beginners: marking a reviewed task *done* routes it to *review* for the reviewer.

## AI agent actions

| Action | Policy | Meaning |
|---|---|---|
| `research` | automatic (if granted) | Research using approved sources |
| `internal_report` | automatic (if granted) | Prepare internal reports |
| `draft_document` | automatic (if granted) | Draft documents for human review |
| `crm_update` | automatic (if granted) | Authorized CRM updates (notes, scores, stage suggestions) |
| `task_recommend` | automatic (if granted) | Recommend task assignments |
| `data_analysis` | automatic (if granted) | Analyse internal data |
| `send_external_email` | **human approval** | Send external email |
| `customer_message` | **human approval** | Send customer communication (WhatsApp/SMS) |
| `submit_application` | **human approval** | Submit university / job applications |
| `submit_visa` | **human approval** | Submit visa applications |
| `publish_content` | **human approval** | Publish content |
| `contract` | **human approval** | Contracts |
| `financial_commitment` | **human approval** | Financial commitments |
| `hiring` | **human approval** | Hiring decisions |
| `salary_change` | **human approval** | Salary changes |
| `discount` | **human approval** | Discounts |
| `sensitive_customer_decision` | **human approval** | Sensitive customer decisions |
| `payment` | **never grantable** | Payments / bank transfers |
| `delete_records` | **never grantable** | Deleting records |
| `disclose_confidential` | **never grantable** | Disclosing confidential data |
| `change_bank_details` | **never grantable** | Changing bank details |
| `legal_commitment` | **never grantable** | Legal commitments |

Agents request actions by emitting `ACTION_REQUEST` lines; the runtime checks them against the agent's granted
permissions. Approval-required actions create an Approval record; prohibited or ungranted actions are denied and audited.
