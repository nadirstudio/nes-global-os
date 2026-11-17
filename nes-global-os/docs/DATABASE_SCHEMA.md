# Database Schema

_Generated from `backend/app/models.py`. Migrations: `backend/alembic/versions/`._

PostgreSQL 16 is the single system of record. All primary keys are UUIDs so records created on the local office
server and in the cloud can be merged without collisions. Google Sheets is never a primary store.

## `ai_providers`

| Column | Type | Null | Notes |
|---|---|---|---|
| provider | VARCHAR(30) | no | PK |
| enabled | BOOLEAN | no |  |
| api_key_enc | TEXT | yes |  |
| key_hint | VARCHAR(12) | yes |  |
| base_url | VARCHAR(300) | yes |  |
| status | VARCHAR(30) | no |  |
| last_error | TEXT | yes |  |
| last_checked_at | DATETIME | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `audit_log`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| at | DATETIME | no |  |
| actor_user_id | UUID | yes |  |
| actor_agent_id | UUID | yes |  |
| actor_label | VARCHAR(200) | yes |  |
| action | VARCHAR(60) | no |  |
| entity | VARCHAR(40) | yes |  |
| entity_id | VARCHAR(60) | yes |  |
| company_id | UUID | yes |  |
| detail | JSON | no |  |
| ip | VARCHAR(60) | yes |  |

## `companies`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| code | VARCHAR(32) | no | unique |
| name | VARCHAR(200) | no |  |
| kind | VARCHAR(20) | no |  |
| parent_id | UUID | yes | → companies.id |
| description | TEXT | yes |  |
| website | VARCHAR(300) | yes |  |
| phone | VARCHAR(60) | yes |  |
| whatsapp | VARCHAR(60) | yes |  |
| email | VARCHAR(200) | yes |  |
| address | TEXT | yes |  |
| services | JSON | no |  |
| status | VARCHAR(20) | no |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `integrations`

| Column | Type | Null | Notes |
|---|---|---|---|
| key | VARCHAR(40) | no | PK |
| name | VARCHAR(120) | no |  |
| status | VARCHAR(30) | no |  |
| detail | TEXT | yes |  |
| last_checked_at | DATETIME | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `job_runs`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| job | VARCHAR(60) | no |  |
| slot | VARCHAR(40) | no |  |
| status | VARCHAR(20) | no |  |
| detail | TEXT | yes |  |
| started_at | DATETIME | no |  |
| finished_at | DATETIME | yes |  |

Unique together: (job, slot)

## `model_prices`

| Column | Type | Null | Notes |
|---|---|---|---|
| model | VARCHAR(80) | no | PK |
| provider | VARCHAR(30) | no |  |
| input_per_mtok | NUMERIC(10, 4) | no |  |
| output_per_mtok | NUMERIC(10, 4) | no |  |

## `settings`

| Column | Type | Null | Notes |
|---|---|---|---|
| key | VARCHAR(80) | no | PK |
| value | JSON | no |  |
| updated_at | DATETIME | no |  |

## `customers`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| name | VARCHAR(200) | no |  |
| phone | VARCHAR(60) | yes |  |
| email | VARCHAR(200) | yes |  |
| city | VARCHAR(100) | yes |  |
| notes | TEXT | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `departments`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| code | VARCHAR(40) | no |  |
| name | VARCHAR(200) | no |  |
| description | TEXT | yes |  |
| is_group_wide | BOOLEAN | no |  |
| head_person_id | UUID | yes | → people.id |
| status | VARCHAR(20) | no |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

Unique together: (company_id, code)

## `pipelines`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| name | VARCHAR(120) | no |  |
| stages | JSON | no |  |

## `reports`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| kind | VARCHAR(30) | no |  |
| company_id | UUID | yes | → companies.id |
| period_start | DATE | no |  |
| period_end | DATE | no |  |
| content | JSON | no |  |
| narrative | TEXT | yes |  |
| narrative_source | VARCHAR(30) | no |  |
| generated_at | DATETIME | no |  |
| generated_by | VARCHAR(60) | no |  |

