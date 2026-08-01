#!/usr/bin/env bash
# HTTPS com Let's Encrypt (HTTP-01) para a app, mantendo o `yarn start` em dev atrás do Nginx.
# Uso:  bash scripts/setup_https_letsencrypt.sh <DOMINIO> <EMAIL>
# Ex.:  bash scripts/setup_https_letsencrypt.sh vivasetubal.tkman91.linkpc.net teu@email.pt
#
# PRÉ-REQUISITOS (no router):
#   - Port-forward TCP 80 e 443 do WAN -> 192.168.1.16 (esta VM)
#   - O domínio (DDNS linkpc) tem de resolver para o teu IP WAN
set -e

DOMAIN="${1:-vivasetubal.tkman91.linkpc.net}"
EMAIL="${2:?Indica o teu email: bash scripts/setup_https_letsencrypt.sh $DOMAIN teu@email.pt}"
APP_DIR="$HOME/Viva_Setubal"

echo "==> 1/6  Pacotes"
sudo apt-get update
sudo apt-get install -y nginx certbot

echo "==> 2/6  Firewall 80/443"
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true

echo "==> 3/6  Nginx temporário (HTTP) para a validação ACME"
sudo mkdir -p /var/www/html/.well-known/acme-challenge
sudo tee /etc/nginx/sites-available/restaurante >/dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 200 'ok'; }
}
EOF
sudo ln -sf /etc/nginx/sites-available/restaurante /etc/nginx/sites-enabled/restaurante
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo "==> 4/6  Emitir certificado Let's Encrypt (HTTP-01)"
sudo certbot certonly --webroot -w /var/www/html -d "$DOMAIN" \
  --agree-tos -m "$EMAIL" --no-eff-email -n \
  --deploy-hook "systemctl reload nginx"

echo "==> 5/6  Config final (proxy dev + TLS)"
sudo cp "$APP_DIR/deploy/nginx-restaurante-dev.conf" /etc/nginx/sites-available/restaurante
sudo sed -i "s/SEU_DOMINIO/$DOMAIN/g" /etc/nginx/sites-available/restaurante
sudo nginx -t && sudo systemctl restart nginx

echo "==> 6/6  Envs (frontend dev atrás do proxy + backend cookie Secure)"
cd "$APP_DIR/frontend"
cat > .env <<EOF
REACT_APP_BACKEND_URL=
WDS_SOCKET_PORT=443
DANGEROUSLY_DISABLE_HOST_CHECK=true
EOF
cd "$APP_DIR/backend"
if grep -q '^COOKIE_SECURE=' .env; then sed -i 's/^COOKIE_SECURE=.*/COOKIE_SECURE="true"/' .env; else echo 'COOKIE_SECURE="true"' >> .env; fi
if grep -q '^COOKIE_SAMESITE=' .env; then sed -i 's/^COOKIE_SAMESITE=.*/COOKIE_SAMESITE="lax"/' .env; else echo 'COOKIE_SAMESITE="lax"' >> .env; fi

echo ""
echo "======================================================"
echo " HTTPS pronto para https://$DOMAIN"
echo " Agora reinicia os serviços:"
echo "   Backend:  sudo systemctl restart viva-backend   (ou reinicia o uvicorn em 127.0.0.1:8001)"
echo "   Frontend: cd $APP_DIR/frontend && yarn start     (fica em 127.0.0.1:3000)"
echo " Renovação automática: systemctl list-timers | grep certbot"
echo "======================================================"
