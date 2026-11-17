# NES Team — Employee Android App (Release 1 + Calls)

A private Android app for NADIR E-SKILLS staff, installed directly from an APK (not the Play Store). It connects to
your own NES GLOBAL OS server over **Tailscale**.

## What's in release 1

| Area | Features | Status |
|---|---|---|
| Attendance | GPS geofence check-in/out + fingerprint/face confirmation; outside the office → "field work" note → manager review; late rule; monthly history | ✅ tested |
| Leave & shifts | Annual/casual/sick/unpaid leave, half days, overtime hours; live balances; manager approval; approved leave marks attendance; shift roster (personal + team) | ✅ tested |
| Tasks & approvals | My tasks, status updates, notes; managers: team tasks, review, approve leave / field check-ins / business approvals | ✅ tested |
| Communication | Group, company and department chats (automatic), 1-to-1 messages, encrypted at rest; company news with urgent alerts; staff directory with call / WhatsApp / email / message | ✅ tested |
| Knowledge | Document hub (policies, SOPs, handbooks, training, contracts, forms); AI HR help desk that answers from the employee's own records and published policies | ✅ tested |
| Security | Device-bound sign-in (30 days), app lock with fingerprint/face/PIN, screenshots and screen recording blocked, no cloud backup of app data, remote sign-out + wipe per phone, MFA | ✅ built (wipe tested via API) |

| **Calls (release 1.2)** | Free voice and video calls between staff, group voice calls from any department/company chat (up to 6 people), ringing with Answer / Voice only / Decline, mute, camera on/off, flip camera, call history with missed calls, who's online | ✅ tested (real WebRTC between 3 browser phones, server on 2 workers) |

**Next releases:** payslips, tax summaries and loans (payroll inside NES OS) · expense claims with receipt photos ·
offline mode with auto-sync · polls and kudos · ringing when the app is closed · Google sign-in · background push.

## How calls work

- **On office Wi-Fi: no SIM, no internet needed.** The phones find each other through the NES server on your network,
  then the voice/video goes directly phone-to-phone through the office router.
- **Outside the office:** calls go through Tailscale (mobile data or any Wi-Fi). Still no SIM minutes.
- **Office address:** in the app's setup (or More → Security → Edit) enter `http://192.168.1.27`. The app then uses
  the office address whenever it answers — so chat and calls keep working when the internet is down — and switches to
  Tailscale automatically when the phone leaves the office.
- **Group calls** are voice-only beyond 4 people and limited to 6 people, because each phone sends its voice to every
  other phone. For bigger meetings, a small media server (LiveKit) can be added to the server later.
- **Ringing:** a call rings when NES Team is open or was used recently. If the app is fully closed, the caller gets
  "No answer" and the other person sees a missed call next time. Ringing on a closed app needs a native background
  service; it's planned after you've tried calls on your real phones.
- **Loudspeaker:** Android plays call audio through the loudspeaker by default; an earpiece switch needs a native
  plugin (next release).
- If two phones on very different networks can't connect directly, a TURN relay can be configured with
  `NES_ICE_SERVERS` in `deploy/.env` — not needed on office Wi-Fi or Tailscale.

## Honest limits of release 1

- **Notifications** appear while the app is open or in recent use (it checks every 30 s). True background push needs
  Firebase or a self-hosted push service — planned with calls.
- **Fingerprint/face** is checked by the phone; the server records that the check was passed. It proves the phone's
  owner unlocked it, not who is holding it. Combined with one device per person and the GPS record, it's the standard
  approach for attendance apps without dedicated biometric hardware.
- **Fake-GPS apps** can fool any phone-based geofence. The server keeps every coordinate, distance and device, so
  managers can spot patterns; rooted-device detection can be added later.
- **"Containerisation"** (a separate encrypted work profile with full remote wipe of the phone's work area) needs
  Android Enterprise / an MDM product. NES Team protects its own data: app lock, screenshot block, no backups,
  remote sign-out + wipe of everything the app stored.
- Documents opened as files (PDF, Word) open in the phone's viewer through a 5-minute link; text documents open inside
  the app.

## One-time server setup (Tailscale HTTPS)

1. Install Tailscale on the server (if not already):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
2. In the Tailscale admin console (login.tailscale.com) → **DNS**: enable **MagicDNS** and **HTTPS Certificates**.
3. Publish NES GLOBAL OS over HTTPS inside your tailnet:
   ```bash
   sudo tailscale serve --bg 80
   tailscale serve status
   ```
   It prints an address like **https://nes-server.tail1234.ts.net** — this is the **server address** staff enter in the app.
4. Each employee installs the **Tailscale** app from the Play Store and signs in to your tailnet (invite them from the
   Tailscale admin console). Keep Tailscale ON.

## Admin setup in the portal (Employee Hub)

1. **Office locations:** Employee Hub → Office locations → add each office/branch (Google Maps → right-click the building
   → copy the coordinates), radius 100–200 m. Once a location exists, staff check in from the app only.
2. **HR rules:** leave days per year, late grace minutes, fingerprint required.
3. **Documents:** publish the HR policy, travel policy, handbook, SOPs. The AI help desk reads them.
4. **People:** every employee needs a profile with a **reporting manager** (leave goes to them) and a login.
5. **AI help desk (optional):** AI Agent Factory → *Employee Help Desk* → Test → Activate. Without it, the help desk still
   answers from data and quotes policies word for word.

## Installing on a phone

1. Download the APK (see `mobile/README.md` for how it's built) and send it to the employee (WhatsApp/USB/Drive).
2. On the phone: open the APK → allow **Install unknown apps** for that source when asked → Install.
3. Open **NES Team** → enter the server address → sign in with work email and password.
4. Allow **Location** ("While using the app") and **Notifications**.
5. The phone must have a screen lock (fingerprint/face/PIN).

## Updating

Install the new APK over the old one. This works only if every APK is signed with the same NES key (the GitHub
workflow does this once the signing secrets are added).

## When a phone is lost or someone leaves

Portal → Employee Hub → **Phones** → *Sign out & wipe*. Also disable their login in Workforce.