## `work_sites`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | yes | → companies.id |
| name | VARCHAR(200) | no |  |
| kind | VARCHAR(20) | no |  |
| lat | NUMERIC(10, 7) | no |  |
| lng | NUMERIC(10, 7) | no |  |
| radius_m | INTEGER | no |  |
| active | BOOLEAN | no |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `people`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| employee_code | VARCHAR(32) | no | unique |
| full_name | VARCHAR(200) | no |  |
| email | VARCHAR(200) | yes |  |
| phone | VARCHAR(60) | yes |  |
| category | VARCHAR(40) | no |  |
| designation | VARCHAR(200) | yes |  |
| company_id | UUID | yes | → companies.id |
| department_id | UUID | yes | → departments.id |
| manager_id | UUID | yes | → people.id |
| skill_level | VARCHAR(20) | no |  |
| skills | JSON | no |  |
| experience_years | NUMERIC(4, 1) | no |  |
| weekly_capacity_hours | NUMERIC(5, 1) | no |  |
| responsibilities | TEXT | yes |  |
| training_requirements | JSON | no |  |
| training_completed | JSON | no |  |
| achievements | JSON | no |  |
| joined_on | DATE | yes |  |
| status | VARCHAR(20) | no |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `agents`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| code | VARCHAR(60) | no | unique |
| name | VARCHAR(200) | no |  |
| company_id | UUID | no | → companies.id |
| department_id | UUID | yes | → departments.id |
| designation | VARCHAR(200) | yes |  |
| job_description | TEXT | yes |  |
| responsibilities | JSON | no |  |
| instructions | TEXT | yes |  |
| knowledge | TEXT | yes |  |
| provider | VARCHAR(30) | no |  |
| model | VARCHAR(80) | no |  |
| fallbacks | JSON | no |  |
| tools | JSON | no |  |
| permissions | JSON | no |  |
| supervisor_person_id | UUID | yes | → people.id |
| supervisor_agent_id | UUID | yes | → agents.id |
| is_coordinator | BOOLEAN | no |  |
| schedule | JSON | no |  |
| status | VARCHAR(20) | no |  |
| monthly_budget | NUMERIC(12, 2) | yes |  |
| daily_token_limit | INTEGER | yes |  |
| version | INTEGER | no |  |
| last_tested_at | DATETIME | yes |  |
| last_test_ok | BOOLEAN | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `attendance`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| person_id | UUID | no | → people.id |
| day | DATE | no |  |
| check_in | DATETIME | yes |  |
| check_out | DATETIME | yes |  |
| status | VARCHAR(20) | no |  |
| note | TEXT | yes |  |
| method | VARCHAR(20) | yes |  |
| site_id | UUID | yes |  |
| in_lat | NUMERIC(10, 7) | yes |  |
| in_lng | NUMERIC(10, 7) | yes |  |
| in_accuracy_m | NUMERIC(8, 1) | yes |  |
| in_distance_m | NUMERIC(10, 1) | yes |  |
| out_lat | NUMERIC(10, 7) | yes |  |
| out_lng | NUMERIC(10, 7) | yes |  |
| outside_geofence | BOOLEAN | no |  |
| biometric_confirmed | BOOLEAN | no |  |
| device_id | UUID | yes |  |
| field_approved | BOOLEAN | yes |  |

Unique together: (person_id, day)

## `leads`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| pipeline_id | UUID | no | → pipelines.id |
| stage | VARCHAR(60) | no |  |
| name | VARCHAR(200) | no |  |
| phone | VARCHAR(60) | yes |  |
| email | VARCHAR(200) | yes |  |
| source | VARCHAR(60) | yes |  |
| service | VARCHAR(200) | yes |  |
| score | INTEGER | no |  |
| value | NUMERIC(14, 2) | yes |  |
| currency | VARCHAR(8) | no |  |
| owner_person_id | UUID | yes | → people.id |
| customer_id | UUID | yes | → customers.id |
| next_follow_up | DATETIME | yes |  |
| status | VARCHAR(20) | no |  |
| notes | TEXT | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `projects`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| name | VARCHAR(200) | no |  |
| kind | VARCHAR(40) | no |  |
| manager_person_id | UUID | yes | → people.id |
| objectives | TEXT | yes |  |
| budget | NUMERIC(14, 2) | yes |  |
| currency | VARCHAR(8) | no |  |
| status | VARCHAR(20) | no |  |
| start_on | DATE | yes |  |
| deadline | DATE | yes |  |
| member_ids | JSON | no |  |
| agent_ids | JSON | no |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `shifts`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| person_id | UUID | no | → people.id |
| day | DATE | no |  |
| start_time | VARCHAR(5) | no |  |
| end_time | VARCHAR(5) | no |  |
| site_id | UUID | yes | → work_sites.id |
| note | VARCHAR(200) | yes |  |

