# AI Agent Registry

_Generated from the database: 115 agents (23 department coordinators)._

Every agent ships as **configured** (not active). To go live: add an API key → TEST (real model call) → ACTIVATE.
Model tiers: `claude-opus-5-5` (advanced reasoning: CEO assistant, strategists, dev, legal), `claude-sonnet-5-5`
(research / standard work), `claude-haiku-5-5` (high-volume, cost-efficient: support, classification, reminders).
Opus/Sonnet agents fall back one tier down if their model is unavailable.

## NADIR E-SKILLS (SMC-PRIVATE) LIMITED

### Executive Office

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| Executive Assistant | `NES-GROUP-EXECUTIVE-ASSISTANT` | claude-opus-5-5 | data_analysis, draft_document, internal_report, research, task_recommend | Daily CEO briefing, weekly report and monthly review from system data; Answer the CEO's questions across all companies using verified data; Prepare management meetings, decision summaries and approval queues; Strategic recommendations, hiring and expansion analyses |

### Finance

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Finance Coordinator | `NES-GROUP-FIN-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Finance department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Budget Monitoring Agent | `NES-GROUP-FIN-BUDGET-MONITORING-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Budget vs actual alerts |
| Expense Analysis Agent | `NES-GROUP-FIN-EXPENSE-ANALYSIS-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report | Expense trends and anomalies |
| Finance Assistant | `NES-GROUP-FIN-FINANCE-ASSISTANT` | claude-sonnet-5-5 | data_analysis, internal_report | Answer finance questions from recorded data |
| Financial Reporting Agent | `NES-GROUP-FIN-FINANCIAL-REPORTING-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report | Monthly company-wise P&L |
| Invoice Agent | `NES-GROUP-FIN-INVOICE-AGENT` | claude-haiku-5-5 | draft_document | Draft invoices for approval |
| Receivables Agent | `NES-GROUP-FIN-RECEIVABLES-AGENT` | claude-haiku-5-5 | customer_message, data_analysis, internal_report | Overdue invoice lists and reminder drafts |

### Human Resources

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Human Resources Coordinator | `NES-GROUP-HR-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Human Resources department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Attendance Agent (Staff) | `NES-GROUP-HR-ATTENDANCE-AGENT--STAFF` | claude-haiku-5-5 | data_analysis, internal_report | Staff attendance summaries |
| Employee Help Desk | `NES-GROUP-HR-EMPLOYEE-HELP-DESK` | claude-haiku-5-5 | internal_report, research | Answer employees' questions in the NES Team app from their own HR data and published company policies; Point employees to the right policy document or to HR when the answer isn't documented |
| Employee Performance Agent | `NES-GROUP-HR-EMPLOYEE-PERFORMANCE-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report | Performance summaries using quality, impact and deadlines |
| Onboarding Agent | `NES-GROUP-HR-ONBOARDING-AGENT` | claude-haiku-5-5 | draft_document, task_recommend | Onboarding checklists and first-week plans |
| Recruitment Agent | `NES-GROUP-HR-RECRUITMENT-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, hiring, internal_report, research | Job descriptions, CV screening summaries |
| Training Agent | `NES-GROUP-HR-TRAINING-AGENT` | claude-sonnet-5-5 | draft_document, task_recommend | Training plans per skill level |
| Workforce Planning Agent | `NES-GROUP-HR-WORKFORCE-PLANNING-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Capacity analysis and hiring plans |

