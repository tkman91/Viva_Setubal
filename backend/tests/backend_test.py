"""Backend API regression tests for Gestão Restaurante."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@restaurante.pt"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    assert data["user"]["email"] == ADMIN_EMAIL
    return data["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class TestAuth:
    def test_login_success(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 10

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_me(self, admin_headers):
        r = requests.get(f"{API}/auth/me", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_no_token_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class TestDashboard:
    def test_dashboard_kpis(self, admin_headers):
        r = requests.get(f"{API}/dashboard", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        for k in ["stock_value", "products_count", "staff_count", "active_now",
                  "today_consumption", "trend", "low_stock", "low_stock_count"]:
            assert k in d, f"missing key {k}"
        assert isinstance(d["trend"], list) and len(d["trend"]) == 7


# ---------------------------------------------------------------------------
# Stock / Products
# ---------------------------------------------------------------------------
class TestStock:
    _product_id = None

    def test_create_product(self, admin_headers):
        payload = {
            "name": f"TEST_Produto_{uuid.uuid4().hex[:6]}",
            "category": "Bebidas",
            "unit": "un",
            "quantity": 10,
            "min_quantity": 5,
            "cost_price": 1.0,
            "sale_price": 2.5,
        }
        r = requests.post(f"{API}/products", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["name"] == payload["name"]
        assert doc["quantity"] == 10
        TestStock._product_id = doc["id"]

    def test_list_products_contains(self, admin_headers):
        r = requests.get(f"{API}/products", headers=admin_headers)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert TestStock._product_id in ids

    def test_update_product(self, admin_headers):
        r = requests.put(
            f"{API}/products/{TestStock._product_id}",
            json={"min_quantity": 20},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["min_quantity"] == 20

    def test_movement_entrada(self, admin_headers):
        r = requests.post(
            f"{API}/stock/movement",
            json={"product_id": TestStock._product_id, "type": "entrada", "quantity": 5},
            headers=admin_headers,
        )
        assert r.status_code == 200
        # verify quantity is now 15
        g = requests.get(f"{API}/products", headers=admin_headers).json()
        p = next(x for x in g if x["id"] == TestStock._product_id)
        assert p["quantity"] == 15

    def test_movement_saida(self, admin_headers):
        r = requests.post(
            f"{API}/stock/movement",
            json={"product_id": TestStock._product_id, "type": "saida", "quantity": 3},
            headers=admin_headers,
        )
        assert r.status_code == 200
        g = requests.get(f"{API}/products", headers=admin_headers).json()
        p = next(x for x in g if x["id"] == TestStock._product_id)
        assert p["quantity"] == 12

    def test_movement_insufficient(self, admin_headers):
        r = requests.post(
            f"{API}/stock/movement",
            json={"product_id": TestStock._product_id, "type": "saida", "quantity": 999999},
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_low_stock_reflected(self, admin_headers):
        # min_quantity=20, quantity=12 -> low stock
        d = requests.get(f"{API}/dashboard", headers=admin_headers).json()
        low_ids = [p["id"] for p in d["low_stock"]]
        assert TestStock._product_id in low_ids


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
RESTAURANT_LAT = 38.7223
RESTAURANT_LNG = -9.1393
RADIUS_M = 150


class TestSettings:
    def test_update_settings_admin(self, admin_headers):
        r = requests.put(
            f"{API}/settings",
            json={
                "restaurant_name": "TEST Restaurante",
                "lat": RESTAURANT_LAT,
                "lng": RESTAURANT_LNG,
                "radius_m": RADIUS_M,
            },
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["radius_m"] == RADIUS_M

    def test_get_settings(self, admin_headers):
        r = requests.get(f"{API}/settings", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["restaurant_name"] == "TEST Restaurante"


# ---------------------------------------------------------------------------
# Staff mgmt + permissions
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _ensure_settings(admin_headers):
    """Ensure restaurant settings are configured before punch tests run (xdist safe)."""
    requests.put(
        f"{API}/settings",
        json={
            "restaurant_name": "TEST Restaurante",
            "lat": RESTAURANT_LAT,
            "lng": RESTAURANT_LNG,
            "radius_m": RADIUS_M,
        },
        headers=admin_headers,
    )


class TestStaffAndPermissions:
    _staff_id = None
    _staff_token = None
    _staff_email = f"test_func_{uuid.uuid4().hex[:6]}@rest.pt"
    _staff_pwd = "func123"

    def test_admin_create_funcionario(self, admin_headers):
        r = requests.post(
            f"{API}/staff",
            json={
                "name": "TEST Funcionario",
                "email": TestStaffAndPermissions._staff_email,
                "password": TestStaffAndPermissions._staff_pwd,
                "role": "funcionario",
                "permissions": ["picagem"],
            },
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "funcionario"
        assert d["permissions"] == ["picagem"]
        TestStaffAndPermissions._staff_id = d["id"]

    def test_list_staff_admin(self, admin_headers):
        r = requests.get(f"{API}/staff", headers=admin_headers)
        assert r.status_code == 200
        ids = [u["id"] for u in r.json()]
        assert TestStaffAndPermissions._staff_id in ids

    def test_funcionario_login(self):
        r = requests.post(
            f"{API}/auth/login",
            json={"email": TestStaffAndPermissions._staff_email,
                  "password": TestStaffAndPermissions._staff_pwd},
        )
        assert r.status_code == 200
        TestStaffAndPermissions._staff_token = r.json()["token"]

    def _fhdr(self):
        return {"Authorization": f"Bearer {TestStaffAndPermissions._staff_token}"}

    def test_funcionario_forbidden_products_post(self):
        r = requests.post(f"{API}/products", json={"name": "X"}, headers=self._fhdr())
        assert r.status_code == 403

    def test_funcionario_forbidden_staff_list(self):
        r = requests.get(f"{API}/staff", headers=self._fhdr())
        assert r.status_code == 403

    def test_funcionario_forbidden_invoices(self):
        r = requests.get(f"{API}/invoices", headers=self._fhdr())
        assert r.status_code == 403

    def test_funcionario_can_get_products(self):
        r = requests.get(f"{API}/products", headers=self._fhdr())
        assert r.status_code == 200

    def test_funcionario_forbidden_settings_put(self):
        r = requests.put(
            f"{API}/settings",
            json={"restaurant_name": "x", "lat": 0, "lng": 0, "radius_m": 10},
            headers=self._fhdr(),
        )
        assert r.status_code == 403

    def test_funcionario_can_timeclock_status(self):
        r = requests.get(f"{API}/timeclock/status", headers=self._fhdr())
        assert r.status_code == 200

    def test_punch_far_rejected(self):
        # ~5000km away
        r = requests.post(
            f"{API}/timeclock/punch",
            json={"lat": 0.0, "lng": 0.0},
            headers=self._fhdr(),
        )
        assert r.status_code == 403
        assert "m" in r.json()["detail"].lower() or "restaurante" in r.json()["detail"].lower()

    def test_punch_near_entrada_then_saida(self):
        # near settings coords
        r = requests.post(
            f"{API}/timeclock/punch",
            json={"lat": RESTAURANT_LAT + 0.0001, "lng": RESTAURANT_LNG},
            headers=self._fhdr(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["action"] == "entrada"
        # status shows clocked in
        s = requests.get(f"{API}/timeclock/status", headers=self._fhdr()).json()
        assert s["clocked_in"] is True
        # saida
        r2 = requests.post(
            f"{API}/timeclock/punch",
            json={"lat": RESTAURANT_LAT, "lng": RESTAURANT_LNG},
            headers=self._fhdr(),
        )
        assert r2.status_code == 200
        assert r2.json()["action"] == "saida"
        s2 = requests.get(f"{API}/timeclock/status", headers=self._fhdr()).json()
        assert s2["clocked_in"] is False

    def test_timeclock_entries(self):
        r = requests.get(f"{API}/timeclock/entries", headers=self._fhdr())
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        # funcionario sees only own
        for e in r.json():
            assert e["user_id"] == TestStaffAndPermissions._staff_id

    def test_update_staff_permissions(self, admin_headers):
        r = requests.put(
            f"{API}/staff/{TestStaffAndPermissions._staff_id}",
            json={"permissions": ["picagem", "consumo"]},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert set(r.json()["permissions"]) == {"picagem", "consumo"}

    def test_cannot_delete_self(self, admin_headers, admin_token):
        # get admin id
        me = requests.get(f"{API}/auth/me", headers=admin_headers).json()
        r = requests.delete(f"{API}/staff/{me['id']}", headers=admin_headers)
        assert r.status_code == 400

    def test_delete_staff(self, admin_headers):
        r = requests.delete(f"{API}/staff/{TestStaffAndPermissions._staff_id}", headers=admin_headers)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Consumo
# ---------------------------------------------------------------------------
class TestConsumo:
    def test_register_consumption_deducts_stock(self, admin_headers):
        # create fresh product
        p = requests.post(
            f"{API}/products",
            json={"name": f"TEST_C_{uuid.uuid4().hex[:4]}", "quantity": 10, "sale_price": 3.5, "cost_price": 1},
            headers=admin_headers,
        ).json()
        r = requests.post(
            f"{API}/consumption",
            json={"product_id": p["id"], "quantity": 2, "deduct_stock": True},
            headers=admin_headers,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["value"] == round(3.5 * 2, 2)
        # stock deducted
        g = requests.get(f"{API}/products", headers=admin_headers).json()
        prod = next(x for x in g if x["id"] == p["id"])
        assert prod["quantity"] == 8

    def test_list_consumption_admin(self, admin_headers):
        r = requests.get(f"{API}/consumption", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Faturacao
# ---------------------------------------------------------------------------
class TestFaturacao:
    _inv_id = None

    def test_create_invoice(self, admin_headers):
        r = requests.post(
            f"{API}/invoices",
            json={
                "client_name": "TEST Cliente",
                "client_nif": "123456789",
                "items": [
                    {"description": "Menu 1", "quantity": 2, "unit_price": 10.0, "vat_rate": 23.0},
                    {"description": "Bebida", "quantity": 3, "unit_price": 2.0, "vat_rate": 23.0},
                ],
            },
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        # subtotal = 20 + 6 = 26; vat = 26*0.23 = 5.98; total = 31.98
        assert d["subtotal"] == 26.0
        assert d["vat_total"] == 5.98
        assert d["total"] == 31.98
        assert d["number"].startswith("FT ")
        assert d["status"] == "rascunho"
        assert d["external_synced"] is False
        TestFaturacao._inv_id = d["id"]

    def test_sync_invoice(self, admin_headers):
        r = requests.post(f"{API}/invoices/{TestFaturacao._inv_id}/sync", headers=admin_headers)
        assert r.status_code == 200
        # verify list
        lst = requests.get(f"{API}/invoices", headers=admin_headers).json()
        inv = next(x for x in lst if x["id"] == TestFaturacao._inv_id)
        assert inv["external_synced"] is True
        assert inv["status"] == "emitida"
