#!/usr/bin/env bash
# Recompila o frontend (build de producao) e publica-o para o Nginx servir.
# Corre isto depois de cada 'git pull' que altere o frontend.
set -e
APP_DIR="$HOME/Viva_Setubal"
WEB_ROOT="/var/www/restaurante"

cd "$APP_DIR/frontend"
export CI=false
yarn install
yarn build

sudo rm -rf "$WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo cp -r build/* "$WEB_ROOT"/
sudo systemctl reload nginx || true

echo "Frontend publicado em $WEB_ROOT (Nginx recarregado)."
