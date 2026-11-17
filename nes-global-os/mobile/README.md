# NES Team (Android) — build guide

React + TypeScript app packaged with Capacitor 8. The APK is built on **GitHub Actions** (free), because building
Android apps needs Google's Android SDK.

## Build the APK on GitHub (one-time setup, ~15 minutes)

1. Create a free account at github.com (if you don't have one) and a **private** repository, e.g. `nes-global-os`.
2. Upload this whole project folder (`nes-global-os/`) to the repository. Easiest: install **GitHub Desktop**, choose
   *Add existing repository* → this folder → *Publish repository* → keep **Private** ticked.
3. Add the signing secrets (from `nes-team-signing-key.zip`, delivered separately — open `GITHUB-SECRETS.txt`):
   repository → **Settings → Secrets and variables → Actions → New repository secret**, four times:
   `NES_KEYSTORE_BASE64`, `NES_KEYSTORE_PASSWORD`, `NES_KEY_ALIAS`, `NES_KEY_PASSWORD`.
4. Repository → **Actions** → *NES Team APK* → **Run workflow**.
5. When it turns green (5–10 min), open the run → **Artifacts** → download `NES-Team-APK-…` (a zip containing the APK).

Every later change to `mobile/` builds a new APK automatically. To publish a numbered release, push a tag such as
`team-v1.0.1`.

Without the secrets the workflow still builds, but a **debug** APK that can't be updated in place — add the secrets
before handing the app to staff.

## Develop locally

```bash
cd mobile
npm ci
npm run dev          # opens in a browser; use the server address of a running NES GLOBAL OS
npm run build        # type-check + production bundle in dist/
npx cap sync android # copy the bundle into the Android project
```
In a desktop browser the fingerprint step is simulated with a confirm dialog and GPS uses the browser's location.
For browser development, add the dev origin to `NES_CORS_ORIGINS` on the server (e.g. `http://localhost:5173`).

## Security settings in the Android project

- `MainActivity.java` sets `FLAG_SECURE` (no screenshots, screen recording or recent-apps preview).
- `AndroidManifest.xml`: `allowBackup=false` + data-extraction rules (no Google backup / device transfer of app data).
- Session token is device-bound and can be revoked from the portal; on revoke + wipe the app clears all stored data.
- Permissions: Internet, fine/coarse location (only while using the app), biometric, notifications.
