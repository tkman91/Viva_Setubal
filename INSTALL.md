# 🏗️ Instalação de raiz — VM Ubuntu 24.04 (Noble)

Guia end-to-end para a app **Gestão de Restaurante** com HTTPS via **DuckDNS (DNS-01)** e portas externas não-standard (ex.: `10443→443`, `10080→80`) e/ou **Twingate**.

> Assume que o repositório fica em `~/Viva_Setubal`. Ajusta se usares outra pasta.

---

## 0. Pré-requisitos (fora da VM)

- **DuckDNS**: o domínio `tkman91.duckdns.org` deve **apontar para o teu IP WAN** (atualiza no duckdns.org ou por cliente DDNS).
- **Router**: port-forward `10443 → IP_DA_VM:443` (o `10080 → :80` é opcional com DNS-01).
- Tem à mão o **token DuckDNS** (topo de https://www.duckdns.org depois de entrares).
- (Opcional) **Twingate**: adiciona a VM como *Resource* para acesso privado.

---

## 1. Preparar a VM e clonar o projeto

```bash
sudo apt update && sudo apt install -y git
cd ~
git clone https://github.com/<o-teu-utilizador>/<o-teu-repo>.git Viva_Setubal
cd Viva_Setubal
```

## 2. Backend + MongoDB (script automático)

```bash
bash scripts/setup_ubuntu.sh
```
Instala o MongoDB 8.0, cria o virtualenv, instala `requirements-selfhost.txt` (inclui `reportlab` para os talões PDF) e cria `backend/.env`.

## 3. Frontend — instalar dependências (Node 20 + Yarn)

```bash
# Node 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
# Remover o "yarn" falso do cmdtest e ativar o Yarn real
sudo apt remove -y cmdtest yarn 2>/dev/null || true
sudo corepack enable && corepack prepare yarn@1.22.22 --activate && hash -r
yarn --version    # deve imprimir 1.22.22

cd ~/Viva_Setubal/frontend
yarn install
cd ~/Viva_Setubal
```

## 4. HTTPS (DuckDNS/DNS-01) + BUILD de produção — sem abrir portas

```bash
# <dominio-duckdns> <email> <token> [porta-https-externa]
bash scripts/setup_https_duckdns.sh tkman91.duckdns.org teu@email.pt SEU_TOKEN 10443
```
Isto: emite o certificado por DNS-01, **compila o frontend** (`yarn build`) e publica-o em `/var/www/restaurante`, configura o Nginx para **servir o build estático** (`/`) e fazer proxy do `/api` → backend, acerta os `.env` (`COOKIE_SECURE="true"`, `CORS_ORIGINS` com a porta) e instala a **renovação automática**.

> O frontend passa a ser servido **estático pelo Nginx** — já **não** corres `yarn start`. Só o backend precisa de estar a correr.

## 5. Arranque automático (systemd) — só o backend

**Backend** — `/etc/systemd/system/viva-backend.service`:
```ini
[Unit]
Description=Viva Setubal API
After=network.target mongod.service

[Service]
User=root
WorkingDirectory=/root/Viva_Setubal/backend
ExecStart=/root/Viva_Setubal/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

Ativar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now viva-backend
sudo systemctl status viva-backend --no-pager
```

> O frontend não tem serviço — é estático (Nginx). O `nginx` e o `mongod` já arrancam sozinhos no boot.

## 6. Aceder e configurar

1. Abre **`https://tkman91.duckdns.org:10443`** (ou pelo nome no Twingate).
2. Entra com o admin (por defeito `admin@restaurante.pt` / `admin123` — muda em `backend/.env`).
3. **Definições** → localização + raio do restaurante (para a picagem).
4. **Config POS** → zonas & mesas, categorias, modificadores, menus/combos, métodos de pagamento, IVA, cabeçalho do talão e (opcional) faturação.
5. **Stock** → produtos. **Gestão de Staff** → funcionários e permissões.

---

## 📲 Instalar como app (PWA)

A app é uma **PWA instalável** (requer HTTPS — já garantido pelo DuckDNS).

- **Android/Chrome:** abre `https://tkman91.duckdns.org:10443`, menu ⋮ → **"Instalar app"** / "Adicionar ao ecrã principal".
- **iPhone/Safari:** botão **Partilhar** → **"Adicionar ao ecrã principal"**.
- Fica um ícone no telemóvel que abre a app em **ecrã cheio** (sem barra do browser).

> A app é servida pelo **build de produção** (Nginx) — PWA completa e mais rápida/estável.

## 🔄 Atualizar a app (após `git pull`)

```bash
cd ~/Viva_Setubal && git pull
# se mudou o backend:
sudo systemctl restart viva-backend
# se mudou o frontend (recompila e republica o build):
bash scripts/build_frontend.sh
```

## ✅ Verificações rápidas

```bash
# Backend responde?
curl -sk https://tkman91.duckdns.org:10443/api/ | head
# Certificado válido e renovação OK?
sudo /opt/certbot/bin/certbot certificates
sudo /opt/certbot/bin/certbot renew --dry-run
# Serviços a correr?
sudo systemctl is-active mongod viva-backend nginx
```

## 🛠️ Se algo falhar
- **Login não guarda sessão** → confirma HTTPS a funcionar e `COOKIE_SECURE="true"` em `backend/.env`; reinicia `viva-backend`.
- **CORS/OPTIONS 400** → `CORS_ORIGINS` tem de conter **exatamente** `https://tkman91.duckdns.org:10443`.
- **certbot DNS-01 falha** → confirma o token e que o domínio existe no DuckDNS; vê `sudo journalctl -u certbot-duckdns`.
- Ver o resto em [`DEPLOY_UBUNTU.md`](./DEPLOY_UBUNTU.md) (tabela de erros comuns).