### Information Technology

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Information Technology Coordinator | `NES-GROUP-IT-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Information Technology department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Cybersecurity Monitoring Agent | `NES-GROUP-IT-CYBERSECURITY-MONITORING-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report | Audit-log review for suspicious activity |
| Database Monitoring Agent | `NES-GROUP-IT-DATABASE-MONITORING-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Database and backup checks |
| IT Support Agent | `NES-GROUP-IT-IT-SUPPORT-AGENT` | claude-haiku-5-5 | draft_document | Staff IT help and troubleshooting guides |
| Infrastructure Monitoring Agent | `NES-GROUP-IT-INFRASTRUCTURE-MONITORING-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Server health summaries |
| Integration Monitoring Agent | `NES-GROUP-IT-INTEGRATION-MONITORING-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Integration status checks |

### Legal & Compliance

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Legal & Compliance Coordinator | `NES-GROUP-LEGAL-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Legal & Compliance department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Compliance Research Agent | `NES-GROUP-LEGAL-COMPLIANCE-RESEARCH-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, research | FBR, SECP and data-protection compliance research |
| Contract Review Assistant | `NES-GROUP-LEGAL-CONTRACT-REVIEW-ASSISTANT` | claude-opus-5-5 | draft_document, internal_report, research | Flag risky clauses for human legal review |
| Policy Management Agent | `NES-GROUP-LEGAL-POLICY-MANAGEMENT-AGENT` | claude-sonnet-5-5 | draft_document | Draft and version internal policies |

### Operations

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Operations Coordinator | `NES-GROUP-OPS-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Operations department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Operations Director Agent | `NES-GROUP-OPS-OPERATIONS-DIRECTOR-AGENT` | claude-opus-5-5 | data_analysis, internal_report, task_recommend | Cross-company operational review |
| Quality Assurance Agent | `NES-GROUP-OPS-QUALITY-ASSURANCE-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report | Group-wide quality reviews |
| SOP Management Agent | `NES-GROUP-OPS-SOP-MANAGEMENT-AGENT` | claude-sonnet-5-5 | draft_document | Draft and maintain SOPs |
| Task Monitoring Agent | `NES-GROUP-OPS-TASK-MONITORING-AGENT` | claude-haiku-5-5 | data_analysis, internal_report, task_recommend | Overdue and blocked task monitoring |
| Workflow Automation Agent | `NES-GROUP-OPS-WORKFLOW-AUTOMATION-AGENT` | claude-sonnet-5-5 | internal_report, research | Identify automation opportunities (n8n / Apps Script) |

## NES Consultancy

### Business & Tax Services

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Business & Tax Services Coordinator | `NES-CONS-TAX-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Business & Tax Services department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Tax & SECP Services Agent | `NES-CONS-TAX-TAX---SECP-SERVICES-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, research | Prepare NTN, tax return, SECP and trademark document checklists; Track filing deadlines |

### Embassy Appointment Booking

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Embassy Appointment Booking Coordinator | `NES-CONS-APPT-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Embassy Appointment Booking department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Embassy Appointment Agent | `NES-CONS-APPT-EMBASSY-APPOINTMENT-AGENT` | claude-sonnet-5-5 | crm_update, data_analysis, draft_document, internal_report, research | Track appointment slots and case timelines; Prepare required-document lists per embassy |

### Operations & Quality

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Operations & Quality Coordinator | `NES-CONS-OPSQA-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Operations & Quality department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Consultancy Operations Agent | `NES-CONS-OPSQA-CONSULTANCY-OPERATIONS-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Monitor case progress across desks; Flag stuck files |
| Quality Assurance Agent | `NES-CONS-OPSQA-QUALITY-ASSURANCE-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report | Review completed files against checklists; Report recurring errors |

### Sales & Client Services

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Sales & Client Services Coordinator | `NES-CONS-SALES-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Sales & Client Services department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Client Follow-up Agent | `NES-CONS-SALES-CLIENT-FOLLOW-UP-AGENT` | claude-haiku-5-5 | crm_update, customer_message, draft_document | Track follow-up dates; Draft follow-up messages for approval |
| Customer Support Agent | `NES-CONS-SALES-CUSTOMER-SUPPORT-AGENT` | claude-haiku-5-5 | crm_update, customer_message, draft_document | Draft replies to WhatsApp/email inquiries; Escalate sensitive cases to humans |
| Lead Generation Agent | `NES-CONS-SALES-LEAD-GENERATION-AGENT` | claude-sonnet-5-5 | crm_update, data_analysis, draft_document, internal_report, research | Identify lead sources (expos, referrals, campaigns); Draft outreach for approval |
| Lead Qualification Agent | `NES-CONS-SALES-LEAD-QUALIFICATION-AGENT` | claude-haiku-5-5 | crm_update, data_analysis | Classify inquiries by service; Score and route leads to the right desk |
| Sales Director Agent | `NES-CONS-SALES-SALES-DIRECTOR-AGENT` | claude-opus-5-5 | crm_update, data_analysis, internal_report, research, task_recommend | Pipeline review and sales targets; Coach sales staff with weekly insights |

