#!/usr/bin/env bash
# HTTPS com Let's Encrypt via DNS-01 (DuckDNS) + FRONTEND EM BUILD DE PRODUCAO.
# NAO precisa de abrir portas 80/443 standard. Ideal p/ portas nao-standard (10443->443) e/ou Twingate.
#
# Uso:
#   bash scripts/setup_https_duckdns.sh <DOMINIO_DUCKDNS> <EMAIL> <DUCKDNS_TOKEN> [PORTA_HTTPS_EXTERNA]
# Ex.:
#   bash scripts/setup_https_duckdns.sh tkman91.duckdns.org teu@email.pt SEU_TOKEN 10443
#
# Onde obter o TOKEN: entra em https://www.duckdns.org (o "token" aparece no topo da pagina).
set -e

DOMAIN="${1:?Indica o dominio DuckDNS, ex: tkman91.duckdns.org}"
EMAIL="${2:?Indica o teu email para o certificado}"
DUCKDNS_TOKEN="${3:?Indica o teu token DuckDNS - ver https://www.duckdns.org}"
EXT_HTTPS_PORT="${4:-10443}"
APP_DIR="$HOME/Viva_Setubal"
WEB_ROOT="/var/www/restaurante"

echo "==> 1/7  Pacotes de sistema (nginx, python venv)"
sudo apt-get update
sudo apt-get install -y nginx python3-venv python3-full

echo "==> 2/7  Certbot + plugin DuckDNS num venv dedicado (/opt/certbot)"
sudo python3 -m venv /opt/certbot
sudo /opt/certbot/bin/pip install --upgrade pip
sudo /opt/certbot/bin/pip install certbot certbot-dns-duckdns
sudo ln -sf /opt/certbot/bin/certbot /usr/local/bin/certbot

echo "==> 3/7  Credenciais DuckDNS (ficheiro protegido)"
sudo mkdir -p /etc/letsencrypt
echo "dns_duckdns_token=$DUCKDNS_TOKEN" | sudo tee /etc/letsencrypt/duckdns.ini >/dev/null
sudo chmod 600 /etc/letsencrypt/duckdns.ini

echo "==> 4/7  Emitir certificado via DNS-01 (sem abrir portas)"
sudo /opt/certbot/bin/certbot certonly \
  --non-interactive --agree-tos -m "$EMAIL" --no-eff-email \
  --preferred-challenges dns \
  --authenticator dns-duckdns \
  --dns-duckdns-credentials /etc/letsencrypt/duckdns.ini \
  --dns-duckdns-propagation-seconds 60 \
  -d "$DOMAIN"

echo "==> 5/7  Envs + BUILD de producao do frontend"
# Frontend: chamadas a /api na mesma origem (funciona em qualquer porta)
cat > "$APP_DIR/frontend/.env" <<EOF
REACT_APP_BACKEND_URL=
EOF
# Backend: cookie Secure + CORS com a porta externa
cd "$APP_DIR/backend"
ORIGIN="https://$DOMAIN:$EXT_HTTPS_PORT"
set_env() {
  local key="$1"; local val="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=\"${val}\"|" .env
  else
    printf '%s="%s"\n' "$key" "$val" >> .env
  fi
}
set_env COOKIE_SECURE "true"
set_env COOKIE_SAMESITE "lax"
set_env CORS_ORIGINS "${ORIGIN},https://${DOMAIN}"
# Compilar e publicar o build
cd "$APP_DIR/frontend"
export CI=false
yarn install
yarn build
sudo rm -rf "$WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo cp -r build/* "$WEB_ROOT"/

echo "==> 6/7  Nginx (serve o build estatico + /api -> uvicorn 8001)"
sudo tee /etc/nginx/sites-available/restaurante >/dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location / { return 301 https://\$host:$EXT_HTTPS_PORT\$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 20m;

    root $WEB_ROOT;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    # PWA: sw.js e index.html sem cache (recebem updates); assets com hash em cache longa
    location = /sw.js      { add_header Cache-Control "no-cache"; }
    location = /index.html { add_header Cache-Control "no-cache"; }
    location /static/      { expires 1y; add_header Cache-Control "public, immutable"; }

    location / { try_files \$uri /index.html; }
}
EOF
sudo ln -sf /etc/nginx/sites-available/restaurante /etc/nginx/sites-enabled/restaurante
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo "==> 7/7  Renovacao automatica (timer systemd via venv)"
sudo tee /etc/systemd/system/certbot-duckdns.service >/dev/null <<'EOF'
[Unit]
Description=Renovar certificados Let's Encrypt (DuckDNS)
[Service]
Type=oneshot
ExecStart=/opt/certbot/bin/certbot renew --quiet --deploy-hook "systemctl reload nginx"
EOF
sudo tee /etc/systemd/system/certbot-duckdns.timer >/dev/null <<'EOF'
[Unit]
Description=Correr a renovacao DuckDNS 2x/dia
[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=1h
Persistent=true
[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now certbot-duckdns.timer

echo ""
echo "======================================================"
echo " HTTPS + build de producao prontos (DNS-01 / DuckDNS)."
echo " Acede em:  https://$DOMAIN:$EXT_HTTPS_PORT"
echo ""
echo " O frontend e servido ESTATICO pelo Nginx (nao precisas de 'yarn start')."
echo " So precisas do backend a correr:"
echo "   sudo systemctl restart viva-backend   (ou uvicorn 127.0.0.1:8001)"
echo ""
echo " Depois de cada 'git pull' com mudancas no frontend, recompila:"
echo "   bash scripts/build_frontend.sh"
echo ""
echo " Certificado: /etc/letsencrypt/live/$DOMAIN/  |  Renovar: sudo certbot renew --dry-run"
echo "======================================================"
