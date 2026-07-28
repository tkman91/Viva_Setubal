#!/usr/bin/env bash
# HTTPS para a app Gestão Restaurante numa VM Ubuntu (Nginx reverse proxy + cert).
# Arquitetura: Nginx (443) serve o build do frontend e faz proxy de /api -> uvicorn 127.0.0.1:8001.
# Uma única origem HTTPS => sem problemas de CORS/cookies.
#
# Uso:  bash scripts/setup_https.sh [HOST]
#   HOST = IP ou hostname pelo qual acedes no browser (default: 192.168.1.16)
set -e

HOST="${1:-192.168.1.16}"
APP_DIR="$HOME/Viva_Setubal"
CERT_DIR="/etc/ssl/restaurante"

echo "==> 1/6  Pacotes (nginx, openssl)"
sudo apt-get update
sudo apt-get install -y nginx openssl

echo "==> 2/6  Certificado self-signed para '$HOST' (825 dias)"
sudo mkdir -p "$CERT_DIR"
if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then SAN="IP:$HOST"; else SAN="DNS:$HOST"; fi
sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=$HOST" -addext "subjectAltName=$SAN"

echo "==> 3/6  Build do frontend (origem relativa => chama /api na mesma origem)"
cd "$APP_DIR/frontend"
echo 'REACT_APP_BACKEND_URL=' > .env
corepack enable 2>/dev/null || true
yarn install
DISABLE_VISUAL_EDITS=true yarn build

echo "==> 4/6  Backend .env para HTTPS (cookie Secure, mesma origem)"
cd "$APP_DIR/backend"
if grep -q '^COOKIE_SECURE=' .env; then sed -i 's/^COOKIE_SECURE=.*/COOKIE_SECURE="true"/' .env; else echo 'COOKIE_SECURE="true"' >> .env; fi
if grep -q '^COOKIE_SAMESITE=' .env; then sed -i 's/^COOKIE_SAMESITE=.*/COOKIE_SAMESITE="lax"/' .env; else echo 'COOKIE_SAMESITE="lax"' >> .env; fi

echo "==> 5/6  Nginx"
sudo cp "$APP_DIR/deploy/nginx-restaurante.conf" /etc/nginx/sites-available/restaurante
sudo sed -i "s#REPLACE_ROOT#$APP_DIR/frontend/build#g" /etc/nginx/sites-available/restaurante
sudo ln -sf /etc/nginx/sites-available/restaurante /etc/nginx/sites-enabled/restaurante
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
sudo ufw allow 'Nginx Full' 2>/dev/null || { sudo ufw allow 80/tcp; sudo ufw allow 443/tcp; } || true

echo "==> 6/6  Backend (systemd) — garante que o uvicorn corre em 127.0.0.1:8001"
cat <<SERVICE | sudo tee /etc/systemd/system/viva-backend.service >/dev/null
[Unit]
Description=Viva Setubal API
After=network.target mongod.service

[Service]
User=$USER
WorkingDirectory=$APP_DIR/backend
ExecStart=$APP_DIR/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE
sudo systemctl daemon-reload
sudo systemctl enable --now viva-backend

echo ""
echo "======================================================"
echo " PRONTO. Abre no browser:  https://$HOST"
echo " (cert self-signed: o browser vai pedir para aceitar a exceção 1x)"
echo " Já NÃO precisas do 'yarn start' — o Nginx serve o build."
echo "======================================================"
