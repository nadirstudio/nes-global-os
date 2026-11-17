#!/usr/bin/env bash
# NES GLOBAL OS — first-time install on a fresh Ubuntu Server 24.04 LTS (run as a sudo user, from this folder).
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if ! command -v docker >/dev/null; then
  say "Installing Docker Engine + Compose plugin (official repository)"
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg ufw openssl
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
fi

say "Firewall: allow SSH, HTTP, HTTPS only"
sudo ufw allow OpenSSH >/dev/null
sudo ufw allow 80/tcp >/dev/null
sudo ufw allow 443/tcp >/dev/null
sudo ufw --force enable >/dev/null

if [ ! -f .env ]; then
  say "Generating secrets into deploy/.env"
  cp .env.example .env
  rand() { openssl rand -base64 48 | tr -d '\n/+=' | cut -c1-48; }
  fernet=$(openssl rand -base64 32 | tr '+/' '-_')
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand)|; s|^NES_JWT_SECRET=.*|NES_JWT_SECRET=$(rand)|; s|^NES_MASTER_KEY=.*|NES_MASTER_KEY=${fernet}|" .env
  chmod 600 .env
  echo "IMPORTANT: copy deploy/.env to a safe offline place. NES_MASTER_KEY decrypts stored API keys; without it they cannot be recovered."
fi

say "Building and starting the stack"
sudo docker compose up -d --build

say "Waiting for the API"
for i in $(seq 1 60); do
  if sudo docker compose exec -T api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')" 2>/dev/null; then break; fi
  sleep 3
done

say "Seeding company structure and AI agent registry (safe to re-run)"
sudo docker compose exec -T api python -m app.cli seed

if ! sudo docker compose exec -T db psql -U nesos -d nesos -tAc "select 1 from users where role='ceo'" | grep -q 1; then
  say "Create the CEO account"
  read -rp "CEO login email: " CEO_EMAIL
  sudo docker compose exec api python -m app.cli create-ceo --email "$CEO_EMAIL" --name "Mubshair Ali"
fi

say "Installing nightly encrypted backup (02:30 Asia/Karachi)"
mkdir -p "$HOME/nesos-backups"
[ -f "$HOME/.nesos-backup-key" ] || { openssl rand -base64 48 > "$HOME/.nesos-backup-key"; chmod 600 "$HOME/.nesos-backup-key"; }
# (server timezone is Asia/Karachi, so 02:30 is local time; '|| true' keeps set -e from aborting on an empty crontab)
{ crontab -l 2>/dev/null | grep -v nesos-backup || true; echo "30 2 * * * $(pwd)/backup.sh >> $HOME/nesos-backups/backup.log 2>&1 # nesos-backup"; } | crontab -
sudo timedatectl set-timezone Asia/Karachi || true

IP=$(hostname -I | awk '{print $1}')
say "Done. Open http://${IP}/ from any computer or phone on the office network."
echo "Next: sign in, enable MFA (Settings → My security), add your Anthropic API key (Settings → AI & costs)."
echo "Keep a copy of ~/.nesos-backup-key offline: backups cannot be restored without it."