### Study Abroad & Admissions

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Study Abroad & Admissions Coordinator | `NES-CONS-STUDY-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Study Abroad & Admissions department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Admission Processing Agent | `NES-CONS-STUDY-ADMISSION-PROCESSING-AGENT` | claude-sonnet-5-5 | crm_update, draft_document, submit_application | Prepare application checklists and SOP drafts; Prepare submissions for human approval |
| Scholarship Agent | `NES-CONS-STUDY-SCHOLARSHIP-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, research | Find scholarships matching student profiles; Track scholarship deadlines |
| Study Abroad Research Agent | `NES-CONS-STUDY-STUDY-ABROAD-RESEARCH-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, research | Country requirements for UK, USA, Canada, Australia, Cyprus, France, New Zealand, Italy and others; Cost-of-study comparisons |
| University Research Agent | `NES-CONS-STUDY-UNIVERSITY-RESEARCH-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, research | Shortlist universities to the student's grades, budget and goals; Track intakes and deadlines |

### Visa, Migration & Jobs

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Visa, Migration & Jobs Coordinator | `NES-CONS-VISA-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Visa, Migration & Jobs department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| CV Preparation Agent | `NES-CONS-VISA-CV-PREPARATION-AGENT` | claude-sonnet-5-5 | draft_document | Draft CVs and cover letters for client review |
| Document Verification Assistant | `NES-CONS-VISA-DOCUMENT-VERIFICATION-ASSISTANT` | claude-sonnet-5-5 | data_analysis, internal_report | Check client files for missing or inconsistent documents before submission |
| Employer Verification Agent | `NES-CONS-VISA-EMPLOYER-VERIFICATION-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, research | Verify overseas employers and flag fraud risk |
| International Jobs Research Agent | `NES-CONS-VISA-INTERNATIONAL-JOBS-RESEARCH-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, research | Research overseas job openings and legal migration routes |
| Recruitment Coordination Agent | `NES-CONS-VISA-RECRUITMENT-COORDINATION-AGENT` | claude-haiku-5-5 | crm_update, data_analysis, internal_report, task_recommend | Track candidate applications and interview schedules |
| Ticketing Assistant | `NES-CONS-VISA-TICKETING-ASSISTANT` | claude-haiku-5-5 | draft_document, financial_commitment | Prepare ticket options for approval (no purchases without approval) |
| Travel Research Agent | `NES-CONS-VISA-TRAVEL-RESEARCH-AGENT` | claude-haiku-5-5 | data_analysis, internal_report, research | Research routes, fares and travel requirements |
| Visa Research Agent | `NES-CONS-VISA-VISA-RESEARCH-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, research | Visa requirements, financial evidence rules and interview preparation material |

## NES Digital Marketing

### Creative

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Creative Coordinator | `NES-DM-CREATIVE-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Creative department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Creative Director Agent | `NES-DM-CREATIVE-CREATIVE-DIRECTOR-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, task_recommend | Creative briefs and review of creative output |
| Graphic Design Assistant | `NES-DM-CREATIVE-GRAPHIC-DESIGN-ASSISTANT` | claude-haiku-5-5 | draft_document | Design briefs and copy for designers |
| SEO Agent | `NES-DM-CREATIVE-SEO-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, research | Technical, on-page and local SEO tasks |
| Social Media Agent | `NES-DM-CREATIVE-SOCIAL-MEDIA-AGENT` | claude-sonnet-5-5 | draft_document, publish_content | Content calendars and post drafts for approval |
| Video Production Coordinator | `NES-DM-CREATIVE-VIDEO-PRODUCTION-COORDINATOR` | claude-haiku-5-5 | draft_document, task_recommend | Video scripts and editing schedules |

### Development

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Development Coordinator | `NES-DM-DEV-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Development department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Project Manager Agent | `NES-DM-DEV-PROJECT-MANAGER-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Client project timelines, milestones and status reports |
| QA Agent | `NES-DM-DEV-QA-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report | Test plans and pre-launch checklists |
| Software Development Assistant | `NES-DM-DEV-SOFTWARE-DEVELOPMENT-ASSISTANT` | claude-opus-5-5 | draft_document, research | Code drafts and technical specs for developer review |
| Web Development Assistant | `NES-DM-DEV-WEB-DEVELOPMENT-ASSISTANT` | claude-opus-5-5 | draft_document, research | WordPress/Elementor builds, fixes and specs |

