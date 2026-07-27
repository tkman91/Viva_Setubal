"""Backend API regression tests for Gestão Restaurante (cookie-based auth)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@restaurante.pt"
ADMIN_PASSWORD = "admin123"


def _login_session(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    return s, r


@pytest.fixture(scope="session")
def admin_session():
    s, r = _login_session(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    # New auth: body must contain only {user}, no token
    assert "user" in data
    assert "token" not in data, "Response body should not contain token when cookie-based auth is used"
    assert data["user"]["email"] == ADMIN_EMAIL
    # Cookie must be set with httpOnly
    cookie = None
    for c in s.cookies:
        if c.name == "access_token":
            cookie = c
    assert cookie is not None, "access_token cookie not set"
    # httpOnly is stored in cookie._rest by requests
    rest = getattr(cookie, "_rest", {}) or {}
    lowered = {k.lower(): v for k, v in rest.items()}
    assert "httponly" in lowered, f"cookie missing HttpOnly flag: rest={rest}"
    return s


# ---------------------------------------------------------------------------
# Auth (cookie-based)
# ---------------------------------------------------------------------------
class TestAuth:
    def test_login_sets_cookie_and_no_token_in_body(self, admin_session):
        # verified in fixture
        assert admin_session.cookies.get("access_token")

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_me_with_cookie(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_me_without_cookie_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout_clears_cookie(self):
        s, r = _login_session(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert r.status_code == 200
        # logout
        r2 = s.post(f"{API}/auth/logout")
        assert r2.status_code == 200
        # session cookie should be cleared server-side; simulate fresh cookie jar
        s2 = requests.Session()
        r3 = s2.get(f"{API}/auth/me")
        assert r3.status_code == 401


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class TestDashboard:
    def test_dashboard_kpis(self, admin_session):
        r = admin_session.get(f"{API}/dashboard")
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

    def test_create_product(self, admin_session):
        payload = {
            "name": f"TEST_Produto_{uuid.uuid4().hex[:6]}",
            "category": "Bebidas",
            "unit": "un",
            "quantity": 10,
            "min_quantity": 5,
            "cost_price": 1.0,
            "sale_price": 2.5,
        }
        r = admin_session.post(f"{API}/products", json=payload)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["name"] == payload["name"]
        assert doc["quantity"] == 10
        TestStock._product_id = doc["id"]

    def test_list_products_contains(self, admin_session):
        r = admin_session.get(f"{API}/products")
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert TestStock._product_id in ids

    def test_update_product(self, admin_session):
        r = admin_session.put(
            f"{API}/products/{TestStock._product_id}",
            json={"min_quantity": 20},
        )
        assert r.status_code == 200
        assert r.json()["min_quantity"] == 20

    def test_movement_entrada(self, admin_session):
        r = admin_session.post(
            f"{API}/stock/movement",
            json={"product_id": TestStock._product_id, "type": "entrada", "quantity": 5},
        )
        assert r.status_code == 200
        g = admin_session.get(f"{API}/products").json()
        p = next(x for x in g if x["id"] == TestStock._product_id)
        assert p["quantity"] == 15

    def test_movement_saida(self, admin_session):
        r = admin_session.post(
            f"{API}/stock/movement",
            json={"product_id": TestStock._product_id, "type": "saida", "quantity": 3},
        )
        assert r.status_code == 200
        g = admin_session.get(f"{API}/products").json()
        p = next(x for x in g if x["id"] == TestStock._product_id)
        assert p["quantity"] == 12

    def test_movement_insufficient(self, admin_session):
        r = admin_session.post(
            f"{API}/stock/movement",
            json={"product_id": TestStock._product_id, "type": "saida", "quantity": 999999},
        )
        assert r.status_code == 400

    def test_low_stock_reflected(self, admin_session):
        d = admin_session.get(f"{API}/dashboard").json()
        low_ids = [p["id"] for p in d["low_stock"]]
        assert TestStock._product_id in low_ids


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
RESTAURANT_LAT = 38.7223
RESTAURANT_LNG = -9.1393
RADIUS_M = 150


@pytest.fixture(scope="session", autouse=True)
def _ensure_settings(admin_session):
    admin_session.put(
        f"{API}/settings",
        json={
            "restaurant_name": "TEST Restaurante",
            "lat": RESTAURANT_LAT,
            "lng": RESTAURANT_LNG,
            "radius_m": RADIUS_M,
        },
    )


class TestSettings:
    def test_update_settings_admin(self, admin_session):
        r = admin_session.put(
            f"{API}/settings",
            json={
                "restaurant_name": "TEST Restaurante",
                "lat": RESTAURANT_LAT,
                "lng": RESTAURANT_LNG,
                "radius_m": RADIUS_M,
            },
        )
        assert r.status_code == 200
        assert r.json()["radius_m"] == RADIUS_M

    def test_get_settings(self, admin_session):
        r = admin_session.get(f"{API}/settings")
        assert r.status_code == 200
        assert r.json()["restaurant_name"] == "TEST Restaurante"


# ---------------------------------------------------------------------------
# Staff mgmt + permissions
# ---------------------------------------------------------------------------
class TestStaffAndPermissions:
    _staff_id = None
    _staff_session = None
    _staff_email = f"test_func_{uuid.uuid4().hex[:6]}@rest.pt"
    _staff_pwd = "func123"

    def test_admin_create_funcionario(self, admin_session):
        r = admin_session.post(
            f"{API}/staff",
            json={
                "name": "TEST Funcionario",
                "email": TestStaffAndPermissions._staff_email,
                "password": TestStaffAndPermissions._staff_pwd,
                "role": "funcionario",
                "permissions": ["picagem"],
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "funcionario"
        assert d["permissions"] == ["picagem"]
        TestStaffAndPermissions._staff_id = d["id"]

    def test_list_staff_admin(self, admin_session):
        r = admin_session.get(f"{API}/staff")
        assert r.status_code == 200
        ids = [u["id"] for u in r.json()]
        assert TestStaffAndPermissions._staff_id in ids

    def test_funcionario_login(self):
        s, r = _login_session(TestStaffAndPermissions._staff_email, TestStaffAndPermissions._staff_pwd)
        assert r.status_code == 200
        assert "token" not in r.json()
        assert s.cookies.get("access_token")
        TestStaffAndPermissions._staff_session = s

    def _fs(self):
        return TestStaffAndPermissions._staff_session

    def test_funcionario_forbidden_products_post(self):
        r = self._fs().post(f"{API}/products", json={"name": "X"})
        assert r.status_code == 403

    def test_funcionario_forbidden_staff_list(self):
        r = self._fs().get(f"{API}/staff")
        assert r.status_code == 403

    def test_funcionario_forbidden_invoices(self):
        r = self._fs().get(f"{API}/invoices")
        assert r.status_code == 403

    def test_funcionario_forbidden_invoices_post(self):
        r = self._fs().post(f"{API}/invoices", json={"client_name": "X", "items": []})
        assert r.status_code == 403

    def test_funcionario_forbidden_staff_post(self):
        r = self._fs().post(f"{API}/staff", json={"name": "X", "email": "x@x.pt", "password": "x"})
        assert r.status_code == 403

    def test_funcionario_can_get_products(self):
        r = self._fs().get(f"{API}/products")
        assert r.status_code == 200

    def test_funcionario_forbidden_settings_put(self):
        r = self._fs().put(
            f"{API}/settings",
            json={"restaurant_name": "x", "lat": 0, "lng": 0, "radius_m": 10},
        )
        assert r.status_code == 403

    def test_funcionario_can_timeclock_status(self):
        r = self._fs().get(f"{API}/timeclock/status")
        assert r.status_code == 200

    def test_punch_far_rejected(self):
        r = self._fs().post(
            f"{API}/timeclock/punch",
            json={"lat": 0.0, "lng": 0.0},
        )
        assert r.status_code == 403
        assert "m" in r.json()["detail"].lower() or "restaurante" in r.json()["detail"].lower()

    def test_punch_near_entrada_then_saida(self):
        r = self._fs().post(
            f"{API}/timeclock/punch",
            json={"lat": RESTAURANT_LAT + 0.0001, "lng": RESTAURANT_LNG},
        )
        assert r.status_code == 200, r.text
        assert r.json()["action"] == "entrada"
        s = self._fs().get(f"{API}/timeclock/status").json()
        assert s["clocked_in"] is True
        r2 = self._fs().post(
            f"{API}/timeclock/punch",
            json={"lat": RESTAURANT_LAT, "lng": RESTAURANT_LNG},
        )
        assert r2.status_code == 200
        assert r2.json()["action"] == "saida"
        s2 = self._fs().get(f"{API}/timeclock/status").json()
        assert s2["clocked_in"] is False

    def test_timeclock_entries_scoped(self):
        r = self._fs().get(f"{API}/timeclock/entries")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        for e in r.json():
            assert e["user_id"] == TestStaffAndPermissions._staff_id

    def test_update_staff_permissions(self, admin_session):
        r = admin_session.put(
            f"{API}/staff/{TestStaffAndPermissions._staff_id}",
            json={"permissions": ["picagem", "consumo"]},
        )
        assert r.status_code == 200
        assert set(r.json()["permissions"]) == {"picagem", "consumo"}

    def test_cannot_delete_self(self, admin_session):
        me = admin_session.get(f"{API}/auth/me").json()
        r = admin_session.delete(f"{API}/staff/{me['id']}")
        assert r.status_code == 400

    def test_delete_staff(self, admin_session):
        r = admin_session.delete(f"{API}/staff/{TestStaffAndPermissions._staff_id}")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Consumo
# ---------------------------------------------------------------------------
class TestConsumo:
    def test_register_consumption_deducts_stock(self, admin_session):
        p = admin_session.post(
            f"{API}/products",
            json={"name": f"TEST_C_{uuid.uuid4().hex[:4]}", "quantity": 10, "sale_price": 3.5, "cost_price": 1},
        ).json()
        r = admin_session.post(
            f"{API}/consumption",
            json={"product_id": p["id"], "quantity": 2, "deduct_stock": True},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["value"] == round(3.5 * 2, 2)
        g = admin_session.get(f"{API}/products").json()
        prod = next(x for x in g if x["id"] == p["id"])
        assert prod["quantity"] == 8

    def test_list_consumption_admin(self, admin_session):
        r = admin_session.get(f"{API}/consumption")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Faturacao
# ---------------------------------------------------------------------------
class TestFaturacao:
    _inv_id = None

    def test_create_invoice(self, admin_session):
        r = admin_session.post(
            f"{API}/invoices",
            json={
                "client_name": "TEST Cliente",
                "client_nif": "123456789",
                "items": [
                    {"description": "Menu 1", "quantity": 2, "unit_price": 10.0, "vat_rate": 23.0},
                    {"description": "Bebida", "quantity": 3, "unit_price": 2.0, "vat_rate": 23.0},
                ],
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["subtotal"] == 26.0
        assert d["vat_total"] == 5.98
        assert d["total"] == 31.98
        assert d["number"].startswith("FT ")
        assert d["status"] == "rascunho"
        assert d["external_synced"] is False
        TestFaturacao._inv_id = d["id"]

    def test_sync_invoice(self, admin_session):
        r = admin_session.post(f"{API}/invoices/{TestFaturacao._inv_id}/sync")
        assert r.status_code == 200
        lst = admin_session.get(f"{API}/invoices").json()
        inv = next(x for x in lst if x["id"] == TestFaturacao._inv_id)
        assert inv["external_synced"] is True
        assert inv["status"] == "emitida"
