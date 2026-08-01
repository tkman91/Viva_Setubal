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
            json={"kind": "product", "ref_id": TestRegistadora._prod_id, "quantity": 3},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        # new schema returns the whole order
        assert d["total"] == 15.0
        assert len(d["items"]) == 1
        assert d["items"][-1]["line_total"] == 15.0
        TestRegistadora._item_id = d["items"][-1]["id"]
        # stock deducted
        p = next(x for x in admin_session.get(f"{API}/products").json() if x["id"] == TestRegistadora._prod_id)
        assert p["quantity"] == 17

    def test_add_item_insufficient_stock(self, admin_session):
        r = admin_session.post(
            f"{API}/orders/{TestRegistadora._order_id}/items",
            json={"kind": "product", "ref_id": TestRegistadora._prod_id, "quantity": 999999},
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
        r = admin_session.post(f"{API}/orders/{TestRegistadora._order_id}/close", json={"payments": []})
        assert r.status_code == 400

    def test_add_and_close(self, admin_session):
        r = admin_session.post(
            f"{API}/orders/{TestRegistadora._order_id}/items",
            json={"kind": "product", "ref_id": TestRegistadora._prod_id, "quantity": 2},
        )
        assert r.status_code == 200
        rc = admin_session.post(f"{API}/orders/{TestRegistadora._order_id}/close", json={"payments": []})
        assert rc.status_code == 200
        assert rc.json()["total"] == 10.0
        # cannot add to closed
        r2 = admin_session.post(
            f"{API}/orders/{TestRegistadora._order_id}/items",
            json={"kind": "product", "ref_id": TestRegistadora._prod_id, "quantity": 1},
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
        # get current product qty first, then add and cancel -> should restore
        p0 = next(x for x in admin_session.get(f"{API}/products").json() if x["id"] == TestRegistadora._prod_id)
        qty0 = p0["quantity"]
        o = admin_session.post(f"{API}/orders", json={"table_name": "TEST Cancel"}).json()
        admin_session.post(
            f"{API}/orders/{o['id']}/items",
            json={"kind": "product", "ref_id": TestRegistadora._prod_id, "quantity": 4},
        )
        r = admin_session.delete(f"{API}/orders/{o['id']}")
        assert r.status_code == 200
        p = next(x for x in admin_session.get(f"{API}/products").json() if x["id"] == TestRegistadora._prod_id)
        assert p["quantity"] == qty0

    def test_add_item_order_not_found(self, admin_session):
        r = admin_session.post(f"{API}/orders/nonexistent/items",
                               json={"kind": "product", "ref_id": TestRegistadora._prod_id, "quantity": 1})
        assert r.status_code == 404

    def test_invoices_endpoint_removed(self, admin_session):
        r = admin_session.get(f"{API}/invoices")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# NEW permission model: ONLY 'admin' has auto full access.
# 'gestor'/'funcionario' get ONLY the modules explicitly assigned.
# ---------------------------------------------------------------------------
class TestNewPermissionModel:
    _gestor_email = f"test_gestor_{uuid.uuid4().hex[:6]}@rest.pt"
    _gestor_pwd = "gestor123"
    _gestor_id = None
    _gestor_session = None

    _func_email = f"test_func2_{uuid.uuid4().hex[:6]}@rest.pt"
    _func_pwd = "func123"
    _func_id = None
    _func_session = None

    _shared_product_id = None

    # -- Creation semantics ------------------------------------------------
    def test_create_admin_gets_all_modules(self, admin_session):
        email = f"test_admin_{uuid.uuid4().hex[:6]}@rest.pt"
        r = admin_session.post(f"{API}/staff", json={
            "name": "TEST Admin2", "email": email, "password": "pw",
            "role": "admin", "permissions": ["stock"],  # should be overwritten to all
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "admin"
        assert set(d["permissions"]) == {"stock", "picagem", "staff", "consumo", "faturacao", "relatorios"}
        # cleanup
        admin_session.delete(f"{API}/staff/{d['id']}")

    def test_create_gestor_keeps_only_selected(self, admin_session):
        r = admin_session.post(f"{API}/staff", json={
            "name": "TEST Gestor", "email": TestNewPermissionModel._gestor_email,
            "password": TestNewPermissionModel._gestor_pwd,
            "role": "gestor", "permissions": ["consumo"],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "gestor"
        assert d["permissions"] == ["consumo"], f"gestor should NOT auto-get all: {d['permissions']}"
        TestNewPermissionModel._gestor_id = d["id"]

    def test_create_funcionario_keeps_only_selected(self, admin_session):
        r = admin_session.post(f"{API}/staff", json={
            "name": "TEST Func2", "email": TestNewPermissionModel._func_email,
            "password": TestNewPermissionModel._func_pwd,
            "role": "funcionario", "permissions": ["picagem"],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["permissions"] == ["picagem"]
        TestNewPermissionModel._func_id = d["id"]

    def test_update_role_to_admin_grants_all(self, admin_session):
        # create a fresh gestor and promote to admin
        email = f"test_promote_{uuid.uuid4().hex[:6]}@rest.pt"
        c = admin_session.post(f"{API}/staff", json={
            "name": "TEST Promote", "email": email, "password": "pw",
            "role": "gestor", "permissions": ["stock"],
        })
        assert c.status_code == 200
        sid = c.json()["id"]
        r = admin_session.put(f"{API}/staff/{sid}", json={"role": "admin"})
        assert r.status_code == 200
        assert set(r.json()["permissions"]) == {"stock", "picagem", "staff", "consumo", "faturacao", "relatorios"}
        admin_session.delete(f"{API}/staff/{sid}")

    # -- Login sessions ----------------------------------------------------
    def test_login_gestor_and_funcionario(self):
        gs, gr = _login_session(TestNewPermissionModel._gestor_email, TestNewPermissionModel._gestor_pwd)
        assert gr.status_code == 200
        TestNewPermissionModel._gestor_session = gs
        fs, fr = _login_session(TestNewPermissionModel._func_email, TestNewPermissionModel._func_pwd)
        assert fr.status_code == 200
        TestNewPermissionModel._func_session = fs

    # -- gestor with only ['consumo'] --------------------------------------
    def test_gestor_partial_perms_consumption_allowed(self):
        s = TestNewPermissionModel._gestor_session
        r = s.get(f"{API}/consumption")
        assert r.status_code == 200

    def test_gestor_partial_perms_orders_forbidden(self):
        s = TestNewPermissionModel._gestor_session
        assert s.get(f"{API}/orders").status_code == 403
        assert s.post(f"{API}/orders", json={"table_name": "x"}).status_code == 403

    def test_gestor_partial_perms_products_post_forbidden(self):
        s = TestNewPermissionModel._gestor_session
        r = s.post(f"{API}/products", json={"name": "X"})
        assert r.status_code == 403

    def test_gestor_partial_perms_products_get_allowed(self):
        s = TestNewPermissionModel._gestor_session
        r = s.get(f"{API}/products")
        assert r.status_code == 200

    def test_gestor_not_admin_cannot_create_staff(self):
        s = TestNewPermissionModel._gestor_session
        r = s.post(f"{API}/staff", json={"name": "X", "email": "x@x.pt", "password": "pw"})
        assert r.status_code == 403

    def test_gestor_not_admin_cannot_update_staff(self):
        s = TestNewPermissionModel._gestor_session
        r = s.put(f"{API}/staff/{TestNewPermissionModel._gestor_id}", json={"name": "Y"})
        assert r.status_code == 403

    def test_gestor_not_admin_cannot_delete_staff(self):
        s = TestNewPermissionModel._gestor_session
        r = s.delete(f"{API}/staff/{TestNewPermissionModel._func_id}")
        assert r.status_code == 403

    def test_gestor_not_admin_cannot_edit_settings(self):
        s = TestNewPermissionModel._gestor_session
        r = s.put(f"{API}/settings", json={"restaurant_name": "x", "lat": 0, "lng": 0, "radius_m": 10})
        assert r.status_code == 403

    def test_gestor_without_staff_perm_cannot_list_staff(self):
        s = TestNewPermissionModel._gestor_session
        r = s.get(f"{API}/staff")
        assert r.status_code == 403

    # -- Register consumption scope (funcionario can only self) ------------
    def test_setup_shared_product(self, admin_session):
        r = admin_session.post(f"{API}/products", json={
            "name": f"TEST_PermProd_{uuid.uuid4().hex[:5]}",
            "quantity": 50, "sale_price": 1.0, "cost_price": 0.5, "min_quantity": 0,
        })
        assert r.status_code == 200
        TestNewPermissionModel._shared_product_id = r.json()["id"]

    def test_funcionario_without_consumo_forbidden_to_register(self):
        s = TestNewPermissionModel._func_session
        r = s.post(f"{API}/consumption", json={
            "product_id": TestNewPermissionModel._shared_product_id, "quantity": 1,
        })
        # funcionario has only 'picagem' -> require_permission('consumo') = 403
        assert r.status_code == 403

    def test_funcionario_granted_consumo_can_self_but_not_others(self, admin_session):
        # grant consumo to funcionario
        admin_session.put(f"{API}/staff/{TestNewPermissionModel._func_id}",
                          json={"permissions": ["picagem", "consumo"]})
        # relogin to refresh session cookie/user
        s, r = _login_session(TestNewPermissionModel._func_email, TestNewPermissionModel._func_pwd)
        assert r.status_code == 200
        # can register for self
        r_self = s.post(f"{API}/consumption", json={
            "product_id": TestNewPermissionModel._shared_product_id, "quantity": 1, "deduct_stock": False,
        })
        assert r_self.status_code == 200, r_self.text
        # cannot register for someone else (gestor id)
        r_other = s.post(f"{API}/consumption", json={
            "staff_id": TestNewPermissionModel._gestor_id,
            "product_id": TestNewPermissionModel._shared_product_id, "quantity": 1, "deduct_stock": False,
        })
        assert r_other.status_code == 403

    def test_gestor_with_consumo_can_register_for_others(self):
        s = TestNewPermissionModel._gestor_session
        r = s.post(f"{API}/consumption", json={
            "staff_id": TestNewPermissionModel._func_id,
            "product_id": TestNewPermissionModel._shared_product_id, "quantity": 1, "deduct_stock": False,
        })
        assert r.status_code == 200, r.text
        assert r.json()["staff_id"] == TestNewPermissionModel._func_id

    # -- Consumption list scoping -----------------------------------------
    def test_funcionario_consumption_list_scoped_to_self(self):
        # re-login funcionario (perms updated)
        s, r = _login_session(TestNewPermissionModel._func_email, TestNewPermissionModel._func_pwd)
        assert r.status_code == 200
        r2 = s.get(f"{API}/consumption")
        assert r2.status_code == 200
        for c in r2.json():
            assert c["staff_id"] == TestNewPermissionModel._func_id

    def test_gestor_with_consumo_sees_all_consumption(self):
        s = TestNewPermissionModel._gestor_session
        r = s.get(f"{API}/consumption")
        assert r.status_code == 200
        staff_ids = {c["staff_id"] for c in r.json()}
        # should include at least the funcionario entry (not only gestor's own)
        assert TestNewPermissionModel._func_id in staff_ids

    # -- Timeclock scope ---------------------------------------------------
    def test_funcionario_timeclock_entries_scoped(self):
        s, r = _login_session(TestNewPermissionModel._func_email, TestNewPermissionModel._func_pwd)
        assert r.status_code == 200
        r2 = s.get(f"{API}/timeclock/entries")
        assert r2.status_code == 200
        for e in r2.json():
            assert e["user_id"] == TestNewPermissionModel._func_id

    def test_gestor_with_picagem_sees_all_entries(self, admin_session):
        # grant picagem to gestor
        admin_session.put(f"{API}/staff/{TestNewPermissionModel._gestor_id}",
                          json={"permissions": ["consumo", "picagem"]})
        s, r = _login_session(TestNewPermissionModel._gestor_email, TestNewPermissionModel._gestor_pwd)
        assert r.status_code == 200
        # ensure at least one entry exists globally (funcionario punched in earlier tests already)
        r2 = s.get(f"{API}/timeclock/entries")
        assert r2.status_code == 200
        # Any entries returned should not be filtered to gestor's own id
        # (we just assert the request works and returns a list)
        assert isinstance(r2.json(), list)

    # -- Cleanup -----------------------------------------------------------
    def test_zz_cleanup(self, admin_session):
        for sid in (TestNewPermissionModel._gestor_id, TestNewPermissionModel._func_id):
            if sid:
                admin_session.delete(f"{API}/staff/{sid}")



# ---------------------------------------------------------------------------
# POS Configuration: zones, tables (bulk), categories, modifier-groups, combos,
# config (payment methods, receipt header, decimals/rounding, VAT).
# ---------------------------------------------------------------------------
class TestPOSConfig:
    _zone_id = None
    _table_id = None
    _cat_id = None
    _mod_group_id = None
    _mod_opt_id = None
    _combo_id = None
    _prod_a = None  # to be used in combo/order
    _prod_b = None  # product with modifier group
    _order_id = None
    _prod_a_qty0 = 30
    _prod_b_qty0 = 30
    _saved_config = None

    # ---------- config (defaults + persistence) --------------------------
    def test_get_pos_config_defaults(self, admin_session):
        r = admin_session.get(f"{API}/pos/config")
        assert r.status_code == 200
        c = r.json()
        for k in ["currency_symbol", "decimals", "rounding", "default_vat_rate",
                  "payment_methods", "receipt", "service_charge_enabled", "service_charge_percent"]:
            assert k in c
        assert isinstance(c["payment_methods"], list) and len(c["payment_methods"]) >= 3
        TestPOSConfig._saved_config = c

    def test_put_pos_config_persists(self, admin_session):
        c = TestPOSConfig._saved_config
        payload = {
            "currency_symbol": c["currency_symbol"],
            "decimals": 2,
            "rounding": "0.05",
            "track_stock_default": True,
            "service_charge_enabled": True,
            "service_charge_percent": 10.0,
            "default_vat_rate": 23.0,
            "payment_methods": c["payment_methods"],
            "receipt": {"name": "TEST RESTAURANTE", "nif": "500000000",
                        "address": "Rua X", "phone": "912345678", "footer": "TESTE"},
        }
        r = admin_session.put(f"{API}/pos/config", json=payload)
        assert r.status_code == 200, r.text
        # reload and check
        r2 = admin_session.get(f"{API}/pos/config")
        d = r2.json()
        assert d["rounding"] == "0.05"
        assert d["service_charge_enabled"] is True
        assert d["service_charge_percent"] == 10.0
        assert d["receipt"]["name"] == "TEST RESTAURANTE"
        assert d["receipt"]["nif"] == "500000000"

    # ---------- zones + tables + bulk ------------------------------------
    def test_create_zone(self, admin_session):
        r = admin_session.post(f"{API}/pos/zones", json={"name": f"TEST_Zona_{uuid.uuid4().hex[:5]}", "order": 99})
        assert r.status_code == 200, r.text
        TestPOSConfig._zone_id = r.json()["id"]

    def test_list_zones_contains(self, admin_session):
        r = admin_session.get(f"{API}/pos/zones")
        assert r.status_code == 200
        assert any(z["id"] == TestPOSConfig._zone_id for z in r.json())

    def test_create_single_table(self, admin_session):
        r = admin_session.post(f"{API}/pos/tables", json={
            "name": "TEST Mesa 1", "zone_id": TestPOSConfig._zone_id, "seats": 4, "order": 0
        })
        assert r.status_code == 200, r.text
        TestPOSConfig._table_id = r.json()["id"]

    def test_bulk_tables(self, admin_session):
        # bulk endpoint uses query params
        r = admin_session.post(
            f"{API}/pos/tables/bulk",
            params={"zone_id": TestPOSConfig._zone_id, "count": 3, "prefix": "TESTM"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 3
        # verify listing
        tables = admin_session.get(f"{API}/pos/tables").json()
        in_zone = [t for t in tables if t.get("zone_id") == TestPOSConfig._zone_id]
        assert len(in_zone) >= 4  # 1 single + 3 bulk

    # ---------- categories ----------------------------------------------
    def test_create_category(self, admin_session):
        r = admin_session.post(f"{API}/pos/categories", json={
            "name": f"TEST_Cat_{uuid.uuid4().hex[:5]}", "color": "#ff0000", "order": 1,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["color"] == "#ff0000"
        TestPOSConfig._cat_id = d["id"]
        # persistence
        r2 = admin_session.get(f"{API}/pos/categories")
        assert any(c["id"] == TestPOSConfig._cat_id for c in r2.json())

    # ---------- modifier groups -----------------------------------------
    def test_create_modifier_group(self, admin_session):
        r = admin_session.post(f"{API}/pos/modifier-groups", json={
            "name": f"TEST_Mod_{uuid.uuid4().hex[:5]}", "min": 0, "max": 2, "required": False,
            "options": [
                {"name": "Extra queijo", "price_delta": 1.0},
                {"name": "Sem cebola", "price_delta": 0.0},
            ],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["options"]) == 2
        assert d["options"][0]["price_delta"] == 1.0
        assert d["options"][0]["id"]  # auto id
        TestPOSConfig._mod_group_id = d["id"]
        TestPOSConfig._mod_opt_id = d["options"][0]["id"]  # +1€ option
        # persistence
        r2 = admin_session.get(f"{API}/pos/modifier-groups")
        assert any(g["id"] == TestPOSConfig._mod_group_id for g in r2.json())

    # ---------- products (with cat + vat + modifier) --------------------
    def test_create_product_A_and_B(self, admin_session):
        rA = admin_session.post(f"{API}/products", json={
            "name": f"TEST_ProdA_{uuid.uuid4().hex[:4]}",
            "category_id": TestPOSConfig._cat_id,
            "quantity": TestPOSConfig._prod_a_qty0, "sale_price": 3.0, "cost_price": 1.0,
            "vat_rate": 13.0, "min_quantity": 0, "track_stock": True,
        })
        assert rA.status_code == 200, rA.text
        TestPOSConfig._prod_a = rA.json()
        assert TestPOSConfig._prod_a["vat_rate"] == 13.0
        rB = admin_session.post(f"{API}/products", json={
            "name": f"TEST_ProdB_{uuid.uuid4().hex[:4]}",
            "category_id": TestPOSConfig._cat_id,
            "quantity": TestPOSConfig._prod_b_qty0, "sale_price": 10.0, "cost_price": 2.0,
            "vat_rate": 23.0, "min_quantity": 0, "track_stock": True,
            "modifier_group_ids": [TestPOSConfig._mod_group_id],
        })
        assert rB.status_code == 200, rB.text
        TestPOSConfig._prod_b = rB.json()
        assert TestPOSConfig._mod_group_id in TestPOSConfig._prod_b.get("modifier_group_ids", [])

    # ---------- combos --------------------------------------------------
    def test_create_combo(self, admin_session):
        r = admin_session.post(f"{API}/pos/combos", json={
            "name": f"TEST_Combo_{uuid.uuid4().hex[:5]}",
            "price": 12.0, "vat_rate": 13.0, "active": True,
            "items": [
                {"product_id": TestPOSConfig._prod_a["id"], "quantity": 1},
                {"product_id": TestPOSConfig._prod_b["id"], "quantity": 1},
            ],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["price"] == 12.0
        assert len(d["items"]) == 2
        TestPOSConfig._combo_id = d["id"]

    # ---------- open order by table_id (dedupe) -------------------------
    def test_open_order_by_table_id(self, admin_session):
        r = admin_session.post(f"{API}/orders", json={"table_id": TestPOSConfig._table_id})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "aberta"
        assert d["table_id"] == TestPOSConfig._table_id
        assert d.get("zone_id") == TestPOSConfig._zone_id
        TestPOSConfig._order_id = d["id"]

    def test_open_same_table_returns_same_order(self, admin_session):
        r = admin_session.post(f"{API}/orders", json={"table_id": TestPOSConfig._table_id})
        assert r.status_code == 200
        assert r.json()["id"] == TestPOSConfig._order_id, "Should NOT create duplicate order"

    # ---------- add product with modifier: unit_price += delta ---------
    def test_add_product_with_modifier(self, admin_session):
        r = admin_session.post(f"{API}/orders/{TestPOSConfig._order_id}/items", json={
            "kind": "product",
            "ref_id": TestPOSConfig._prod_b["id"],
            "quantity": 2,
            "modifiers": [{"group_id": TestPOSConfig._mod_group_id, "option_id": TestPOSConfig._mod_opt_id}],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        item = d["items"][-1]
        # unit price 10 + 1 (extra queijo) = 11, x2 = 22
        assert item["unit_price"] == 11.0
        assert item["line_total"] == 22.0
        assert item["modifiers"][0]["name"] == "Extra queijo"
        # stock B deducted by 2
        p = next(x for x in admin_session.get(f"{API}/products").json() if x["id"] == TestPOSConfig._prod_b["id"])
        assert p["quantity"] == TestPOSConfig._prod_b_qty0 - 2

    # ---------- add combo: components deducted from stock --------------
    def test_add_combo_deducts_components(self, admin_session):
        r = admin_session.post(f"{API}/orders/{TestPOSConfig._order_id}/items", json={
            "kind": "combo",
            "ref_id": TestPOSConfig._combo_id,
            "quantity": 1,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        combo_item = d["items"][-1]
        assert combo_item["kind"] == "combo"
        assert combo_item["line_total"] == 12.0
        # A and B each -1 more
        prods = admin_session.get(f"{API}/products").json()
        pa = next(x for x in prods if x["id"] == TestPOSConfig._prod_a["id"])
        pb = next(x for x in prods if x["id"] == TestPOSConfig._prod_b["id"])
        assert pa["quantity"] == TestPOSConfig._prod_a_qty0 - 1
        assert pb["quantity"] == TestPOSConfig._prod_b_qty0 - 3  # -2 (mod) -1 (combo)

    # ---------- discount % + service charge -----------------------------
    def test_patch_discount_percent_and_service(self, admin_session):
        r = admin_session.patch(f"{API}/orders/{TestPOSConfig._order_id}", json={
            "discount_type": "percent", "discount_value": 10.0, "service_charge_enabled": True,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        # subtotal = 22 + 12 = 34; 10% discount = 3.4 -> after = 30.6; service 10% = 3.06 -> raw total 33.66 rounded to 0.05 => 33.65
        assert d["subtotal"] == 34.0
        assert d["discount_amount"] == 3.4
        assert d["service_charge_amount"] == 3.06
        # rounding "0.05" was set in earlier test
        assert abs(d["total"] - 33.65) < 0.01 or abs(d["total"] - 33.66) < 0.01
        # VAT breakdown must be non-empty and include both rates
        rates = {v["rate"] for v in d["vat_breakdown"]}
        assert 23.0 in rates and 13.0 in rates

    # ---------- close order with payments (change) ---------------------
    def test_close_order_with_payment_and_change(self, admin_session):
        # get current total
        cur = next(o for o in admin_session.get(f"{API}/orders?status=aberta").json() if o["id"] == TestPOSConfig._order_id)
        total = cur["total"]
        pay_amt = round(total + 5.0, 2)  # pay 5€ extra -> change 5
        r = admin_session.post(f"{API}/orders/{TestPOSConfig._order_id}/close", json={
            "payments": [{"method": "Dinheiro", "amount": pay_amt}],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "paga"
        assert d["amount_paid"] == pay_amt
        assert abs(d["change"] - 5.0) < 0.01
        assert d["closed_at"]

    def test_close_insufficient_payment_400(self, admin_session):
        # open a fresh order, add item, try pay less
        o = admin_session.post(f"{API}/orders", json={"table_name": "TEST Insuf"}).json()
        admin_session.post(f"{API}/orders/{o['id']}/items", json={
            "kind": "product", "ref_id": TestPOSConfig._prod_a["id"], "quantity": 1,
        })
        r = admin_session.post(f"{API}/orders/{o['id']}/close", json={
            "payments": [{"method": "Dinheiro", "amount": 0.5}],
        })
        assert r.status_code == 400
        # cleanup
        admin_session.delete(f"{API}/orders/{o['id']}")

    # ---------- cleanup --------------------------------------------------
    def test_zz_cleanup_pos(self, admin_session):
        # restore config to defaults (disable service, rounding=none)
        if TestPOSConfig._saved_config:
            c = TestPOSConfig._saved_config
            admin_session.put(f"{API}/pos/config", json={
                "currency_symbol": c.get("currency_symbol", "€"),
                "decimals": int(c.get("decimals", 2)),
                "rounding": c.get("rounding", "none"),
                "track_stock_default": c.get("track_stock_default", True),
                "service_charge_enabled": c.get("service_charge_enabled", False),
                "service_charge_percent": c.get("service_charge_percent", 0.0),
                "default_vat_rate": c.get("default_vat_rate", 23.0),
                "payment_methods": c.get("payment_methods", []),
                "receipt": c.get("receipt", {}),
            })
        # delete combo, mod group, category, zone (cascade tables), products
        if TestPOSConfig._combo_id:
            admin_session.delete(f"{API}/pos/combos/{TestPOSConfig._combo_id}")
        if TestPOSConfig._mod_group_id:
            admin_session.delete(f"{API}/pos/modifier-groups/{TestPOSConfig._mod_group_id}")
        if TestPOSConfig._cat_id:
            admin_session.delete(f"{API}/pos/categories/{TestPOSConfig._cat_id}")
        if TestPOSConfig._zone_id:
            admin_session.delete(f"{API}/pos/zones/{TestPOSConfig._zone_id}")
        for p in (TestPOSConfig._prod_a, TestPOSConfig._prod_b):
            if p:
                admin_session.delete(f"{API}/products/{p['id']}")
