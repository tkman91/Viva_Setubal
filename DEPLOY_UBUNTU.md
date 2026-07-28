# 🚀 Deploy numa VM Ubuntu 24.04 (Noble) — passo-a-passo

> ⚠️ **Erro comum:** correr `apt install uvicorn` e depois `uvicorn ...` usa o **Python do sistema** e dá
> `ModuleNotFoundError: No module named 'dotenv'`. No Ubuntu Noble **tens de usar um virtualenv** — o
> `pip install` global está bloqueado (PEP 668). Segue os passos abaixo.

## Opção A — Script automático (recomendado)

Depois de clonares o repositório:

```bash
cd ~/Viva_Setubal
bash scripts/setup_ubuntu.sh
```

O script instala o MongoDB, cria o virtualenv, instala as dependências e cria o `backend/.env`.
No fim, arranca o backend:

```bash
cd backend
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001
```

---

## Opção B — Manual

### 1. Pacotes de sistema
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip curl gnupg
```

### 2. MongoDB 8.0 (não vem nos repositórios base do Noble)
```bash
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl enable --now mongod
systemctl status mongod        # deve estar "active (running)"
```

### 3. Backend (FastAPI) — SEMPRE dentro de um virtualenv
```bash
cd ~/Viva_Setubal/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-selfhost.txt
```
> Usa `requirements-selfhost.txt` (só as dependências de runtime).
> **Não** uses o `requirements.txt` completo numa VM externa — ele contém pacotes
> do ambiente Emergent (ex.: `emergentintegrations`) que não estão no PyPI e fazem o `pip install` falhar.

### 4. Criar o ficheiro `backend/.env` (não vem no git!)
```bash
cat > .env <<'EOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="viva_setubal"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="COLA_AQUI_UMA_CHAVE_ALEATORIA"
ADMIN_EMAIL="admin@restaurante.pt"
ADMIN_PASSWORD="admin123"
COOKIE_SECURE="false"
COOKIE_SAMESITE="lax"
EOF
```
> 🔑 **`COOKIE_SECURE="false"` + `COOKIE_SAMESITE="lax"` são essenciais em HTTP** (sem HTTPS).
> Sem isto o browser recusa guardar o cookie de sessão e o login "não funciona".
> Quando tiveres HTTPS/domínio, muda para `COOKIE_SECURE="true"` e `COOKIE_SAMESITE="none"`.
Gera a chave JWT:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Arrancar o backend
```bash
# (com o venv ativo)
uvicorn server:app --host 0.0.0.0 --port 8001
```
Testar noutra shell:
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@restaurante.pt","password":"admin123"}'
```
Deve devolver `{"user": {...}}`.

### 6. Frontend (React)
```bash
# Node 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# IMPORTANTE: remover o "yarn" falso do pacote cmdtest (senao da erro
# "[Errno 2] No such file or directory: 'install'")
sudo apt remove -y cmdtest yarn 2>/dev/null || true

# Yarn real via Corepack (vem com o Node 20)
sudo corepack enable
corepack prepare yarn@1.22.22 --activate
hash -r
yarn --version        # deve imprimir 1.22.22

cd ~/Viva_Setubal/frontend
echo 'REACT_APP_BACKEND_URL=http://localhost:8001' > .env
yarn install
yarn start            # abre em http://localhost:3000
```

---

## Deixar a correr em produção (systemd) — opcional

`/etc/systemd/system/viva-backend.service`:
```ini
[Unit]
Description=Viva Setubal API
After=network.target mongod.service

[Service]
User=root
WorkingDirectory=/root/Viva_Setubal/backend
ExecStart=/root/Viva_Setubal/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now viva-backend
```

---

## Erros frequentes

| Erro | Causa | Solução |
|------|-------|---------|
| `ModuleNotFoundError: No module named 'dotenv'` | uvicorn do sistema (apt) sem deps | usar venv + `pip install -r requirements-selfhost.txt` |
| `KeyError: 'MONGO_URL'` | falta o `backend/.env` | criar o `.env` (passo 4) |
| `ServerSelectionTimeoutError` | MongoDB não está a correr | `sudo systemctl start mongod` |
| `error: externally-managed-environment` | `pip` global no Noble | criar e ativar um virtualenv |
| `pip` falha em `emergentintegrations` | requirements.txt do Emergent | usar `requirements-selfhost.txt` |
| `ERROR: [Errno 2] No such file or directory: 'install'` (no `yarn install`) | `yarn` falso do pacote **cmdtest** a mascarar o Yarn real | `sudo apt remove -y cmdtest yarn && sudo corepack enable && corepack prepare yarn@1.22.22 --activate && hash -r` |
| Login não funciona (fica preso no ecrã de login em HTTP) | Cookie de sessão exige HTTPS (`Secure`/`SameSite=None`) | pôr `COOKIE_SECURE="false"` e `COOKIE_SAMESITE="lax"` no `backend/.env` e reiniciar o backend |
| Login falha por rede / não chega ao backend | `REACT_APP_BACKEND_URL` errado para o browser que usas | usar o endereço que o **browser** alcança (ex.: `http://IP_DA_VM:8001`), não `localhost` se acederes de outra máquina; rebuild/reiniciar `yarn start` |
