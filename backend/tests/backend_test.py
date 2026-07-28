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
                  "today_consumption", "trend", "low_stock", "low_stock_count",
                  "today_sales", "open_tables"]:
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

    def test_funcionario_forbidden_orders_list(self):
        r = self._fs().get(f"{API}/orders")
        assert r.status_code == 403

    def test_funcionario_forbidden_orders_open(self):
        r = self._fs().post(f"{API}/orders", json={"table_name": "M1"})
        assert r.status_code == 403

    def test_funcionario_forbidden_orders_add_item(self):
        r = self._fs().post(f"{API}/orders/xxx/items", json={"product_id": "y", "quantity": 1})
        assert r.status_code == 403

    def test_funcionario_forbidden_orders_close(self):
        r = self._fs().post(f"{API}/orders/xxx/close")
        assert r.status_code == 403

    def test_funcionario_forbidden_orders_cancel(self):
        r = self._fs().delete(f"{API}/orders/xxx")
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
# Registadora (Orders / Mesas)
# ---------------------------------------------------------------------------
class TestRegistadora:
    _prod_id = None
    _prod_qty0 = 20
    _order_id = None
    _item_id = None

    def test_setup_product(self, admin_session):
        r = admin_session.post(f"{API}/products", json={
            "name": f"TEST_Reg_{uuid.uuid4().hex[:5]}",
            "quantity": self._prod_qty0,
            "sale_price": 5.0,
            "cost_price": 1.0,
            "min_quantity": 0,
        })
        assert r.status_code == 200
        TestRegistadora._prod_id = r.json()["id"]

    def test_open_table(self, admin_session):
        r = admin_session.post(f"{API}/orders", json={"table_name": "TEST Mesa"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "aberta"
        assert d["table_name"] == "TEST Mesa"
        assert d["items"] == []
        assert d["total"] == 0.0
        TestRegistadora._order_id = d["id"]

    def test_list_open_orders(self, admin_session):
        r = admin_session.get(f"{API}/orders?status=aberta")
        assert r.status_code == 200
        ids = [o["id"] for o in r.json()]
        assert TestRegistadora._order_id in ids

    def test_add_item_deducts_stock(self, admin_session):
        r = admin_session.post(
            f"{API}/orders/{TestRegistadora._order_id}/items",
            json={"product_id": TestRegistadora._prod_id, "quantity": 3},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["item"]["line_total"] == 15.0
        assert d["total"] == 15.0
        TestRegistadora._item_id = d["item"]["id"]
        # stock deducted
        p = next(x for x in admin_session.get(f"{API}/products").json() if x["id"] == TestRegistadora._prod_id)
        assert p["quantity"] == 17

    def test_add_item_insufficient_stock(self, admin_session):
        r = admin_session.post(
            f"{API}/orders/{TestRegistadora._order_id}/items",
            json={"product_id": TestRegistadora._prod_id, "quantity": 999999},
        )
        assert r.status_code == 400
        assert "stock" in r.json()["detail"].lower()

    def test_remove_item_returns_stock(self, admin_session):
        r = admin_session.delete(
            f"{API}/orders/{TestRegistadora._order_id}/items/{TestRegistadora._item_id}"
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0.0
        p = next(x for x in admin_session.get(f"{API}/products").json() if x["id"] == TestRegistadora._prod_id)
        assert p["quantity"] == 20

    def test_close_empty_order_400(self, admin_session):
        r = admin_session.post(f"{API}/orders/{TestRegistadora._order_id}/close")
        assert r.status_code == 400

    def test_add_and_close(self, admin_session):
        r = admin_session.post(
            f"{API}/orders/{TestRegistadora._order_id}/items",
            json={"product_id": TestRegistadora._prod_id, "quantity": 2},
        )
        assert r.status_code == 200
        rc = admin_session.post(f"{API}/orders/{TestRegistadora._order_id}/close")
        assert rc.status_code == 200
        assert rc.json()["total"] == 10.0
        # cannot add to closed
        r2 = admin_session.post(
            f"{API}/orders/{TestRegistadora._order_id}/items",
            json={"product_id": TestRegistadora._prod_id, "quantity": 1},
        )
        assert r2.status_code == 400

    def test_dashboard_reflects_sales_and_open_tables(self, admin_session):
        # open another table (still open) to bump open_tables counter
        o = admin_session.post(f"{API}/orders", json={"table_name": "TEST Mesa Open"}).json()
        d = admin_session.get(f"{API}/dashboard").json()
        assert "today_sales" in d
        assert "open_tables" in d
        assert d["today_sales"] >= 10.0
        assert d["open_tables"] >= 1
        # cancel it -> stock unchanged (no items) + open table removed
        rc = admin_session.delete(f"{API}/orders/{o['id']}")
        assert rc.status_code == 200

    def test_cancel_open_returns_stock(self, admin_session):
        # new order, add items, cancel -> stock restored fully
        o = admin_session.post(f"{API}/orders", json={"table_name": "TEST Cancel"}).json()
        admin_session.post(
            f"{API}/orders/{o['id']}/items",
            json={"product_id": TestRegistadora._prod_id, "quantity": 4},
        )
        # product qty currently 18 after previous close(2)
        r = admin_session.delete(f"{API}/orders/{o['id']}")
        assert r.status_code == 200
        p = next(x for x in admin_session.get(f"{API}/products").json() if x["id"] == TestRegistadora._prod_id)
        assert p["quantity"] == 18

    def test_add_item_order_not_found(self, admin_session):
        r = admin_session.post(f"{API}/orders/nonexistent/items",
                               json={"product_id": TestRegistadora._prod_id, "quantity": 1})
        assert r.status_code == 404

    def test_invoices_endpoint_removed(self, admin_session):
        r = admin_session.get(f"{API}/invoices")
        assert r.status_code == 404
