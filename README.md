# 🍽️ Gestão de Restaurante

Aplicação full-stack para gestão de restaurante: **controlo de stock**, **picagem de ponto com geolocalização**, **gestão de staff com permissões por módulo**, **consumo do staff** e uma **registadora (POS) com mesas** que desconta o stock automaticamente.

**Stack:** React 19 + FastAPI + MongoDB · Interface PT-PT · Moeda € · Auth por cookie httpOnly

> 🚀 **Deploy numa VM / HTTPS:** ver [`DEPLOY_UBUNTU.md`](./DEPLOY_UBUNTU.md) e os scripts em [`scripts/`](./scripts).
> 🔑 **Permissões:** só o `admin` tem acesso total; o admin escolhe por módulo o que cada `gestor`/`funcionario` vê.

---

## 📋 Pré-requisitos

Instala o seguinte na tua máquina antes de começar:

| Ferramenta | Versão recomendada | Verificar |
|------------|--------------------|-----------|
| **Python** | 3.11+ | `python3 --version` |
| **Node.js**| 18+ ou 20+ | `node --version` |
| **Yarn**   | 1.22+ | `yarn --version` |
| **MongoDB**| 6.0+ | `mongod --version` |
| **Git**    | qualquer | `git --version` |

> ⚠️ **Usa sempre `yarn`** no frontend (não `npm`) — o projeto usa `yarn.lock` e resolutions específicas.

### Instalar o Yarn (se necessário)
```bash
npm install -g yarn
```

### Instalar o MongoDB
- **macOS (Homebrew):**
  ```bash
  brew tap mongodb/brew
  brew install mongodb-community@7.0
  brew services start mongodb-community@7.0
  ```
- **Ubuntu/Debian:** segue o guia oficial → https://www.mongodb.com/docs/manual/administration/install-on-linux/
- **Windows:** instalador oficial → https://www.mongodb.com/try/download/community
- **Alternativa (sem instalar):** usa o [MongoDB Atlas](https://www.mongodb.com/atlas) (gratuito na nuvem) e usa a connection string no `.env`.

---

## 🚀 Instalação passo-a-passo

### 1. Clonar o repositório
```bash
git clone https://github.com/<o-teu-utilizador>/<o-teu-repo>.git
cd <o-teu-repo>
```

### 2. Configurar o Backend (FastAPI)

```bash
cd backend

# Criar e ativar ambiente virtual
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows (PowerShell)

# Instalar dependências
pip install -r requirements.txt
```

Cria o ficheiro **`backend/.env`** com o seguinte conteúdo:

```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="restaurante"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="troca-isto-por-uma-chave-aleatoria-de-64-caracteres"
ADMIN_EMAIL="admin@restaurante.pt"
ADMIN_PASSWORD="admin123"
```

> 🔐 Gera uma `JWT_SECRET` segura:
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```
> Se usares o **MongoDB Atlas**, substitui `MONGO_URL` pela tua connection string
> (ex: `mongodb+srv://user:pass@cluster.mongodb.net`).

**Iniciar o backend:**
```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```
O backend fica disponível em **http://localhost:8001** (API em `http://localhost:8001/api`).
Na primeira arrancada é criado automaticamente o utilizador **admin**.

### 3. Configurar o Frontend (React)

Abre **outro terminal**:

```bash
cd frontend
yarn install
```

Cria o ficheiro **`frontend/.env`**:

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

**Iniciar o frontend:**
```bash
yarn start
```
A aplicação abre em **http://localhost:3000**.

---

## 🔑 Credenciais de acesso (por defeito)

| Campo | Valor |
|-------|-------|
| Email | `admin@restaurante.pt` |
| Password | `admin123` |
| Perfil | `admin` (acesso total) |

> Define estes valores em `backend/.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`) **antes** do primeiro arranque.
> Depois de entrar, cria os restantes funcionários em **Gestão de Staff** e configura a localização do restaurante em **Definições** (necessário para a picagem de ponto).

---

## 🗂️ Estrutura do projeto

```
.
├── backend/
│   ├── server.py            # API FastAPI (todas as rotas sob /api)
│   ├── requirements.txt     # dependências Python
│   └── .env                 # variáveis de ambiente (NÃO versionar)
├── frontend/
│   ├── src/
│   │   ├── App.js           # rotas e providers
│   │   ├── context/         # AuthContext (autenticação)
│   │   ├── lib/api.js       # cliente axios + helpers (€)
│   │   ├── components/       # Layout + componentes UI (shadcn)
│   │   └── pages/            # Dashboard, Stock, Picagem, Staff, Consumo, Faturacao, Settings
│   ├── package.json
│   └── .env                 # REACT_APP_BACKEND_URL (NÃO versionar)
└── README.md
```

---

## ✅ Verificar que está tudo a funcionar

Com o backend a correr, testa a API:
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@restaurante.pt","password":"admin123"}'
```
Deves receber um JSON com `token` e `user`.

---

## 🧩 Módulos da aplicação

| Módulo | Descrição |
|--------|-----------|
| **Painel** | KPIs de stock, staff, consumo e alertas |
| **Picagem de Ponto** | Entrada/saída validada por raio de geolocalização (GPS do browser) |
| **Controlo de Stock** | Produtos, movimentos de entrada/saída, alertas de stock baixo |
| **Consumo Staff** | Registo de consumo (desconta stock + valor) |
| **Gestão de Staff** | Adicionar funcionários, funções e permissões por módulo |
| **Faturação** | Faturas com IVA (23/13/6/0%); botão "Emitir" preparado para integração externa (InvoiceXpress/Moloni) |
| **Definições** | Localização e raio do restaurante |

---

## 🛠️ Problemas comuns (Troubleshooting)

- **`pymongo.errors.ServerSelectionTimeoutError`** → o MongoDB não está a correr. Arranca o serviço (`brew services start mongodb-community` ou `sudo systemctl start mongod`).
- **CORS / pedidos bloqueados** → confirma que `CORS_ORIGINS` no `backend/.env` inclui `http://localhost:3000`.
- **Frontend não liga ao backend** → confirma `REACT_APP_BACKEND_URL=http://localhost:8001` em `frontend/.env` e **reinicia** o `yarn start` (variáveis `REACT_APP_*` só são lidas ao arrancar).
- **Picagem diz "localização não configurada"** → entra como admin e define coordenadas + raio em **Definições**.
- **Geolocalização não funciona** → o browser exige HTTPS ou `localhost`; permite o acesso à localização quando pedido.
- **`command not found: yarn`** → instala com `npm install -g yarn`.

---

## 📦 Build de produção (frontend)

```bash
cd frontend
yarn build
```
Os ficheiros otimizados ficam em `frontend/build/`, prontos a servir por qualquer servidor estático.

---

## 📄 .gitignore recomendado

Certifica-te de que **não versionas segredos nem dependências**. Cria um `.gitignore` na raiz:

```gitignore
# Python
backend/venv/
__pycache__/
*.pyc

# Node
frontend/node_modules/
frontend/build/

# Ambiente / segredos
.env
backend/.env
frontend/.env

# Sistema
.DS_Store
```