Unique together: (person_id, day)

## `users`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| email | VARCHAR(200) | no | unique |
| password_hash | VARCHAR(200) | no |  |
| role | VARCHAR(20) | no |  |
| person_id | UUID | yes | → people.id |
| is_active | BOOLEAN | no |  |
| mfa_secret_enc | TEXT | yes |  |
| mfa_enabled | BOOLEAN | no |  |
| failed_logins | INTEGER | no |  |
| locked_until | DATETIME | yes |  |
| last_login_at | DATETIME | yes |  |
| token_version | INTEGER | no |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `activities`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| lead_id | UUID | yes | → leads.id |
| customer_id | UUID | yes | → customers.id |
| channel | VARCHAR(20) | no |  |
| direction | VARCHAR(10) | no |  |
| summary | TEXT | no |  |
| by_user_id | UUID | yes | → users.id |
| at | DATETIME | no |  |

## `announcements`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | yes | → companies.id |
| department_id | UUID | yes | → departments.id |
| title | VARCHAR(200) | no |  |
| body | TEXT | no |  |
| priority | VARCHAR(10) | no |  |
| pinned | BOOLEAN | no |  |
| author_user_id | UUID | yes | → users.id |
| created_at | DATETIME | no |  |

## `approvals`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | yes | → companies.id |
| kind | VARCHAR(40) | no |  |
| title | VARCHAR(300) | no |  |
| payload | JSON | no |  |
| requested_by_user_id | UUID | yes | → users.id |
| requested_by_agent_id | UUID | yes | → agents.id |
| status | VARCHAR(20) | no |  |
| decided_by_user_id | UUID | yes | → users.id |
| decided_at | DATETIME | yes |  |
| decision_note | TEXT | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `chat_channels`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| kind | VARCHAR(20) | no |  |
| name | VARCHAR(200) | yes |  |
| company_id | UUID | yes | → companies.id |
| department_id | UUID | yes | → departments.id |
| direct_key | VARCHAR(80) | yes | unique |
| created_by_user_id | UUID | yes | → users.id |
| created_at | DATETIME | no |  |
| last_message_at | DATETIME | yes |  |

## `devices`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| user_id | UUID | no | → users.id |
| install_id | VARCHAR(64) | yes |  |
| name | VARCHAR(200) | yes |  |
| platform | VARCHAR(40) | yes |  |
| app_version | VARCHAR(20) | yes |  |
| created_at | DATETIME | no |  |
| last_seen_at | DATETIME | yes |  |
| last_ip | VARCHAR(60) | yes |  |
| revoked_at | DATETIME | yes |  |
| wipe | BOOLEAN | no |  |

## `documents`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| title | VARCHAR(300) | no |  |
| category | VARCHAR(20) | no |  |
| company_id | UUID | yes | → companies.id |
| department_id | UUID | yes | → departments.id |
| person_id | UUID | yes | → people.id |
| leaders_only | BOOLEAN | no |  |
| body_text | TEXT | yes |  |
| file_name | VARCHAR(300) | yes |  |
| file_path | VARCHAR(500) | yes |  |
| mime | VARCHAR(100) | yes |  |
| size_bytes | INTEGER | yes |  |
| sha256 | VARCHAR(64) | yes |  |
| version | INTEGER | no |  |
| uploaded_by_user_id | UUID | yes | → users.id |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `finance_entries`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| project_id | UUID | yes | → projects.id |
| kind | VARCHAR(10) | no |  |
| category | VARCHAR(100) | yes |  |
| service | VARCHAR(200) | yes |  |
| amount | NUMERIC(14, 2) | no |  |
| currency | VARCHAR(8) | no |  |
| fx_to_pkr | NUMERIC(14, 6) | no |  |
| description | TEXT | yes |  |
| reference | VARCHAR(100) | yes |  |
| occurred_on | DATE | no |  |
| created_by_user_id | UUID | yes | → users.id |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `invoices`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| customer_id | UUID | yes | → customers.id |
| project_id | UUID | yes | → projects.id |
| number | VARCHAR(40) | no |  |
| amount | NUMERIC(14, 2) | no |  |
| paid_amount | NUMERIC(14, 2) | no |  |
| currency | VARCHAR(8) | no |  |
| status | VARCHAR(20) | no |  |
| issued_on | DATE | yes |  |
| due_on | DATE | yes |  |
| description | TEXT | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

Unique together: (company_id, number)

