#!/usr/bin/env bash
# Setup e arranque do backend numa VM Ubuntu 24.04 (Noble)
# Uso:  cd ~/Viva_Setubal/backend  &&  bash ../scripts/setup_ubuntu.sh
set -e

echo "==> 1/6  Pacotes de sistema (python venv, node, yarn, mongo tools)"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip curl gnupg

echo "==> 2/6  Instalar MongoDB 8.0 (se ainda nao existir)"
if ! command -v mongod >/dev/null 2>&1; then
  curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
  echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
  sudo apt-get update
  sudo apt-get install -y mongodb-org
fi
sudo systemctl enable --now mongod
echo "    MongoDB estado:" && systemctl is-active mongod

echo "==> 3/6  Virtualenv Python + dependencias do backend"
cd "$(dirname "$0")/../backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-selfhost.txt

echo "==> 4/6  Criar backend/.env (se nao existir)"
if [ ! -f .env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > .env <<EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="viva_setubal"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="$SECRET"
ADMIN_EMAIL="admin@restaurante.pt"
ADMIN_PASSWORD="admin123"
COOKIE_SECURE="false"
COOKIE_SAMESITE="lax"
EOF
  echo "    .env criado."
else
  echo "    .env ja existe, mantido."
fi

echo "==> 5/6  Backend pronto. Arrancar com:"
echo "    cd backend && source venv/bin/activate && uvicorn server:app --host 0.0.0.0 --port 8001"

echo "==> 6/6  FIM. (Para o frontend: cd frontend && yarn install && yarn start)"
