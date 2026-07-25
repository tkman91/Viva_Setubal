import os
import uuid
import math
import jwt
import bcrypt
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# DB + App setup
# ---------------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Gestão Restaurante API")
api_router = APIRouter(prefix="/api")

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restaurante")

MODULES = ["stock", "picagem", "staff", "consumo", "faturacao", "relatorios"]

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


security = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Não autenticado")
    token = creds.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado")
    user.pop("password_hash", None)
    return user


def has_permission(user: dict, module: str) -> bool:
    if user.get("role") in ("admin", "gestor"):
        return True
    return module in (user.get("permissions") or [])


def require_permission(module: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if not has_permission(user, module):
            raise HTTPException(status_code=403, detail="Sem permissão para este módulo")
        return user

    return dep


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("admin", "gestor"):
        raise HTTPException(status_code=403, detail="Apenas gestores")
    return user


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def clean(doc: dict) -> dict:
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class LoginInput(BaseModel):
    email: str
    password: str


class StaffCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "funcionario"  # admin | gestor | funcionario
    hourly_wage: float = 0.0
    phone: Optional[str] = ""
    permissions: List[str] = Field(default_factory=list)


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    hourly_wage: Optional[float] = None
    phone: Optional[str] = None
    permissions: Optional[List[str]] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    category: str = "Geral"
    unit: str = "un"
    quantity: float = 0.0
    min_quantity: float = 0.0
    cost_price: float = 0.0
    sale_price: float = 0.0


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    min_quantity: Optional[float] = None
    cost_price: Optional[float] = None
    sale_price: Optional[float] = None


class StockMovementInput(BaseModel):
    product_id: str
    type: str  # entrada | saida
    quantity: float
    note: Optional[str] = ""


class ClockInput(BaseModel):
    lat: float
    lng: float


class ConsumptionInput(BaseModel):
    staff_id: Optional[str] = None  # gestor pode registar por outro; senão próprio
    product_id: str
    quantity: float = 1.0
    deduct_stock: bool = True


class SettingsInput(BaseModel):
    restaurant_name: str
    lat: float
    lng: float
    radius_m: float = 100.0


class InvoiceItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    vat_rate: float = 23.0


class InvoiceCreate(BaseModel):
    client_name: str
    client_nif: Optional[str] = ""
    items: List[InvoiceItem]


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api_router.post("/auth/login")
async def login(data: LoginInput):
    email = data.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Conta desativada")
    token = create_access_token(user["id"])
    return {"token": token, "user": clean(dict(user))}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ---------------------------------------------------------------------------
# Staff routes
# ---------------------------------------------------------------------------
@api_router.get("/staff")
async def list_staff(user: dict = Depends(require_permission("staff"))):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users


@api_router.post("/staff")
async def create_staff(data: StaffCreate, user: dict = Depends(require_admin)):
    email = data.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email já registado")
    perms = data.permissions
    if data.role in ("admin", "gestor"):
        perms = MODULES
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "email": email,
        "password_hash": hash_password(data.password),
        "role": data.role,
        "hourly_wage": data.hourly_wage,
        "phone": data.phone,
        "permissions": perms,
        "active": True,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return clean(dict(doc))


@api_router.put("/staff/{staff_id}")
async def update_staff(staff_id: str, data: StaffUpdate, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": staff_id})
    if not target:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    if "password" in upd:
        upd["password_hash"] = hash_password(upd.pop("password"))
    if upd.get("role") in ("admin", "gestor"):
        upd["permissions"] = MODULES
    await db.users.update_one({"id": staff_id}, {"$set": upd})
    doc = await db.users.find_one({"id": staff_id}, {"_id": 0, "password_hash": 0})
    return doc


@api_router.delete("/staff/{staff_id}")
async def delete_staff(staff_id: str, user: dict = Depends(require_admin)):
    if staff_id == user["id"]:
        raise HTTPException(status_code=400, detail="Não pode eliminar a própria conta")
    await db.users.delete_one({"id": staff_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Products / Stock
# ---------------------------------------------------------------------------
@api_router.get("/products")
async def list_products(user: dict = Depends(get_current_user)):
    return await db.products.find({}, {"_id": 0}).to_list(1000)


@api_router.post("/products")
async def create_product(data: ProductCreate, user: dict = Depends(require_permission("stock"))):
    doc = {"id": str(uuid.uuid4()), **data.model_dump(), "created_at": now_iso()}
    await db.products.insert_one(doc)
    return clean(dict(doc))


@api_router.put("/products/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, user: dict = Depends(require_permission("stock"))):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.products.update_one({"id": product_id}, {"$set": upd})
    doc = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return doc


@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(require_permission("stock"))):
    await db.products.delete_one({"id": product_id})
    return {"ok": True}


@api_router.post("/stock/movement")
async def stock_movement(data: StockMovementInput, user: dict = Depends(require_permission("stock"))):
    product = await db.products.find_one({"id": data.product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    delta = data.quantity if data.type == "entrada" else -data.quantity
    new_qty = round(product["quantity"] + delta, 3)
    if new_qty < 0:
        raise HTTPException(status_code=400, detail="Stock insuficiente")
    await db.products.update_one({"id": data.product_id}, {"$set": {"quantity": new_qty}})
    mv = {
        "id": str(uuid.uuid4()),
        "product_id": data.product_id,
        "product_name": product["name"],
        "type": data.type,
        "quantity": data.quantity,
        "note": data.note,
        "user_id": user["id"],
        "user_name": user["name"],
        "created_at": now_iso(),
    }
    await db.stock_movements.insert_one(mv)
    return clean(dict(mv))


@api_router.get("/stock/movements")
async def list_movements(user: dict = Depends(require_permission("stock"))):
    return await db.stock_movements.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


# ---------------------------------------------------------------------------
# Settings (localização do restaurante)
# ---------------------------------------------------------------------------
@api_router.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    s = await db.settings.find_one({"id": "main"}, {"_id": 0})
    return s or {}


@api_router.put("/settings")
async def update_settings(data: SettingsInput, user: dict = Depends(require_admin)):
    doc = {"id": "main", **data.model_dump()}
    await db.settings.update_one({"id": "main"}, {"$set": doc}, upsert=True)
    return doc


# ---------------------------------------------------------------------------
# Picagem de Ponto
# ---------------------------------------------------------------------------
@api_router.post("/timeclock/punch")
async def punch(data: ClockInput, user: dict = Depends(require_permission("picagem"))):
    settings = await db.settings.find_one({"id": "main"})
    if not settings:
        raise HTTPException(status_code=400, detail="Localização do restaurante não configurada")
    dist = haversine(data.lat, data.lng, settings["lat"], settings["lng"])
    if dist > settings["radius_m"]:
        raise HTTPException(
            status_code=403,
            detail=f"Está a {int(dist)}m do restaurante (limite {int(settings['radius_m'])}m). Aproxime-se para picar.",
        )
    open_entry = await db.time_entries.find_one({"user_id": user["id"], "clock_out": None})
    if open_entry:
        out = now_iso()
        seconds = (datetime.fromisoformat(out) - datetime.fromisoformat(open_entry["clock_in"])).total_seconds()
        await db.time_entries.update_one(
            {"id": open_entry["id"]},
            {"$set": {"clock_out": out, "clock_out_lat": data.lat, "clock_out_lng": data.lng, "duration_seconds": seconds}},
        )
        return {"action": "saida", "distance_m": int(dist), "duration_seconds": seconds}
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user["name"],
        "clock_in": now_iso(),
        "clock_in_lat": data.lat,
        "clock_in_lng": data.lng,
        "clock_out": None,
        "duration_seconds": 0,
    }
    await db.time_entries.insert_one(entry)
    return {"action": "entrada", "distance_m": int(dist)}


@api_router.get("/timeclock/status")
async def clock_status(user: dict = Depends(get_current_user)):
    open_entry = await db.time_entries.find_one({"user_id": user["id"], "clock_out": None}, {"_id": 0})
    return {"clocked_in": open_entry is not None, "entry": open_entry}


@api_router.get("/timeclock/entries")
async def clock_entries(user: dict = Depends(get_current_user)):
    if has_permission(user, "picagem") and user.get("role") in ("admin", "gestor"):
        entries = await db.time_entries.find({}, {"_id": 0}).sort("clock_in", -1).to_list(300)
    else:
        entries = await db.time_entries.find({"user_id": user["id"]}, {"_id": 0}).sort("clock_in", -1).to_list(100)
    return entries


# ---------------------------------------------------------------------------
# Consumo do Staff
# ---------------------------------------------------------------------------
@api_router.post("/consumption")
async def register_consumption(data: ConsumptionInput, user: dict = Depends(require_permission("consumo"))):
    product = await db.products.find_one({"id": data.product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    target_id = data.staff_id or user["id"]
    if target_id != user["id"] and user.get("role") not in ("admin", "gestor"):
        raise HTTPException(status_code=403, detail="Sem permissão para registar por outro")
    target = await db.users.find_one({"id": target_id})
    if not target:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    if data.deduct_stock:
        new_qty = round(product["quantity"] - data.quantity, 3)
        if new_qty < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        await db.products.update_one({"id": data.product_id}, {"$set": {"quantity": new_qty}})
    value = round(product.get("sale_price", 0.0) * data.quantity, 2)
    doc = {
        "id": str(uuid.uuid4()),
        "staff_id": target_id,
        "staff_name": target["name"],
        "product_id": data.product_id,
        "product_name": product["name"],
        "quantity": data.quantity,
        "unit_price": product.get("sale_price", 0.0),
        "value": value,
        "deducted_stock": data.deduct_stock,
        "created_at": now_iso(),
    }
    await db.consumptions.insert_one(doc)
    return clean(dict(doc))


@api_router.get("/consumption")
async def list_consumption(user: dict = Depends(get_current_user)):
    if has_permission(user, "consumo") and user.get("role") in ("admin", "gestor"):
        items = await db.consumptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    else:
        items = await db.consumptions.find({"staff_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


# ---------------------------------------------------------------------------
# Faturação (estrutura preparada)
# ---------------------------------------------------------------------------
@api_router.get("/invoices")
async def list_invoices(user: dict = Depends(require_permission("faturacao"))):
    return await db.invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)


@api_router.post("/invoices")
async def create_invoice(data: InvoiceCreate, user: dict = Depends(require_permission("faturacao"))):
    subtotal = 0.0
    vat_total = 0.0
    items = []
    for it in data.items:
        line = round(it.quantity * it.unit_price, 2)
        vat = round(line * it.vat_rate / 100, 2)
        subtotal += line
        vat_total += vat
        items.append({**it.model_dump(), "line_total": line, "vat_amount": vat})
    total = round(subtotal + vat_total, 2)
    count = await db.invoices.count_documents({})
    doc = {
        "id": str(uuid.uuid4()),
        "number": f"FT {datetime.now(timezone.utc).year}/{count + 1:04d}",
        "client_name": data.client_name,
        "client_nif": data.client_nif,
        "items": items,
        "subtotal": round(subtotal, 2),
        "vat_total": round(vat_total, 2),
        "total": total,
        "status": "rascunho",
        "external_synced": False,
        "created_by": user["name"],
        "created_at": now_iso(),
    }
    await db.invoices.insert_one(doc)
    return clean(dict(doc))


@api_router.post("/invoices/{invoice_id}/sync")
async def sync_invoice(invoice_id: str, user: dict = Depends(require_permission("faturacao"))):
    # Estrutura preparada para integração externa (InvoiceXpress/Moloni)
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {"external_synced": True, "status": "emitida", "synced_at": now_iso()}},
    )
    return {"ok": True, "message": "Fatura marcada como emitida (integração externa a ligar futuramente)"}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@api_router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    low_stock = [p for p in products if p["quantity"] <= p["min_quantity"]]
    stock_value = round(sum(p["quantity"] * p.get("cost_price", 0) for p in products), 2)
    staff_count = await db.users.count_documents({"active": True})
    active_now = await db.time_entries.count_documents({"clock_out": None})
    today = datetime.now(timezone.utc).date().isoformat()
    consumptions = await db.consumptions.find({}, {"_id": 0}).to_list(1000)
    today_consumption = round(
        sum(c["value"] for c in consumptions if c["created_at"][:10] == today), 2
    )
    total_consumption = round(sum(c["value"] for c in consumptions), 2)
    # consumo por dia (últimos 7 dias)
    by_day = {}
    for i in range(6, -1, -1):
        d = (datetime.now(timezone.utc).date() - timedelta(days=i)).isoformat()
        by_day[d] = 0.0
    for c in consumptions:
        d = c["created_at"][:10]
        if d in by_day:
            by_day[d] += c["value"]
    trend = [{"day": d[5:], "value": round(v, 2)} for d, v in by_day.items()]
    return {
        "products_count": len(products),
        "low_stock_count": len(low_stock),
        "low_stock": low_stock[:10],
        "stock_value": stock_value,
        "staff_count": staff_count,
        "active_now": active_now,
        "today_consumption": today_consumption,
        "total_consumption": total_consumption,
        "trend": trend,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@restaurante.pt").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "name": "Administrador",
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "role": "admin",
            "hourly_wage": 0.0,
            "phone": "",
            "permissions": MODULES,
            "active": True,
            "created_at": now_iso(),
        })
        logger.info("Admin criado: %s", admin_email)
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})


@api_router.get("/")
async def root():
    return {"message": "Gestão Restaurante API"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
