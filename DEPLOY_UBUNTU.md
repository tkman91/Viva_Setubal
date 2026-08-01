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

O bloco abaixo **gera automaticamente** a chave JWT e cria o `.env`:
```bash
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
cat > .env <<EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="viva_setubal"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="$JWT_SECRET"
ADMIN_EMAIL="admin@restaurante.pt"
ADMIN_PASSWORD="admin123"
COOKIE_SECURE="false"
COOKIE_SAMESITE="lax"
EOF
```
> 🔑 Para gerar uma chave JWT avulsa (ex.: para trocar a existente):
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```
> ⚠️ **`COOKIE_SECURE="false"` + `COOKIE_SAMESITE="lax"` são essenciais em HTTP** (sem HTTPS).
> Sem isto o browser recusa guardar o cookie de sessão e o login "não funciona".
> Quando tiveres HTTPS/domínio, muda para `COOKIE_SECURE="true"` e `COOKIE_SAMESITE="none"`.

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

## 🔒 HTTPS (Nginx reverse proxy)

Recomendado: Nginx à frente serve o frontend e faz proxy de `/api` para o uvicorn — **uma única origem HTTPS** (adeus problemas de CORS/cookies).

### A) Domínio público + Let's Encrypt (cert válido)
Pré-requisitos no router: **port-forward TCP 80 e 443** → IP da VM, e o domínio a resolver para o teu IP WAN.
```bash
cd ~/Viva_Setubal
bash scripts/setup_https_letsencrypt.sh SEU_DOMINIO teu@email.pt
```
Mantém o `yarn start` em dev atrás do Nginx (config `deploy/nginx-restaurante-dev.conf`), emite o certificado, e acerta os `.env`
(frontend passa a chamar `/api` na mesma origem; backend fica com `COOKIE_SECURE="true"`).

### B) Só LAN (sem domínio) — certificado self-signed
```bash
cd ~/Viva_Setubal
bash scripts/setup_https.sh 192.168.1.16     # serve o BUILD de produção via Nginx
```

> Depois do HTTPS acede sempre pelo **domínio/host do certificado** (não pelo IP cru).
> Renovação Let's Encrypt: automática (`systemctl list-timers | grep certbot`).

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
| `OPTIONS /api/auth/login 400 Bad Request` (preflight CORS) | O `Origin` do browser não está em `CORS_ORIGINS` | pôr em `backend/.env` `CORS_ORIGINS="http://IP_DA_VM:3000,http://localhost:3000"` (tem de coincidir EXATAMENTE com o endereço/porta na barra do browser) e reiniciar o backend |
| `OPTIONS ... 400` continua mesmo com o `CORS_ORIGINS` aparentemente certo | `.env` não recarregado (o `--reload` do uvicorn NÃO relê o `.env`) ou origin diferente | **atalho para LAN/teste:** pôr `CORS_ORIGIN_REGEX=".*"` no `backend/.env` e **matar/reabrir** o uvicorn. Confirmar o `Origin` exato no separador Network (F12). O log do backend imprime `CORS config -> origins=... regex=...` no arranque. |
| Browser do PC dá **timeout** em `:3000`/`:8001` mas o **SSH funciona** | Firewall a "dropar" pacotes: `ufw` na VM e/ou firewall do **Proxmox** (só o 22 está permitido) | Na VM: `sudo ufw allow 3000/tcp && sudo ufw allow 8001/tcp`. No Proxmox: **VM → Firewall** desativar (teste) ou permitir tcp 3000/8001. Arrancar o frontend com `HOST=0.0.0.0 yarn start`. |
| `Failed to compile` / `Can't resolve src/index.js` + `[VisualEditsPlugin] ... ENOENT ... visual-edit-overlay.js` | plugin `@emergentbase/visual-edits` (editor Emergent) falha fora do Emergent e parte a compilação | `git pull` (o `craco.config.js` já ignora o plugin quando o overlay não existe). Alternativa imediata sem pull: `DISABLE_VISUAL_EDITS=true HOST=0.0.0.0 yarn start` ou `yarn remove @emergentbase/visual-edits && yarn start` |
| `certbot` falha a validar (HTTP-01) | ISP bloqueia a porta 80 ou tens **CGNAT** (o IP WAN não é mesmo teu) | usar validação **DNS-01** (`certbot certonly --dns-<provedor>`), que não precisa de abrir portas |
