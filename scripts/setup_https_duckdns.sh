#!/usr/bin/env bash
# HTTPS com Let's Encrypt via DNS-01 (DuckDNS) — NÃO precisa de abrir portas 80/443 standard.
# Ideal quando usas portas externas não-standard (ex.: 10443->443, 10080->80) e/ou Twingate.
#
# Uso:
#   bash scripts/setup_https_duckdns.sh <DOMINIO_DUCKDNS> <EMAIL> <DUCKDNS_TOKEN> [PORTA_HTTPS_EXTERNA]
# Ex.:
#   bash scripts/setup_https_duckdns.sh tkman91.duckdns.org teu@email.pt SEU_TOKEN_DUCKDNS 10443
#
# Onde obter o TOKEN: entra em https://www.duckdns.org (o "token" aparece no topo da página).
set -e

DOMAIN="${1:?Indica o dominio DuckDNS, ex: tkman91.duckdns.org}"
EMAIL="${2:?Indica o teu email para o certificado}"
DUCKDNS_TOKEN="${3:?Indica o teu token DuckDNS - ver https://www.duckdns.org}"
EXT_HTTPS_PORT="${4:-10443}"
APP_DIR="$HOME/Viva_Setubal"

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

echo "==> 5/7  Nginx (proxy HTTPS: / -> yarn start 3000, /api -> uvicorn 8001)"
sudo cp "$APP_DIR/deploy/nginx-restaurante-dev.conf" /etc/nginx/sites-available/restaurante
sudo sed -i "s/SEU_DOMINIO/$DOMAIN/g" /etc/nginx/sites-available/restaurante
# porta externa não-standard: preservar host:porta nos redirects
sudo sed -i "s#return 301 https://\$host\$request_uri;#return 301 https://\$host:$EXT_HTTPS_PORT\$request_uri;#" /etc/nginx/sites-available/restaurante
sudo ln -sf /etc/nginx/sites-available/restaurante /etc/nginx/sites-enabled/restaurante
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo "==> 6/7  Envs (frontend dev atrás do proxy + backend cookie Secure + CORS)"
cd "$APP_DIR/frontend"
cat > .env <<EOF
REACT_APP_BACKEND_URL=
WDS_SOCKET_PORT=$EXT_HTTPS_PORT
DANGEROUSLY_DISABLE_HOST_CHECK=true
EOF
cd "$APP_DIR/backend"
ORIGIN="https://$DOMAIN:$EXT_HTTPS_PORT"

set_env() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=\"${val}\"|" .env
  else
    printf '%s="%s"\n' "$key" "$val" >> .env
  fi
}
set_env COOKIE_SECURE "true"
set_env COOKIE_SAMESITE "lax"
set_env CORS_ORIGINS "${ORIGIN},https://${DOMAIN}"

echo "==> 7/7  Renovação automática (timer systemd via venv)"
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
echo " HTTPS pronto (DNS-01 / DuckDNS)."
echo " Acede em:  https://$DOMAIN:$EXT_HTTPS_PORT"
echo ""
echo " Reinicia os serviços da app:"
echo "   Backend:  sudo systemctl restart viva-backend   (ou reinicia o uvicorn 127.0.0.1:8001)"
echo "   Frontend: cd $APP_DIR/frontend && HOST=0.0.0.0 yarn start   (fica em 127.0.0.1:3000)"
echo ""
echo " Certificado: /etc/letsencrypt/live/$DOMAIN/"
echo " Renovação:   systemctl list-timers | grep certbot-duckdns"
echo " Testar renovação: sudo /opt/certbot/bin/certbot renew --dry-run"
echo "======================================================"
