# Integration Status

Statuses shown in the app are computed or verified — an integration only shows **CONNECTED** after a successful live check.
`CONNECTED` cannot be set by hand (the API rejects it).

| Integration | Status at delivery | What's built | What's needed from you |
|---|---|---|---|
| PostgreSQL | CONNECTED | Full schema + migrations | — |
| Redis | CONNECTED | Rate limiting | — |
| Background worker | CONNECTED when running | Schedule + agent queue + heartbeat | — |
| **Anthropic Claude** | NOT CONNECTED | Provider adapter, test button, fallback, budgets, cost tracking | An **Anthropic API key** from console.anthropic.com (separate from your Claude.ai subscription). Enter it in Settings → AI & costs. Then set model prices and budgets. |
| OpenAI | NOT CONNECTED | Adapter ready | Optional API key |
| Google Gemini | NOT CONNECTED | Adapter ready | Optional API key |
| OpenAI-compatible | NOT CONNECTED | Adapter ready (base URL) | Optional endpoint + key |
| Gmail | NOT CONNECTED | Planned Phase 11 | Google Cloud project, OAuth consent screen, OAuth client ID (Web), Workspace admin approval of scopes |
| Google Drive / Docs / Sheets / Calendar / Forms | NOT CONNECTED | Planned Phase 11 (Sheets export-only from PostgreSQL) | Same OAuth client; list of Drive folders and Sheets to sync |
| Google Apps Script | NOT CONNECTED | Planned Phase 11 — existing Apps Script apps (Accounting & Payroll, Appointment Booking, Document Pack) to be migrated or bridged | Source code / Sheet IDs of the existing scripts |
| **WhatsApp Business Cloud API** | NOT CONNECTED | Planned Phase 12: shared inbox, company numbers, routing, templates, human takeover | Meta Business Manager (verified), WhatsApp Business Account, a phone number ID **per company number**, a permanent System User access token, approved message templates, a public HTTPS webhook URL |
| n8n | NOT CONNECTED | Planned (optional) | Decide whether to self-host on the server |
| Cloud object storage | NOT CONNECTED | Planned Phase 2 | Bucket + access key (S3/B2/R2/GCS) |
| Cloud sync | NOT CONNECTED | Designed (outbox + conflict queue), Phase 2 | Cloud VPS |
| Tailscale (employee app access) | Set up by you | App + portal reachable at https://<server>.<tailnet>.ts.net via `tailscale serve` | Tailscale account; MagicDNS + HTTPS enabled; staff invited (see EMPLOYEE_APP.md) |
| GitHub Actions (APK builds) | Set up by you | Workflow `.github/workflows/nes-team-apk.yml` | Private GitHub repo + 4 signing secrets |
| Off-site backups | NOT CONNECTED | `backup.sh` supports `rclone` | An rclone remote (e.g. Google Drive) |
| Web research provider | NOT CONNECTED | Planned — research agents currently use knowledge + data only | Choice of search API |
| Existing NES Digital Marketing CRM | — | The new CRM is ready; nothing was rebuilt from the old one | Source code or export of the existing CRM so it can be imported/integrated rather than duplicated |

## On WhatsApp QR-code (WhatsApp Web) automation

Not used, by design. Automating WhatsApp Web through a QR login breaks WhatsApp's terms, gets numbers banned without warning,
disconnects when the phone sleeps or loses internet, and offers no delivery guarantees or audit trail. The official
WhatsApp Business Platform (Cloud API) supports multiple numbers per business, webhooks, templates and an audit trail, and
keeps your numbers safe. Meta charges for some message types (mainly business-initiated templates) — check Meta's current
pricing page for Pakistan before going live. If you need a stop-gap before Cloud API
approval, the safe option is the free WhatsApp Business app on shared devices with click-to-chat links from the CRM
(already in the lead drawer).
