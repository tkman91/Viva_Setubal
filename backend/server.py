import os
import uuid
import math
import asyncio
import jwt
import bcrypt
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
import io

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
COOKIE_MAX_AGE = 7 * 24 * 3600
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "none").lower()
if COOKIE_SAMESITE not in ("lax", "strict", "none"):
    COOKIE_SAMESITE = "lax"
if COOKIE_SAMESITE == "none":
    COOKIE_SECURE = True  # browsers exigem Secure quando SameSite=None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restaurante")

MODULES = ["stock", "picagem", "staff", "consumo", "faturacao", "relatorios", "menus"]

# Fecho automático de ponto: se não houver sinal (heartbeat) durante este tempo, fecha por "no_signal".
AUTO_CHECKOUT_GRACE_SECONDS = 300  # 5 minutos
WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
LATE_TOLERANCE_MIN = 5
try:
    LISBON = ZoneInfo("Europe/Lisbon")
except Exception:
    LISBON = timezone.utc

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
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    token = request.cookies.get("access_token")
    if not token and creds is not None:
        token = creds.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
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
    await enrich_role(user)
    return user


async def enrich_role(user: dict) -> dict:
    """Deriva permissões/flags a partir do cargo (fonte de verdade), a cada pedido."""
    role = None
    if user.get("role_id"):
        role = await db.roles.find_one({"id": user["role_id"]}, {"_id": 0})
    if role is None:
        role = await db.roles.find_one({"name": user.get("role")}, {"_id": 0})
    if role:
        user["role_id"] = role["id"]
        user["role"] = role["name"]
        user["is_admin"] = bool(role.get("is_admin"))
        user["is_supervisor"] = bool(role.get("is_supervisor")) or bool(role.get("is_admin"))
        user["permissions"] = MODULES if role.get("is_admin") else list(role.get("modules") or [])
        user["rank"] = int(role.get("rank") or 0)
        user["is_system"] = bool(role.get("is_system"))
    else:
        legacy = user.get("role")
        user["is_admin"] = legacy == "admin"
        user["is_supervisor"] = legacy in ("admin", "gestor")
        user["permissions"] = MODULES if legacy == "admin" else list(user.get("permissions") or [])
        user["rank"] = 100 if legacy == "admin" else 0
        user["is_system"] = legacy == "admin"
    return user


def has_permission(user: dict, module: str) -> bool:
    if user.get("is_admin"):
        return True
    return module in (user.get("permissions") or [])


def can_manage(user: dict, module: str) -> bool:
    """Âmbito de gestão/supervisão: admin, ou cargo supervisor com a permissão do módulo."""
    if user.get("is_admin"):
        return True
    return bool(user.get("is_supervisor")) and module in (user.get("permissions") or [])