### E-commerce

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ E-commerce Coordinator | `NES-DM-ECOM-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the E-commerce department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| E-commerce Operations Agent | `NES-DM-ECOM-E-COMMERCE-OPERATIONS-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, task_recommend | Store setup and catalogue tasks |
| Product Research Agent | `NES-DM-ECOM-PRODUCT-RESEARCH-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, research | Product and market research for e-commerce clients |

### Sales

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Sales Coordinator | `NES-DM-SALES-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Sales department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Customer Support Agent | `NES-DM-SALES-CUSTOMER-SUPPORT-AGENT` | claude-haiku-5-5 | crm_update, customer_message, draft_document | Client questions and monthly report delivery drafts |
| Lead Generation Agent | `NES-DM-SALES-LEAD-GENERATION-AGENT` | claude-sonnet-5-5 | crm_update, data_analysis, draft_document, internal_report, research | Find prospects locally and internationally; Draft outreach for approval |
| Marketing Strategist | `NES-DM-SALES-MARKETING-STRATEGIST` | claude-opus-5-5 | data_analysis, draft_document, internal_report, research | Audits, competitor research and 90-day roadmaps |
| Proposal Agent | `NES-DM-SALES-PROPOSAL-AGENT` | claude-sonnet-5-5 | discount, draft_document | Draft proposals with fixed fees for approval |
| Sales Agent | `NES-DM-SALES-SALES-AGENT` | claude-sonnet-5-5 | crm_update, customer_message, draft_document | Qualify prospects and book free consultations |

## NES E-commerce

### E-commerce Operations

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ E-commerce Operations Coordinator | `NES-ECOM-OPS-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the E-commerce Operations department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Store Operations Agent | `NES-ECOM-OPS-STORE-OPERATIONS-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, task_recommend | Catalogue, orders and fulfilment tracking |

## NES Events

### Events & Expos

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Events & Expos Coordinator | `NES-EVENTS-EVENTS-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Events & Expos department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Events Planning Agent | `NES-EVENTS-EVENTS-EVENTS-PLANNING-AGENT` | claude-sonnet-5-5 | data_analysis, draft_document, internal_report, research | Expo and seminar plans, vendor lists, timelines |
| Sponsorship & Partnership Agent | `NES-EVENTS-EVENTS-SPONSORSHIP---PARTNERSHIP-AGENT` | claude-sonnet-5-5 | crm_update, data_analysis, draft_document, internal_report, research | Sponsor prospect lists and proposals for approval |

## Nadir Academy

### Academic Management

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Academic Management Coordinator | `NES-ACAD-ACADEMIC-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Academic Management department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Academic Coordinator Agent | `NES-ACAD-ACADEMIC-ACADEMIC-COORDINATOR-AGENT` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Batch planning and teacher coordination |
| Lesson Planning Agent | `NES-ACAD-ACADEMIC-LESSON-PLANNING-AGENT` | claude-sonnet-5-5 | draft_document, research | Draft lesson plans for teacher review |
| Student Progress Agent | `NES-ACAD-ACADEMIC-STUDENT-PROGRESS-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Track progress and flag at-risk students |

### Administration

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Administration Coordinator | `NES-ACAD-ADMIN-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Administration department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Attendance Agent (Students) | `NES-ACAD-ADMIN-ATTENDANCE-AGENT--STUDENTS` | claude-haiku-5-5 | data_analysis, internal_report | Student attendance summaries |
| Fee Management Agent | `NES-ACAD-ADMIN-FEE-MANAGEMENT-AGENT` | claude-haiku-5-5 | customer_message, data_analysis, internal_report | Fee due lists and reminder drafts |
| Timetable Agent | `NES-ACAD-ADMIN-TIMETABLE-AGENT` | claude-haiku-5-5 | internal_report, task_recommend | Draft class timetables without clashes |