## `leave_requests`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| person_id | UUID | no | → people.id |
| kind | VARCHAR(20) | no |  |
| start_on | DATE | no |  |
| end_on | DATE | no |  |
| half_day | BOOLEAN | no |  |
| days | NUMERIC(5, 1) | no |  |
| hours | NUMERIC(5, 1) | yes |  |
| reason | TEXT | yes |  |
| status | VARCHAR(20) | no |  |
| approver_person_id | UUID | yes | → people.id |
| decided_by_user_id | UUID | yes | → users.id |
| decided_at | DATETIME | yes |  |
| decision_note | TEXT | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `milestones`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| project_id | UUID | no | → projects.id |
| title | VARCHAR(200) | no |  |
| deliverable | TEXT | yes |  |
| due_on | DATE | yes |  |
| done | BOOLEAN | no |  |

## `tasks`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| company_id | UUID | no | → companies.id |
| department_id | UUID | yes | → departments.id |
| project_id | UUID | yes | → projects.id |
| title | VARCHAR(300) | no |  |
| description | TEXT | yes |  |
| assignee_person_id | UUID | yes | → people.id |
| assignee_agent_id | UUID | yes | → agents.id |
| reviewer_person_id | UUID | yes | → people.id |
| created_by_user_id | UUID | yes | → users.id |
| priority | VARCHAR(10) | no |  |
| impact | VARCHAR(10) | no |  |
| complexity | VARCHAR(12) | no |  |
| required_skills | JSON | no |  |
| status | VARCHAR(20) | no |  |
| due_at | DATETIME | yes |  |
| estimated_hours | NUMERIC(6, 1) | no |  |
| quality_score | INTEGER | yes |  |
| customer_satisfaction | INTEGER | yes |  |
| completed_at | DATETIME | yes |  |
| result | TEXT | yes |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `user_company_access`

| Column | Type | Null | Notes |
|---|---|---|---|
| user_id | UUID | no | PK, → users.id |
| company_id | UUID | no | PK, → companies.id |

## `agent_runs`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| agent_id | UUID | no | → agents.id |
| task_id | UUID | yes | → tasks.id |
| trigger | VARCHAR(30) | no |  |
| input | TEXT | yes |  |
| output | TEXT | yes |  |
| status | VARCHAR(20) | no |  |
| provider | VARCHAR(30) | yes |  |
| model | VARCHAR(80) | yes |  |
| input_tokens | INTEGER | no |  |
| output_tokens | INTEGER | no |  |
| cost | NUMERIC(12, 6) | no |  |
| cost_currency | VARCHAR(8) | no |  |
| priced | BOOLEAN | no |  |
| error | TEXT | yes |  |
| started_at | DATETIME | no |  |
| finished_at | DATETIME | yes |  |

## `announcement_reads`

| Column | Type | Null | Notes |
|---|---|---|---|
| announcement_id | UUID | no | PK, → announcements.id |
| user_id | UUID | no | PK, → users.id |
| read_at | DATETIME | no |  |

## `calls`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| kind | VARCHAR(10) | no |  |
| media | VARCHAR(10) | no |  |
| channel_id | UUID | yes | → chat_channels.id |
| initiator_user_id | UUID | no | → users.id |
| status | VARCHAR(12) | no |  |
| started_at | DATETIME | no |  |
| answered_at | DATETIME | yes |  |
| ended_at | DATETIME | yes |  |
| end_reason | VARCHAR(40) | yes |  |

## `chat_members`

| Column | Type | Null | Notes |
|---|---|---|---|
| channel_id | UUID | no | PK, → chat_channels.id |
| user_id | UUID | no | PK, → users.id |

## `chat_messages`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | no | PK |
| channel_id | UUID | no | → chat_channels.id |
| sender_user_id | UUID | yes | → users.id |
| body_enc | TEXT | no |  |
| created_at | DATETIME | no |  |
| deleted | BOOLEAN | no |  |

## `chat_reads`

| Column | Type | Null | Notes |
|---|---|---|---|
| channel_id | UUID | no | PK, → chat_channels.id |
| user_id | UUID | no | PK, → users.id |
| last_read_at | DATETIME | no |  |

## `call_participants`

| Column | Type | Null | Notes |
|---|---|---|---|
| call_id | UUID | no | PK, → calls.id |
| user_id | UUID | no | PK, → users.id |
| state | VARCHAR(10) | no |  |
| joined_at | DATETIME | yes |  |
| left_at | DATETIME | yes |  |
| seen | BOOLEAN | no |  |