def require_permission(module: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if not has_permission(user, module):
            raise HTTPException(status_code=403, detail="Sem permissão para este módulo")
        return user

    return dep


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas o administrador")
    return user


def require_manage(module: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if not can_manage(user, module):
            raise HTTPException(status_code=403, detail="Sem permissão de gestão para este módulo")
        return user

    return dep


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


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


class RoleInput(BaseModel):
    name: str
    modules: List[str] = Field(default_factory=list)
    is_supervisor: bool = False


class StaffCreate(BaseModel):
    name: str
    email: str
    password: str
    role_id: str
    hourly_wage: float = 0.0
    phone: Optional[str] = ""


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role_id: Optional[str] = None
    hourly_wage: Optional[float] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    category: str = "Geral"
    category_id: Optional[str] = None
    unit: str = "un"
    quantity: float = 0.0
    min_quantity: float = 0.0
    cost_price: float = 0.0
    sale_price: float = 0.0
    vat_rate: float = 23.0
    track_stock: bool = True
    modifier_group_ids: List[str] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    category_id: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    min_quantity: Optional[float] = None
    cost_price: Optional[float] = None
    sale_price: Optional[float] = None
    vat_rate: Optional[float] = None
    track_stock: Optional[bool] = None
    modifier_group_ids: Optional[List[str]] = None


class StockMovementInput(BaseModel):
    product_id: str
    type: str  # entrada | saida
    quantity: float
    note: Optional[str] = ""


class ClockInput(BaseModel):
    lat: float
    lng: float


class ScheduleInput(BaseModel):
    shifts: dict = Field(default_factory=dict)


class EntryUpdate(BaseModel):
    clock_in: Optional[str] = None
    clock_out: Optional[str] = None


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
    late_tolerance_min: int = 5
    no_signal_minutes: int = 5


# --- POS configuração ---
class ZoneInput(BaseModel):
    name: str
    order: int = 0


class TableInput(BaseModel):
    name: str
    zone_id: Optional[str] = None
    seats: int = 4
    order: int = 0


class CategoryInput(BaseModel):
    name: str
    color: str = "#111827"
    order: int = 0


class ModifierOption(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    price_delta: float = 0.0


class ModifierGroupInput(BaseModel):
    name: str
    min: int = 0
    max: int = 1
    required: bool = False
    options: List[ModifierOption] = Field(default_factory=list)


class ComboItem(BaseModel):
    product_id: str
    quantity: float = 1.0


class ComboInput(BaseModel):
    name: str
    price: float = 0.0
    vat_rate: float = 23.0
    category_id: Optional[str] = None
    items: List[ComboItem] = Field(default_factory=list)
    active: bool = True


class PaymentMethod(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True


class ReceiptConfig(BaseModel):
    name: str = ""
    nif: str = ""
    address: str = ""
    phone: str = ""
    footer: str = "Obrigado pela preferência!"


class POSConfigInput(BaseModel):
    currency_symbol: str = "€"
    decimals: int = 2
    rounding: str = "none"  # none | 0.05 | 0.10
    track_stock_default: bool = True
    service_charge_enabled: bool = False
    service_charge_percent: float = 0.0
    default_vat_rate: float = 23.0
    payment_methods: List[PaymentMethod] = Field(default_factory=list)
    receipt: ReceiptConfig = Field(default_factory=ReceiptConfig)
    invoice_provider: str = "none"  # none | invoicexpress | moloni | outro
    invoice_enabled: bool = False
    invoice_account: str = ""
    invoice_api_key: str = ""


DEFAULT_POS_CONFIG = {
    "id": "main",
    "currency_symbol": "€",
    "decimals": 2,
    "rounding": "none",
    "track_stock_default": True,
    "service_charge_enabled": False,
    "service_charge_percent": 0.0,
    "default_vat_rate": 23.0,
    "payment_methods": [
        {"id": str(uuid.uuid4()), "name": "Dinheiro", "enabled": True},
        {"id": str(uuid.uuid4()), "name": "Multibanco", "enabled": True},
        {"id": str(uuid.uuid4()), "name": "MB Way", "enabled": True},
    ],
    "receipt": {"name": "", "nif": "", "address": "", "phone": "", "footer": "Obrigado pela preferência!"},
    "invoice_provider": "none",
    "invoice_enabled": False,
    "invoice_account": "",
    "invoice_api_key": "",
}


# --- Encomendas / POS ---
class OrderCreate(BaseModel):
    table_id: Optional[str] = None
    table_name: Optional[str] = None


class SelectedModifier(BaseModel):
    group_id: Optional[str] = None
    option_id: str


class OrderItemInput(BaseModel):
    kind: str = "product"  # product | combo
    ref_id: str
    quantity: float = 1.0
    modifiers: List[SelectedModifier] = Field(default_factory=list)
    notes: Optional[str] = ""


class OrderPatch(BaseModel):
    discount_type: Optional[str] = None  # none | percent | fixed
    discount_value: Optional[float] = None
    service_charge_enabled: Optional[bool] = None


class PaymentEntry(BaseModel):
    method: str
    amount: float


class OrderClose(BaseModel):
    payments: List[PaymentEntry] = Field(default_factory=list)


class OrderCancel(BaseModel):
    reason: Optional[str] = ""


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api_router.post("/auth/login")
async def login(data: LoginInput, response: Response):
    email = data.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Conta desativada")
    token = create_access_token(user["id"])
    set_auth_cookie(response, token)
    u = clean(dict(user))
    u.pop("password_hash", None)
    await enrich_role(u)
    return {"user": u}


@api_router.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ---------------------------------------------------------------------------
# Staff routes
# ---------------------------------------------------------------------------
@api_router.get("/staff")
async def list_staff(user: dict = Depends(require_permission("staff"))):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    roles = await db.roles.find({}, {"_id": 0}).to_list(200)
    rmap = {r["id"]: r for r in roles}
    for u in users:
        r = rmap.get(u.get("role_id")) or next((x for x in roles if x["name"] == u.get("role")), None)
        if r:
            u["role"] = r["name"]
            u["role_id"] = r["id"]
            u["is_admin"] = bool(r.get("is_admin"))
            u["permissions"] = MODULES if r.get("is_admin") else list(r.get("modules") or [])
            u["rank"] = int(r.get("rank") or 0)
    return users


async def _resolve_role(role_id: str) -> dict:
    role = await db.roles.find_one({"id": role_id}, {"_id": 0})
    if not role:
        raise HTTPException(status_code=400, detail="Cargo inválido")
    return role


async def _role_rank(role_id: str) -> int:
    r = await db.roles.find_one({"id": role_id}, {"_id": 0})
    return int((r or {}).get("rank") or 0)


@api_router.post("/staff")
async def create_staff(data: StaffCreate, user: dict = Depends(require_admin)):
    email = data.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email já registado")
    role = await _resolve_role(data.role_id)
    if int(role.get("rank") or 0) > int(user.get("rank") or 0):
        raise HTTPException(status_code=403, detail="Não pode atribuir um cargo superior ao seu")
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "email": email,
        "password_hash": hash_password(data.password),
        "role_id": role["id"],
        "role": role["name"],
        "hourly_wage": data.hourly_wage,
        "phone": data.phone,
        "active": True,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    doc.pop("_id", None)
    return clean(dict(doc))


@api_router.put("/staff/{staff_id}")
async def update_staff(staff_id: str, data: StaffUpdate, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": staff_id})
    if not target:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    target_rank = await _role_rank(target.get("role_id"))
    if target_rank > int(user.get("rank") or 0):
        raise HTTPException(status_code=403, detail="Sem permissão para gerir contas deste cargo")
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    if "password" in upd:
        upd["password_hash"] = hash_password(upd.pop("password"))
    if "role_id" in upd:
        role = await _resolve_role(upd["role_id"])
        if int(role.get("rank") or 0) > int(user.get("rank") or 0):
            raise HTTPException(status_code=403, detail="Não pode atribuir um cargo superior ao seu")
        upd["role_id"] = role["id"]
        upd["role"] = role["name"]
        upd.pop("permissions", None)
    await db.users.update_one({"id": staff_id}, {"$set": upd})
    doc = await db.users.find_one({"id": staff_id}, {"_id": 0, "password_hash": 0})
    return doc


@api_router.delete("/staff/{staff_id}")
async def delete_staff(staff_id: str, user: dict = Depends(require_admin)):
    if staff_id == user["id"]:
        raise HTTPException(status_code=400, detail="Não pode eliminar a própria conta")
    target = await db.users.find_one({"id": staff_id})
    if not target:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    target_rank = await _role_rank(target.get("role_id"))
    if target_rank > int(user.get("rank") or 0):
        raise HTTPException(status_code=403, detail="Sem permissão para eliminar contas deste cargo")
    await db.users.delete_one({"id": staff_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Cargos (Roles) — RBAC dinâmico
# ---------------------------------------------------------------------------
@api_router.get("/roles")
async def list_roles(user: dict = Depends(get_current_user)):
    return await db.roles.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)


@api_router.post("/roles")
async def create_role(data: RoleInput, user: dict = Depends(require_admin)):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome obrigatório")
    if await db.roles.find_one({"name": name}):
        raise HTTPException(status_code=400, detail="Já existe um cargo com esse nome")
    mods = [m for m in data.modules if m in MODULES]
    doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "modules": mods,
        "is_admin": False,
        "is_supervisor": bool(data.is_supervisor),
        "is_system": False,
        "rank": 0,
        "created_at": now_iso(),
    }
    await db.roles.insert_one(doc)
    return clean(dict(doc))


@api_router.put("/roles/{role_id}")
async def update_role(role_id: str, data: RoleInput, user: dict = Depends(require_admin)):
    role = await db.roles.find_one({"id": role_id})
    if not role:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    if role.get("is_system"):
        raise HTTPException(status_code=403, detail="Este cargo de sistema não pode ser alterado")
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome obrigatório")
    if await db.roles.find_one({"name": name, "id": {"$ne": role_id}}):
        raise HTTPException(status_code=400, detail="Já existe um cargo com esse nome")
    mods = [m for m in data.modules if m in MODULES]
    await db.roles.update_one({"id": role_id}, {"$set": {"name": name, "modules": mods, "is_supervisor": bool(data.is_supervisor)}})
    # sincroniza o nome do cargo nos funcionários
    await db.users.update_many({"role_id": role_id}, {"$set": {"role": name}})
    return await db.roles.find_one({"id": role_id}, {"_id": 0})


@api_router.delete("/roles/{role_id}")
async def delete_role(role_id: str, user: dict = Depends(require_admin)):
    role = await db.roles.find_one({"id": role_id})
    if not role:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    if role.get("is_system"):
        raise HTTPException(status_code=403, detail="Este cargo de sistema não pode ser eliminado")
    in_use = await db.users.count_documents({"role_id": role_id})
    if in_use:
        raise HTTPException(status_code=400, detail=f"Cargo em uso por {in_use} funcionário(s). Reatribua-os primeiro.")
    await db.roles.delete_one({"id": role_id})
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
    if not s:
        return {}
    s.setdefault("late_tolerance_min", 5)
    s.setdefault("no_signal_minutes", 5)
    return s


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
            {"$set": {
                "clock_out": out, "clock_out_lat": data.lat, "clock_out_lng": data.lng,
                "duration_seconds": seconds, "auto_checkout": False, "checkout_reason": "manual",
            }},
        )
        return {"action": "saida", "distance_m": int(dist), "duration_seconds": seconds}
    now = now_iso()
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user["name"],
        "clock_in": now,
        "clock_in_lat": data.lat,
        "clock_in_lng": data.lng,
        "clock_out": None,
        "duration_seconds": 0,
        "last_seen": now,
        "last_lat": data.lat,
        "last_lng": data.lng,
        "auto_checkout": False,
        "checkout_reason": None,
    }
    await db.time_entries.insert_one(entry)
    await _check_late_on_entry(user, now)
    return {"action": "entrada", "distance_m": int(dist)}


@api_router.post("/timeclock/heartbeat")
async def timeclock_heartbeat(data: ClockInput, user: dict = Depends(require_permission("picagem"))):
    """Recebe a localização periódica enquanto em serviço. Fecha o ponto automaticamente se sair do raio."""
    open_entry = await db.time_entries.find_one({"user_id": user["id"], "clock_out": None})
    if not open_entry:
        return {"clocked_in": False}
    settings = await db.settings.find_one({"id": "main"})
    now = now_iso()
    dist = None
    if settings and settings.get("lat") is not None:
        dist = haversine(data.lat, data.lng, settings["lat"], settings["lng"])
        if dist > settings["radius_m"]:
            seconds = (datetime.fromisoformat(now) - datetime.fromisoformat(open_entry["clock_in"])).total_seconds()
            await db.time_entries.update_one(
                {"id": open_entry["id"]},
                {"$set": {
                    "clock_out": now, "clock_out_lat": data.lat, "clock_out_lng": data.lng,
                    "duration_seconds": max(0, seconds), "auto_checkout": True, "checkout_reason": "out_of_radius",
                }},
            )
            return {"clocked_in": False, "auto_checkout": True, "reason": "out_of_radius", "distance_m": int(dist)}
    await db.time_entries.update_one(
        {"id": open_entry["id"]},
        {"$set": {"last_seen": now, "last_lat": data.lat, "last_lng": data.lng}},
    )
    return {"clocked_in": True, "distance_m": int(dist) if dist is not None else None}


@api_router.get("/timeclock/status")
async def clock_status(user: dict = Depends(get_current_user)):
    open_entry = await db.time_entries.find_one({"user_id": user["id"], "clock_out": None}, {"_id": 0})
    return {"clocked_in": open_entry is not None, "entry": open_entry}


@api_router.get("/timeclock/entries")
async def clock_entries(user: dict = Depends(get_current_user)):
    if can_manage(user, "picagem"):
        entries = await db.time_entries.find({}, {"_id": 0}).sort("clock_in", -1).to_list(300)
    else:
        entries = await db.time_entries.find({"user_id": user["id"]}, {"_id": 0}).sort("clock_in", -1).to_list(100)
    return entries


def _hhmm_to_min(s: str) -> int:
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def _to_utc_iso(s: str) -> str:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LISBON)
    return dt.astimezone(timezone.utc).isoformat()


# --- Horário semanal + cumprimento ---
@api_router.get("/schedules")
async def list_schedules(user: dict = Depends(require_manage("picagem"))):
    users = await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(1000)
    scheds = await db.schedules.find({}, {"_id": 0}).to_list(1000)
    smap = {s["user_id"]: s.get("shifts", {}) for s in scheds}
    return [{"user_id": u["id"], "user_name": u["name"], "role": u.get("role"), "shifts": smap.get(u["id"], {})} for u in users]


@api_router.put("/schedules/{user_id}")
async def set_schedule(user_id: str, data: ScheduleInput, user: dict = Depends(require_manage("picagem"))):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    shifts = {k: v for k, v in (data.shifts or {}).items() if k in WEEKDAY_KEYS}
    await db.schedules.update_one({"user_id": user_id}, {"$set": {"user_id": user_id, "shifts": shifts}}, upsert=True)
    return {"user_id": user_id, "shifts": shifts}


@api_router.get("/schedules/compliance")
async def schedule_compliance(date: Optional[str] = None, user: dict = Depends(require_manage("picagem"))):
    target = datetime.now(LISBON).date() if not date else datetime.fromisoformat(date).date()
    wk = WEEKDAY_KEYS[target.weekday()]
    settings_doc = await db.settings.find_one({"id": "main"}) or {}
    tol = int(settings_doc.get("late_tolerance_min") or 5)
    scheds = await db.schedules.find({}, {"_id": 0}).to_list(1000)
    users = {u["id"]: u for u in await db.users.find({}, {"_id": 0}).to_list(1000)}
    start = (datetime.combine(target, datetime.min.time(), LISBON) - timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    end = (datetime.combine(target, datetime.max.time(), LISBON) + timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    entries = await db.time_entries.find({"clock_in": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(2000)
    first_in = {}
    for e in entries:
        try:
            cin = datetime.fromisoformat(e["clock_in"]).astimezone(LISBON)
        except Exception:
            continue
        if cin.date() != target:
            continue
        uid = e.get("user_id")
        if uid not in first_in or cin < first_in[uid]:
            first_in[uid] = cin
    items = []
    for s in scheds:
        shift = (s.get("shifts") or {}).get(wk) or {}
        if shift.get("off") or not shift.get("start"):
            continue
        uid = s["user_id"]
        u = users.get(uid)
        if not u:
            continue
        sched_min = _hhmm_to_min(shift["start"])
        actual = first_in.get(uid)
        if actual is None:
            items.append({"user_id": uid, "user_name": u["name"], "scheduled_start": shift.get("start"), "scheduled_end": shift.get("end"), "actual_in": None, "status": "falta", "late_minutes": None})
        else:
            late = (actual.hour * 60 + actual.minute) - sched_min
            items.append({"user_id": uid, "user_name": u["name"], "scheduled_start": shift.get("start"), "scheduled_end": shift.get("end"), "actual_in": actual.strftime("%H:%M"), "status": "atraso" if late > tol else "presente", "late_minutes": late})
    return {"date": target.isoformat(), "weekday": wk, "items": items}


# --- Correção de picagens (gestor) ---
@api_router.put("/timeclock/entries/{entry_id}")
async def correct_entry(entry_id: str, data: EntryUpdate, user: dict = Depends(require_manage("picagem"))):
    entry = await db.time_entries.find_one({"id": entry_id})
    if not entry:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    upd = {}
    ci_iso = _to_utc_iso(data.clock_in) if data.clock_in else entry["clock_in"]
    upd["clock_in"] = ci_iso
    ci_dt = datetime.fromisoformat(ci_iso)
    if data.clock_out:
        co_iso = _to_utc_iso(data.clock_out)
        co_dt = datetime.fromisoformat(co_iso)
        if co_dt < ci_dt:
            raise HTTPException(status_code=400, detail="A saída não pode ser anterior à entrada")
        upd["clock_out"] = co_iso
        upd["duration_seconds"] = max(0, (co_dt - ci_dt).total_seconds())
        if not entry.get("clock_out"):
            upd["auto_checkout"] = False
            upd["checkout_reason"] = "correction"
    elif entry.get("clock_out"):
        co_dt = datetime.fromisoformat(entry["clock_out"])
        if co_dt < ci_dt:
            raise HTTPException(status_code=400, detail="A saída não pode ser anterior à entrada")
        upd["duration_seconds"] = max(0, (co_dt - ci_dt).total_seconds())
    await db.time_entries.update_one({"id": entry_id}, {"$set": upd})
    return await db.time_entries.find_one({"id": entry_id}, {"_id": 0})


@api_router.delete("/timeclock/entries/{entry_id}")
async def delete_entry(entry_id: str, user: dict = Depends(require_manage("picagem"))):
    if not user.get("is_system"):
        raise HTTPException(status_code=403, detail="Apenas cargos de sistema (Administrador/Dono) podem eliminar picagens")
    await db.time_entries.delete_one({"id": entry_id})
    return {"ok": True}


# --- Avisos (atrasos e faltas) ---
async def _create_notification(ntype: str, uid: str, uname: str, message: str, date_str: str):
    exists = await db.notifications.find_one({"type": ntype, "user_id": uid, "date": date_str})
    if exists:
        return
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "type": ntype, "user_id": uid, "user_name": uname,
        "message": message, "date": date_str, "created_at": now_iso(), "read": False,
    })


async def _check_late_on_entry(user: dict, clock_in_iso: str):
    sched = await db.schedules.find_one({"user_id": user["id"]})
    if not sched:
        return
    cin = datetime.fromisoformat(clock_in_iso).astimezone(LISBON)
    wk = WEEKDAY_KEYS[cin.date().weekday()]
    shift = (sched.get("shifts") or {}).get(wk) or {}
    if shift.get("off") or not shift.get("start"):
        return
    settings_doc = await db.settings.find_one({"id": "main"}) or {}
    tol = int(settings_doc.get("late_tolerance_min") or 5)
    late = (cin.hour * 60 + cin.minute) - _hhmm_to_min(shift["start"])
    if late > tol:
        await _create_notification("atraso", user["id"], user["name"], f"Entrou às {cin.strftime('%H:%M')} (turno {shift['start']}, +{late} min de atraso)", cin.date().isoformat())


async def _detect_faltas(tol: int):
    nowL = datetime.now(LISBON)
    target = nowL.date()
    wk = WEEKDAY_KEYS[target.weekday()]
    scheds = await db.schedules.find({}, {"_id": 0}).to_list(1000)
    if not scheds:
        return
    users = {u["id"]: u for u in await db.users.find({}, {"_id": 0}).to_list(1000)}
    start = (datetime.combine(target, datetime.min.time(), LISBON) - timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    end = (datetime.combine(target, datetime.max.time(), LISBON) + timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    entries = await db.time_entries.find({"clock_in": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(2000)
    punched = set()
    for e in entries:
        try:
            cin = datetime.fromisoformat(e["clock_in"]).astimezone(LISBON)
        except Exception:
            continue
        if cin.date() == target:
            punched.add(e.get("user_id"))
    now_min = nowL.hour * 60 + nowL.minute
    for s in scheds:
        shift = (s.get("shifts") or {}).get(wk) or {}
        if shift.get("off") or not shift.get("start"):
            continue
        uid = s["user_id"]
        if uid in punched or now_min < _hhmm_to_min(shift["start"]) + tol:
            continue
        u = users.get(uid)
        if not u:
            continue
        await _create_notification("falta", uid, u["name"], f"Falta ao turno de {shift['start']} (sem picagem)", target.isoformat())


@api_router.get("/notifications")
async def list_notifications(user: dict = Depends(require_manage("picagem"))):
    items = await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({"read": False})
    return {"items": items, "unread": unread}


@api_router.post("/notifications/read")
async def mark_notifications_read(user: dict = Depends(require_manage("picagem"))):
    await db.notifications.update_many({"read": False}, {"$set": {"read": True}})
    return {"ok": True}


@api_router.get("/schedules/weekly-summary")
async def weekly_summary(week_start: Optional[str] = None, user: dict = Depends(require_manage("picagem"))):
    if week_start:
        d0 = datetime.fromisoformat(week_start).date()
    else:
        today = datetime.now(LISBON).date()
        d0 = today - timedelta(days=today.weekday())
    d6 = d0 + timedelta(days=6)
    scheds = {s["user_id"]: s for s in await db.schedules.find({}, {"_id": 0}).to_list(1000)}
    users = await db.users.find({}, {"_id": 0}).to_list(1000)
    start = (datetime.combine(d0, datetime.min.time(), LISBON) - timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    end = (datetime.combine(d6, datetime.max.time(), LISBON) + timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    entries = await db.time_entries.find({"clock_in": {"$gte": start, "$lte": end}, "clock_out": {"$ne": None}}, {"_id": 0}).to_list(5000)
    actual = {}
    for e in entries:
        try:
            cin = datetime.fromisoformat(e["clock_in"]).astimezone(LISBON).date()
        except Exception:
            continue
        if cin < d0 or cin > d6:
            continue
        actual[e["user_id"]] = actual.get(e["user_id"], 0.0) + float(e.get("duration_seconds") or 0)
    items = []
    for u in users:
        shifts = (scheds.get(u["id"], {}) or {}).get("shifts", {})
        planned = 0.0
        for k in WEEKDAY_KEYS:
            sh = shifts.get(k) or {}
            if sh.get("off") or not sh.get("start") or not sh.get("end"):
                continue
            mins = _hhmm_to_min(sh["end"]) - _hhmm_to_min(sh["start"])
            if mins > 0:
                planned += mins / 60
        items.append({"user_id": u["id"], "user_name": u["name"], "planned_hours": round(planned, 2), "actual_hours": round(actual.get(u["id"], 0.0) / 3600, 2)})
    items.sort(key=lambda x: x["user_name"])
    return {"week_start": d0.isoformat(), "week_end": d6.isoformat(), "items": items}


@api_router.get("/reports/hours")
async def reports_hours(from_: str = Query(..., alias="from"), to: str = Query(...), user: dict = Depends(require_permission("relatorios"))):
    d_from = datetime.fromisoformat(from_).date()
    d_to = datetime.fromisoformat(to).date()
    start = (datetime.combine(d_from, datetime.min.time(), LISBON) - timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    end = (datetime.combine(d_to, datetime.max.time(), LISBON) + timedelta(hours=3)).astimezone(timezone.utc).isoformat()
    entries = await db.time_entries.find({"clock_in": {"$gte": start, "$lte": end}, "clock_out": {"$ne": None}}, {"_id": 0}).to_list(5000)
    users = {u["id"]: u for u in await db.users.find({}, {"_id": 0}).to_list(1000)}
    agg = {}
    for e in entries:
        try:
            cin = datetime.fromisoformat(e["clock_in"]).astimezone(LISBON).date()
        except Exception:
            continue
        if cin < d_from or cin > d_to:
            continue
        if e.get("user_id") not in users:
            continue
        agg[e["user_id"]] = agg.get(e["user_id"], 0.0) + float(e.get("duration_seconds") or 0)
    items = []
    total_hours = 0.0
    total_cost = 0.0
    for uid, secs in agg.items():
        u = users.get(uid) or {}
        hours = round(secs / 3600, 2)
        wage = float(u.get("hourly_wage") or 0)
        cost = round(hours * wage, 2)
        total_hours += hours
        total_cost += cost
        items.append({"user_id": uid, "user_name": u.get("name", "?"), "hours": hours, "hourly_wage": wage, "cost": cost})
    items.sort(key=lambda x: x["user_name"])
    return {"from": d_from.isoformat(), "to": d_to.isoformat(), "items": items, "total_hours": round(total_hours, 2), "total_cost": round(total_cost, 2)}


# ---------------------------------------------------------------------------
# Consumo do Staff
# ---------------------------------------------------------------------------
@api_router.post("/consumption")
async def register_consumption(data: ConsumptionInput, user: dict = Depends(require_permission("consumo"))):
    product = await db.products.find_one({"id": data.product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    target_id = data.staff_id or user["id"]
    if target_id != user["id"] and not can_manage(user, "consumo"):
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
    if can_manage(user, "consumo"):
        items = await db.consumptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    else:
        items = await db.consumptions.find({"staff_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


# ---------------------------------------------------------------------------
# POS — Configuração (config, zonas, mesas, categorias, modificadores, combos)
# ---------------------------------------------------------------------------
async def get_pos_config() -> dict:
    cfg = await db.pos_config.find_one({"id": "main"}, {"_id": 0})
    if not cfg:
        await db.pos_config.insert_one(dict(DEFAULT_POS_CONFIG))
        cfg = await db.pos_config.find_one({"id": "main"}, {"_id": 0})
    for k, v in DEFAULT_POS_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


@api_router.get("/pos/config")
async def read_pos_config(user: dict = Depends(get_current_user)):
    cfg = await get_pos_config()
    key = cfg.pop("invoice_api_key", "")
    cfg["invoice_api_key_set"] = bool(key)
    return cfg


@api_router.put("/pos/config")
async def update_pos_config(data: POSConfigInput, user: dict = Depends(require_admin)):
    existing = await get_pos_config()
    payload = data.model_dump()
    if not payload.get("invoice_api_key"):
        payload["invoice_api_key"] = existing.get("invoice_api_key", "")
    doc = {"id": "main", **payload}
    await db.pos_config.update_one({"id": "main"}, {"$set": doc}, upsert=True)
    out = dict(doc)
    key = out.pop("invoice_api_key", "")
    out["invoice_api_key_set"] = bool(key)
    return out


@api_router.get("/pos/zones")
async def list_zones(user: dict = Depends(get_current_user)):
    return await db.pos_zones.find({}, {"_id": 0}).sort("order", 1).to_list(200)


@api_router.post("/pos/zones")
async def create_zone(data: ZoneInput, user: dict = Depends(require_admin)):
    doc = {"id": str(uuid.uuid4()), **data.model_dump()}
    await db.pos_zones.insert_one(doc)
    return clean(dict(doc))


@api_router.put("/pos/zones/{zone_id}")
async def update_zone(zone_id: str, data: ZoneInput, user: dict = Depends(require_admin)):
    await db.pos_zones.update_one({"id": zone_id}, {"$set": data.model_dump()})
    return await db.pos_zones.find_one({"id": zone_id}, {"_id": 0})


@api_router.delete("/pos/zones/{zone_id}")
async def delete_zone(zone_id: str, user: dict = Depends(require_admin)):
    await db.pos_zones.delete_one({"id": zone_id})
    await db.pos_tables.delete_many({"zone_id": zone_id})
    return {"ok": True}


@api_router.get("/pos/tables")
async def list_tables(user: dict = Depends(get_current_user)):
    return await db.pos_tables.find({}, {"_id": 0}).sort("order", 1).to_list(500)


@api_router.post("/pos/tables")
async def create_table(data: TableInput, user: dict = Depends(require_admin)):
    doc = {"id": str(uuid.uuid4()), **data.model_dump()}
    await db.pos_tables.insert_one(doc)
    return clean(dict(doc))


@api_router.post("/pos/tables/bulk")
async def create_tables_bulk(zone_id: str, count: int, prefix: str = "Mesa", user: dict = Depends(require_admin)):
    existing = await db.pos_tables.count_documents({"zone_id": zone_id})
    docs = [
        {"id": str(uuid.uuid4()), "name": f"{prefix} {existing + i + 1}", "zone_id": zone_id, "seats": 4, "order": existing + i}
        for i in range(count)
    ]
    if docs:
        await db.pos_tables.insert_many(docs)
    return {"created": len(docs)}


@api_router.put("/pos/tables/{table_id}")
async def update_table(table_id: str, data: TableInput, user: dict = Depends(require_admin)):
    await db.pos_tables.update_one({"id": table_id}, {"$set": data.model_dump()})
    return await db.pos_tables.find_one({"id": table_id}, {"_id": 0})


@api_router.delete("/pos/tables/{table_id}")
async def delete_table(table_id: str, user: dict = Depends(require_admin)):
    await db.pos_tables.delete_one({"id": table_id})
    return {"ok": True}


@api_router.get("/pos/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    return await db.pos_categories.find({}, {"_id": 0}).sort("order", 1).to_list(200)


@api_router.post("/pos/categories")
async def create_category(data: CategoryInput, user: dict = Depends(require_admin)):
    doc = {"id": str(uuid.uuid4()), **data.model_dump()}
    await db.pos_categories.insert_one(doc)
    return clean(dict(doc))


@api_router.put("/pos/categories/{cat_id}")
async def update_category(cat_id: str, data: CategoryInput, user: dict = Depends(require_admin)):
    await db.pos_categories.update_one({"id": cat_id}, {"$set": data.model_dump()})
    return await db.pos_categories.find_one({"id": cat_id}, {"_id": 0})


@api_router.delete("/pos/categories/{cat_id}")
async def delete_category(cat_id: str, user: dict = Depends(require_admin)):
    await db.pos_categories.delete_one({"id": cat_id})
    return {"ok": True}


@api_router.get("/pos/modifier-groups")
async def list_modifier_groups(user: dict = Depends(get_current_user)):
    return await db.pos_modifiers.find({}, {"_id": 0}).to_list(200)


@api_router.post("/pos/modifier-groups")
async def create_modifier_group(data: ModifierGroupInput, user: dict = Depends(require_admin)):
    doc = {"id": str(uuid.uuid4()), **data.model_dump()}
    await db.pos_modifiers.insert_one(doc)
    return clean(dict(doc))


@api_router.put("/pos/modifier-groups/{group_id}")
async def update_modifier_group(group_id: str, data: ModifierGroupInput, user: dict = Depends(require_admin)):
    await db.pos_modifiers.update_one({"id": group_id}, {"$set": data.model_dump()})
    return await db.pos_modifiers.find_one({"id": group_id}, {"_id": 0})


@api_router.delete("/pos/modifier-groups/{group_id}")
async def delete_modifier_group(group_id: str, user: dict = Depends(require_admin)):
    await db.pos_modifiers.delete_one({"id": group_id})
    return {"ok": True}


@api_router.get("/pos/combos")
async def list_combos(user: dict = Depends(get_current_user)):
    return await db.pos_combos.find({}, {"_id": 0}).to_list(200)


@api_router.post("/pos/combos")
async def create_combo(data: ComboInput, user: dict = Depends(require_permission("menus"))):
    doc = {"id": str(uuid.uuid4()), **data.model_dump()}
    await db.pos_combos.insert_one(doc)
    return clean(dict(doc))


@api_router.put("/pos/combos/{combo_id}")
async def update_combo(combo_id: str, data: ComboInput, user: dict = Depends(require_permission("menus"))):
    await db.pos_combos.update_one({"id": combo_id}, {"$set": data.model_dump()})
    return await db.pos_combos.find_one({"id": combo_id}, {"_id": 0})


@api_router.delete("/pos/combos/{combo_id}")
async def delete_combo(combo_id: str, user: dict = Depends(require_permission("menus"))):
    await db.pos_combos.delete_one({"id": combo_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Registadora / Mesas — encomendas com modificadores, IVA, desconto, pagamento
# ---------------------------------------------------------------------------
def round_money(v: float, rounding: str) -> float:
    if rounding == "0.05":
        return round(round(v / 0.05) * 0.05, 2)
    if rounding == "0.10":
        return round(round(v / 0.10) * 0.10, 2)
    return round(v, 2)


def compute_order(order: dict, config: dict) -> dict:
    items = order.get("items", [])
    subtotal = round(sum(i["line_total"] for i in items), 2)
    dtype = order.get("discount_type", "none")
    dval = order.get("discount_value", 0.0) or 0.0
    if dtype == "percent":
        discount_amount = round(subtotal * dval / 100, 2)
    elif dtype == "fixed":
        discount_amount = round(min(dval, subtotal), 2)
    else:
        discount_amount = 0.0
    after = round(subtotal - discount_amount, 2)
    ratio = (after / subtotal) if subtotal > 0 else 0.0
    svc_enabled = order.get("service_charge_enabled", False)
    svc_pct = config.get("service_charge_percent", 0.0) or 0.0
    service_charge_amount = round(after * svc_pct / 100, 2) if svc_enabled else 0.0
    total_raw = after + service_charge_amount
    total = round_money(total_raw, config.get("rounding", "none"))
    default_vat = config.get("default_vat_rate", 23.0)
    rates: dict = {}
    for i in items:
        r = i.get("vat_rate", default_vat)
        rates[r] = rates.get(r, 0.0) + i["line_total"] * ratio
    if service_charge_amount:
        rates[default_vat] = rates.get(default_vat, 0.0) + service_charge_amount
    vat_breakdown = []
    for r, gross in sorted(rates.items()):
        net = gross / (1 + r / 100) if r else gross
        vat_breakdown.append({"rate": r, "base": round(net, 2), "vat": round(gross - net, 2)})
    order["subtotal"] = subtotal
    order["discount_amount"] = discount_amount
    order["service_charge_amount"] = service_charge_amount
    order["total"] = total
    order["vat_breakdown"] = vat_breakdown
    return order


async def _apply_stock(deductions: list, sign: int):
    for d in deductions:
        prod = await db.products.find_one({"id": d["product_id"]})
        if prod:
            await db.products.update_one(
                {"id": d["product_id"]},
                {"$set": {"quantity": round(prod["quantity"] + sign * d["quantity"], 3)}},
            )


@api_router.get("/orders")
async def list_orders(status: Optional[str] = None, user: dict = Depends(require_permission("faturacao"))):
    q = {}
    if status:
        q["status"] = status
    return await db.orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)


@api_router.post("/orders")
async def open_order(data: OrderCreate, user: dict = Depends(require_permission("faturacao"))):
    table_name = data.table_name
    zone_id = None
    zone_name = None
    if data.table_id:
        table = await db.pos_tables.find_one({"id": data.table_id}, {"_id": 0})
        if not table:
            raise HTTPException(status_code=404, detail="Mesa não encontrada")
        existing = await db.orders.find_one({"table_id": data.table_id, "status": "aberta"}, {"_id": 0})
        if existing:
            return existing
        table_name = table["name"]
        zone_id = table.get("zone_id")
        if zone_id:
            z = await db.pos_zones.find_one({"id": zone_id}, {"_id": 0})
            zone_name = z["name"] if z else None
    if not table_name:
        raise HTTPException(status_code=400, detail="Indique a mesa")
    doc = {
        "id": str(uuid.uuid4()),
        "table_id": data.table_id,
        "table_name": table_name,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "status": "aberta",
        "items": [],
        "discount_type": "none",
        "discount_value": 0.0,
        "discount_amount": 0.0,
        "service_charge_enabled": False,
        "service_charge_amount": 0.0,
        "subtotal": 0.0,
        "total": 0.0,
        "vat_breakdown": [],
        "payments": [],
        "amount_paid": 0.0,
        "change": 0.0,
        "opened_by": user["name"],
        "created_at": now_iso(),
        "closed_at": None,
    }
    await db.orders.insert_one(doc)
    return clean(dict(doc))


@api_router.post("/orders/{order_id}/items")
async def add_order_item(order_id: str, data: OrderItemInput, user: dict = Depends(require_permission("faturacao"))):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Mesa não encontrada")
    if order["status"] != "aberta":
        raise HTTPException(status_code=400, detail="Mesa já fechada")
    config = await get_pos_config()
    deductions = []
    mods_out = []
    if data.kind == "combo":
        combo = await db.pos_combos.find_one({"id": data.ref_id})
        if not combo:
            raise HTTPException(status_code=404, detail="Menu/combo não encontrado")
        name = combo["name"]
        unit_price = combo.get("price", 0.0)
        vat_rate = combo.get("vat_rate", config.get("default_vat_rate", 23.0))
        for ci in combo.get("items", []):
            prod = await db.products.find_one({"id": ci["product_id"]})
            if prod and prod.get("track_stock", True):
                need = ci["quantity"] * data.quantity
                if round(prod["quantity"] - need, 3) < 0:
                    raise HTTPException(status_code=400, detail=f"Stock insuficiente: {prod['name']}")
                deductions.append({"product_id": ci["product_id"], "quantity": need})
    else:
        product = await db.products.find_one({"id": data.ref_id})
        if not product:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        name = product["name"]
        unit_price = product.get("sale_price", 0.0)
        vat_rate = product.get("vat_rate", config.get("default_vat_rate", 23.0))
        # modificadores
        if data.modifiers:
            groups = await db.pos_modifiers.find({}, {"_id": 0}).to_list(500)
            opt_map = {}
            for g in groups:
                for o in g.get("options", []):
                    opt_map[o["id"]] = o
            for sm in data.modifiers:
                o = opt_map.get(sm.option_id)
                if o:
                    unit_price += o.get("price_delta", 0.0)
                    mods_out.append({"name": o["name"], "price_delta": o.get("price_delta", 0.0)})
        if product.get("track_stock", True):
            if round(product["quantity"] - data.quantity, 3) < 0:
                raise HTTPException(status_code=400, detail="Stock insuficiente")
            deductions.append({"product_id": data.ref_id, "quantity": data.quantity})
    await _apply_stock(deductions, -1)
    item = {
        "id": str(uuid.uuid4()),
        "kind": data.kind,
        "ref_id": data.ref_id,
        "product_name": name,
        "quantity": data.quantity,
        "unit_price": round(unit_price, 2),
        "vat_rate": vat_rate,
        "modifiers": mods_out,
        "notes": data.notes or "",
        "line_total": round(unit_price * data.quantity, 2),
        "stock_deductions": deductions,
    }
    order["items"] = order["items"] + [item]
    compute_order(order, config)
    await db.orders.update_one({"id": order_id}, {"$set": {
        "items": order["items"], "subtotal": order["subtotal"], "total": order["total"],
        "discount_amount": order["discount_amount"], "service_charge_amount": order["service_charge_amount"],
        "vat_breakdown": order["vat_breakdown"],
    }})
    return clean(order)


@api_router.delete("/orders/{order_id}/items/{item_id}")
async def remove_order_item(order_id: str, item_id: str, user: dict = Depends(require_permission("faturacao"))):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Mesa não encontrada")
    if order["status"] != "aberta":
        raise HTTPException(status_code=400, detail="Mesa já fechada")
    item = next((i for i in order["items"] if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    await _apply_stock(item.get("stock_deductions", []), 1)
    order["items"] = [i for i in order["items"] if i["id"] != item_id]
    config = await get_pos_config()
    compute_order(order, config)
    await db.orders.update_one({"id": order_id}, {"$set": {
        "items": order["items"], "subtotal": order["subtotal"], "total": order["total"],
        "discount_amount": order["discount_amount"], "service_charge_amount": order["service_charge_amount"],
        "vat_breakdown": order["vat_breakdown"],
    }})
    return clean(order)


@api_router.patch("/orders/{order_id}")
async def patch_order(order_id: str, data: OrderPatch, user: dict = Depends(require_permission("faturacao"))):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Mesa não encontrada")
    if order["status"] != "aberta":
        raise HTTPException(status_code=400, detail="Mesa já fechada")
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    order.update(upd)
    config = await get_pos_config()
    compute_order(order, config)
    await db.orders.update_one({"id": order_id}, {"$set": {
        "discount_type": order.get("discount_type", "none"),
        "discount_value": order.get("discount_value", 0.0),
        "service_charge_enabled": order.get("service_charge_enabled", False),
        "subtotal": order["subtotal"], "total": order["total"],
        "discount_amount": order["discount_amount"], "service_charge_amount": order["service_charge_amount"],
        "vat_breakdown": order["vat_breakdown"],
    }})
    return clean(order)


@api_router.post("/orders/{order_id}/close")
async def close_order(order_id: str, data: OrderClose, user: dict = Depends(require_permission("faturacao"))):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Mesa não encontrada")
    if not order["items"]:
        raise HTTPException(status_code=400, detail="Mesa vazia — adicione itens antes de fechar")
    config = await get_pos_config()
    compute_order(order, config)
    payments = [p.model_dump() for p in data.payments]
    amount_paid = round(sum(p["amount"] for p in payments), 2)
    if payments and amount_paid + 0.01 < order["total"]:
        raise HTTPException(status_code=400, detail=f"Pagamento insuficiente. Falta {round(order['total'] - amount_paid, 2)}€")
    change = round(max(amount_paid - order["total"], 0.0), 2) if payments else 0.0
    await db.orders.update_one({"id": order_id}, {"$set": {
        "status": "paga", "closed_at": now_iso(),
        "payments": payments, "amount_paid": amount_paid, "change": change,
        "subtotal": order["subtotal"], "total": order["total"],
        "discount_amount": order["discount_amount"], "service_charge_amount": order["service_charge_amount"],
        "vat_breakdown": order["vat_breakdown"],
    }})
    saved = await db.orders.find_one({"id": order_id}, {"_id": 0})
    return saved


@api_router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, data: OrderCancel, user: dict = Depends(require_permission("faturacao"))):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Mesa não encontrada")
    if order["status"] == "aberta":
        for it in order["items"]:
            await _apply_stock(it.get("stock_deductions", []), 1)
    await db.orders.update_one({"id": order_id}, {"$set": {
        "status": "cancelada", "cancel_reason": data.reason or "",
        "cancelled_by": user["name"], "closed_at": now_iso(),
    }})
    return {"ok": True}


@api_router.delete("/orders/{order_id}")
async def delete_order(order_id: str, user: dict = Depends(require_admin)):
    order = await db.orders.find_one({"id": order_id})
    if order and order["status"] == "aberta":
        for it in order["items"]:
            await _apply_stock(it.get("stock_deductions", []), 1)
    await db.orders.delete_one({"id": order_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Faturação (configurável) + Talão PDF + Relatórios
# ---------------------------------------------------------------------------
@api_router.post("/orders/{order_id}/invoice")
async def emit_invoice(order_id: str, user: dict = Depends(require_permission("faturacao"))):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Encomenda não encontrada")
    if order.get("status") != "paga":
        raise HTTPException(status_code=400, detail="Só é possível faturar contas pagas")
    if order.get("invoice"):
        return order["invoice"]
    config = await get_pos_config()
    if not config.get("invoice_enabled"):
        raise HTTPException(status_code=400, detail="Faturação não configurada. Ative em Config POS → Faturação.")
    provider = config.get("invoice_provider", "none")
    # NOTA: emissão REAL do fornecedor (InvoiceXpress/Moloni) fica centralizada aqui.
    # Enquanto não houver credenciais reais ligadas, gera número sequencial SIMULADO.
    year = datetime.now(timezone.utc).year
    count = await db.orders.count_documents({"invoice": {"$ne": None}}) + 1
    invoice = {
        "number": f"FT {year}/{count}",
        "provider": provider,
        "issued_at": now_iso(),
        "issued_by": user["name"],
        "simulated": True,
    }
    await db.orders.update_one({"id": order_id}, {"$set": {"invoice": invoice}})
    return invoice


def _fmt_money(v: float, config: dict) -> str:
    d = int(config.get("decimals", 2))
    sym = config.get("currency_symbol", "€")
    s = f"{(v or 0):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} {sym}"


def build_receipt_pdf(order: dict, config: dict) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    r = config.get("receipt", {}) or {}
    items = order.get("items", [])
    vat = order.get("vat_breakdown", [])
    payments = order.get("payments", [])
    rows = 8
    if r.get("address"): rows += 1
    if r.get("nif"): rows += 1
    if r.get("phone"): rows += 1
    rows += len(items) + sum(1 for it in items if it.get("modifiers"))
    rows += 4
    if order.get("discount_amount"): rows += 1
    if order.get("service_charge_amount"): rows += 1
    rows += len(vat) + len(payments)
    if order.get("change"): rows += 1
    if order.get("invoice"): rows += 1
    rows += 3

    W = 80 * mm
    H = (rows * 5 + 18) * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    y = [H - 8 * mm]

    def line(left, right="", size=8, bold=False, center=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if center:
            c.drawCentredString(W / 2, y[0], left)
        else:
            c.drawString(5 * mm, y[0], left[:34])
            if right:
                c.drawRightString(W - 5 * mm, y[0], right)
        y[0] -= 5 * mm

    def sep():
        c.setDash(1, 2)
        c.line(5 * mm, y[0] + 1.5 * mm, W - 5 * mm, y[0] + 1.5 * mm)
        c.setDash()
        y[0] -= 3 * mm

    line(r.get("name") or "Restaurante", size=11, bold=True, center=True)
    if r.get("address"): line(r["address"], size=7, center=True)
    if r.get("nif"): line(f"NIF: {r['nif']}", size=7, center=True)
    if r.get("phone"): line(r["phone"], size=7, center=True)
    if order.get("invoice"): line(f"Fatura {order['invoice']['number']}", size=8, bold=True, center=True)
    sep()
    line(f"Mesa: {order.get('table_name', '-')}" + (f" · {order['zone_name']}" if order.get("zone_name") else ""), size=7)
    dt = order.get("closed_at") or now_iso()
    line(dt[:19].replace("T", " "), size=7)
    sep()
    for it in items:
        line(f"{it['quantity']:g}x {it['product_name']}", _fmt_money(it["line_total"], config))
        for md in it.get("modifiers", []):
            line(f"  + {md['name']}", size=7)
    sep()
    line("Subtotal", _fmt_money(order.get("subtotal", 0), config))
    if order.get("discount_amount"):
        line("Desconto", "-" + _fmt_money(order["discount_amount"], config))
    if order.get("service_charge_amount"):
        line("Serviço", _fmt_money(order["service_charge_amount"], config))
    line("TOTAL", _fmt_money(order.get("total", 0), config), size=11, bold=True)
    sep()
    for v in vat:
        line(f"IVA {v['rate']:g}% (base {_fmt_money(v['base'], config)})", _fmt_money(v["vat"], config), size=7)
    if payments:
        sep()
        for p in payments:
            line(p["method"], _fmt_money(p["amount"], config), size=7)
        if order.get("change"):
            line("Troco", _fmt_money(order["change"], config), size=7)
    y[0] -= 2 * mm
    line(r.get("footer") or "", size=8, center=True)
    c.showPage()
    c.save()
    return buf.getvalue()


@api_router.get("/orders/{order_id}/receipt.pdf")
async def receipt_pdf(order_id: str, user: dict = Depends(require_permission("faturacao"))):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Encomenda não encontrada")
    config = await get_pos_config()
    pdf = build_receipt_pdf(order, config)
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=talao-{order_id[:8]}.pdf"},
    )


@api_router.get("/reports/pos")
async def reports_pos(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    user: dict = Depends(require_permission("relatorios")),
):
    today = datetime.now(timezone.utc).date()
    d_from = from_ or (today - timedelta(days=29)).isoformat()
    d_to = to or today.isoformat()
    orders = await db.orders.find({"status": "paga"}, {"_id": 0}).to_list(5000)
    sel = [o for o in orders if d_from <= (o.get("closed_at") or "")[:10] <= d_to]
    total = round(sum(o["total"] for o in sel), 2)
    count = len(sel)
    avg = round(total / count, 2) if count else 0.0
    by_zone, by_method, by_day, by_vat = {}, {}, {}, {}
    for o in sel:
        z = o.get("zone_name") or "Sem zona"
        by_zone[z] = round(by_zone.get(z, 0) + o["total"], 2)
        d = o["closed_at"][:10]
        by_day[d] = round(by_day.get(d, 0) + o["total"], 2)
        for p in o.get("payments", []):
            by_method[p["method"]] = round(by_method.get(p["method"], 0) + p["amount"], 2)
        for v in o.get("vat_breakdown", []):
            by_vat[v["rate"]] = round(by_vat.get(v["rate"], 0) + v["vat"], 2)
    cancelled = await db.orders.count_documents({"status": "cancelada", "closed_at": {"$gte": d_from, "$lte": d_to + "T99"}})
    return {
        "from": d_from, "to": d_to,
        "total_sales": total, "order_count": count, "avg_ticket": avg, "cancelled_count": cancelled,
        "by_zone": [{"zone": k, "total": v} for k, v in sorted(by_zone.items(), key=lambda x: -x[1])],
        "by_method": [{"method": k, "total": v} for k, v in sorted(by_method.items(), key=lambda x: -x[1])],
        "by_day": [{"day": k, "total": v} for k, v in sorted(by_day.items())],
        "by_vat": [{"rate": k, "vat": v} for k, v in sorted(by_vat.items())],
    }


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
    orders_all = await db.orders.find({}, {"_id": 0}).to_list(2000)
    today_sales = round(
        sum(o["total"] for o in orders_all if o["status"] == "paga" and (o.get("closed_at") or "")[:10] == today), 2
    )
    open_tables = len([o for o in orders_all if o["status"] == "aberta"])
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
        "today_sales": today_sales,
        "open_tables": open_tables,
        "trend": trend,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    app.state.checkout_task = asyncio.create_task(auto_checkout_worker())
    # 1. Cargos de sistema (protegidos, controlo total). Administrador (topo) > Dono/a.
    async def ensure_system_role(name: str, rank: int) -> dict:
        role = await db.roles.find_one({"name": name})
        if role is None:
            role = {
                "id": str(uuid.uuid4()),
                "name": name,
                "modules": MODULES,
                "is_admin": True,
                "is_supervisor": True,
                "is_system": True,
                "rank": rank,
                "created_at": now_iso(),
            }
            await db.roles.insert_one(role)
        else:
            patch = {}
            if role.get("rank") != rank:
                patch["rank"] = rank
            if not role.get("is_admin"):
                patch["is_admin"] = True
            if not role.get("is_supervisor"):
                patch["is_supervisor"] = True
            if not role.get("is_system"):
                patch["is_system"] = True
            if role.get("modules") != MODULES:
                patch["modules"] = MODULES
            if patch:
                await db.roles.update_one({"id": role["id"]}, {"$set": patch})
                role.update(patch)
        return role

    admin_role = await ensure_system_role("Administrador", 100)
    await ensure_system_role("Dono/a", 90)
    # limpa qualquer flag de sistema herdada por cargos que não sejam os dois de topo
    await db.roles.update_many(
        {"is_system": True, "name": {"$nin": ["Administrador", "Dono/a"]}},
        {"$set": {"is_system": False}},
    )
    await db.roles.update_many({"rank": {"$exists": False}}, {"$set": {"rank": 0}})

    # 2. Utilizador admin (via .env)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@restaurante.pt").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "name": "Administrador",
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "role_id": admin_role["id"],
            "role": "Administrador",
            "hourly_wage": 0.0,
            "phone": "",
            "active": True,
            "created_at": now_iso(),
        })
        logger.info("Admin criado: %s", admin_email)
    else:
        patch = {}
        if not verify_password(admin_password, existing["password_hash"]):
            patch["password_hash"] = hash_password(admin_password)
        if not existing.get("role_id") or existing.get("role") in ("admin", None):
            patch["role_id"] = admin_role["id"]
            patch["role"] = "Administrador"
        if patch:
            await db.users.update_one({"email": admin_email}, {"$set": patch})

    # 3. Migração única de utilizadores legados (role string -> cargo dinâmico)
    legacy = await db.users.find({"role_id": {"$exists": False}}).to_list(1000)
    if legacy:
        gestor_perms, func_perms = set(), set()
        for u in legacy:
            if u.get("role") == "gestor":
                gestor_perms |= set(u.get("permissions") or [])
            elif u.get("role") == "funcionario":
                func_perms |= set(u.get("permissions") or [])
        if not func_perms:
            func_perms = {"picagem"}
        gestor_role = await db.roles.find_one({"name": "Gestor"})
        if gestor_role is None:
            gestor_role = {
                "id": str(uuid.uuid4()), "name": "Gestor",
                "modules": sorted(gestor_perms & set(MODULES)) or ["stock", "picagem", "consumo", "faturacao", "relatorios"],
                "is_admin": False, "is_supervisor": True, "is_system": False, "rank": 0, "created_at": now_iso(),
            }
            await db.roles.insert_one(gestor_role)
        func_role = await db.roles.find_one({"name": "Funcionário"})
        if func_role is None:
            func_role = {
                "id": str(uuid.uuid4()), "name": "Funcionário",
                "modules": sorted(func_perms & set(MODULES)),
                "is_admin": False, "is_supervisor": False, "is_system": False, "rank": 0, "created_at": now_iso(),
            }
            await db.roles.insert_one(func_role)
        for u in legacy:
            if u.get("role") == "admin":
                rid, rname = admin_role["id"], "Administrador"
            elif u.get("role") == "gestor":
                rid, rname = gestor_role["id"], "Gestor"
            else:
                rid, rname = func_role["id"], "Funcionário"
            await db.users.update_one({"id": u["id"]}, {"$set": {"role_id": rid, "role": rname}, "$unset": {"permissions": ""}})


@api_router.get("/")
async def root():
    return {"message": "Gestão Restaurante API"}


app.include_router(api_router)

_cors_regex = os.environ.get("CORS_ORIGIN_REGEX")
_cors_kwargs = {"allow_credentials": True, "allow_methods": ["*"], "allow_headers": ["*"]}
if _cors_regex:
    _cors_kwargs["allow_origin_regex"] = _cors_regex
else:
    _cors_kwargs["allow_origins"] = [
        o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()
    ]
logger.info("CORS config -> origins=%s regex=%s", _cors_kwargs.get("allow_origins"), _cors_regex)

app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.on_event("shutdown")
async def shutdown_db_client():
    task = getattr(app.state, "checkout_task", None)
    if task:
        task.cancel()
    client.close()


async def auto_checkout_worker():
    """Fecha pontos sem heartbeat (no_signal) e deteta faltas ao turno."""
    while True:
        try:
            await asyncio.sleep(60)
            settings_doc = await db.settings.find_one({"id": "main"}) or {}
            grace = int(settings_doc.get("no_signal_minutes") or 5) * 60
            tol = int(settings_doc.get("late_tolerance_min") or 5)
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=grace)
            open_entries = await db.time_entries.find({"clock_out": None}).to_list(1000)
            for e in open_entries:
                last = e.get("last_seen") or e.get("clock_in")
                try:
                    last_dt = datetime.fromisoformat(last)
                except Exception:
                    continue
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if last_dt < cutoff:
                    out = last
                    try:
                        seconds = (datetime.fromisoformat(out) - datetime.fromisoformat(e["clock_in"])).total_seconds()
                    except Exception:
                        seconds = 0
                    await db.time_entries.update_one(
                        {"id": e["id"]},
                        {"$set": {
                            "clock_out": out,
                            "clock_out_lat": e.get("last_lat"),
                            "clock_out_lng": e.get("last_lng"),
                            "duration_seconds": max(0, seconds),
                            "auto_checkout": True,
                            "checkout_reason": "no_signal",
                        }},
                    )
            await _detect_faltas(tol)
        except asyncio.CancelledError:
            break
        except Exception as ex:
            logger.exception("auto_checkout_worker: %s", ex)