### Examination

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Examination Coordinator | `NES-ACAD-EXAM-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Examination department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Certificate Coordination Agent | `NES-ACAD-EXAM-CERTIFICATE-COORDINATION-AGENT` | claude-haiku-5-5 | draft_document, publish_content | Prepare certificate lists for approval |
| Examination Scheduling Agent | `NES-ACAD-EXAM-EXAMINATION-SCHEDULING-AGENT` | claude-haiku-5-5 | internal_report, task_recommend | Exam schedules and invigilation plans |
| Question Preparation Assistant | `NES-ACAD-EXAM-QUESTION-PREPARATION-ASSISTANT` | claude-sonnet-5-5 | draft_document | Draft question papers for teacher approval |
| Result Processing Agent | `NES-ACAD-EXAM-RESULT-PROCESSING-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Compile results for verification |

### Sales and Admissions

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Sales and Admissions Coordinator | `NES-ACAD-SALES-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Sales and Admissions department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Course Recommendation Agent | `NES-ACAD-SALES-COURSE-RECOMMENDATION-AGENT` | claude-haiku-5-5 | data_analysis, draft_document | Recommend courses to the student's goals and level |
| Education Sales Agent | `NES-ACAD-SALES-EDUCATION-SALES-AGENT` | claude-sonnet-5-5 | crm_update, data_analysis, draft_document, internal_report, research | Course inquiries pipeline; Seasonal campaign ideas |
| Student Admission Agent | `NES-ACAD-SALES-STUDENT-ADMISSION-AGENT` | claude-haiku-5-5 | crm_update, draft_document | Admission forms and fee status tracking |

## Nadir Services

### Service Desk

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Service Desk Coordinator | `NES-SERV-DESK-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Service Desk department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Computer Services Agent | `NES-SERV-DESK-COMPUTER-SERVICES-AGENT` | claude-haiku-5-5 | draft_document | Computer service requests |
| Customer Support Agent | `NES-SERV-DESK-CUSTOMER-SUPPORT-AGENT` | claude-haiku-5-5 | crm_update, customer_message, draft_document | Answer service inquiries and required-document questions |
| Daily Cash Reporting Agent | `NES-SERV-DESK-DAILY-CASH-REPORTING-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Daily cash summary from recorded entries |
| Online Application Assistant | `NES-SERV-DESK-ONLINE-APPLICATION-ASSISTANT` | claude-sonnet-5-5 | draft_document, submit_application | Prepare online applications for approval |
| Order Management Agent | `NES-SERV-DESK-ORDER-MANAGEMENT-AGENT` | claude-haiku-5-5 | crm_update, internal_report | Track orders from request to collection |
| Printing Services Agent | `NES-SERV-DESK-PRINTING-SERVICES-AGENT` | claude-haiku-5-5 | crm_update, draft_document | Printing order intake and status |

## Nadir Studio

### Creative & Production

| Agent | Code | Model | Permissions | Responsibilities |
|---|---|---|---|---|
| ◆ Creative & Production Coordinator | `NES-STUDIO-CREATIVE-COORDINATOR` | claude-sonnet-5-5 | data_analysis, internal_report, task_recommend | Coordinate the Creative & Production department's people and agents; Morning priorities, task recommendations and end-of-day summary for the department head |
| Creative Order Agent | `NES-STUDIO-CREATIVE-CREATIVE-ORDER-AGENT` | claude-haiku-5-5 | crm_update, draft_document | Order intake and briefs |
| Customer Follow-up Agent | `NES-STUDIO-CREATIVE-CUSTOMER-FOLLOW-UP-AGENT` | claude-haiku-5-5 | customer_message, draft_document | Ready/collection notifications for approval |
| Design Coordination Agent | `NES-STUDIO-CREATIVE-DESIGN-COORDINATION-AGENT` | claude-haiku-5-5 | draft_document, task_recommend | Assign design work and track approvals |
| Printing Production Agent | `NES-STUDIO-CREATIVE-PRINTING-PRODUCTION-AGENT` | claude-haiku-5-5 | internal_report, task_recommend | Production queue and delivery dates |
| Quality Control Agent | `NES-STUDIO-CREATIVE-QUALITY-CONTROL-AGENT` | claude-haiku-5-5 | data_analysis, internal_report | Check outputs against the order |
| Translation Coordination Agent | `NES-STUDIO-CREATIVE-TRANSLATION-COORDINATION-AGENT` | claude-haiku-5-5 | draft_document, task_recommend | Translation jobs and proofreading |
